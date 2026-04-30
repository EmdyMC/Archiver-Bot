import discord
import asyncio
import os, sys
import difflib
from datetime import timedelta
from discord.ext import commands
from discord import app_commands
from constants import LOG_CHANNEL, MODERATOR_ID, OTHER_ARCHIVES, HIGHER_ROLES, HELPER_ID, COMMANDS_LIST, DISCORD_CHAR_LIMIT

# Create tags selector
class TagSelectView(discord.ui.View):
    def __init__(self, tags: list[discord.ForumTag], thread: discord.Thread):
        super().__init__()
        self.selected_tags = []
        self.thread = thread
        self.all_tags = tags
        options = [discord.SelectOption(label=tag.name, emoji=tag.emoji, value=str(tag.id)) for tag in tags[:25]]
        self.tag_select = discord.ui.Select(
            placeholder="Choose the tags for the post. . .",
            min_values=1,
            max_values=min(5, len(options)),
            options=options
        )
        self.tag_select.callback = self.select_callback
        self.add_item(self.tag_select)
    async def select_callback(self, interaction:discord.Interaction):
        await interaction.response.defer()
        self.tag_select.disabled = True
        self.selected_tags = self.tag_select.values
        tags_to_apply =  [tag for tag in self.all_tags if str(tag.id) in self.selected_tags]
        log_message = []
        utility_cog = interaction.client.get_cog("Utility")
        for tag in tags_to_apply:
            emoji = tag.emoji or ""
            log_message.append(f"{emoji} {tag.name}".strip())
        if log_message:
            await utility_cog.log(title=f"Tags {",  ".join(log_message)} added", message=f"To post: **{self.thread.jump_url}**\nBy: {interaction.user.mention}")
        await self.thread.edit(applied_tags=tags_to_apply)
        await interaction.edit_original_response(content="Tags set!", view=None)

class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Log function
    async def log(self, title: str, message: str, colour: discord.Color = discord.Color.default()):
        log_channel = self.bot.get_channel(LOG_CHANNEL)
        if log_channel:
            embed = discord.Embed(title=title, description=message, color=colour)
            sent_message = await log_channel.send(embed=embed)
            return sent_message
    
    async def log_embed(self, embed: discord.Embed):
        log_channel = self.bot.get_channel(LOG_CHANNEL)
        if log_channel:
            sent_message = await log_channel.send(embed=embed)
            return sent_message      

    # Timeout function
    async def timeout_user(self, seconds: int, user: discord.Member):
        try:
            until = discord.utils.utcnow() + timedelta(seconds=seconds)
            await user.timeout(until, reason="No chat user caught")
        except discord.Forbidden:
            await self.log(title="Timeout failed", message=f"Could not timeout user {user.mention}, no permission.", colour=discord.Color.orange())

    # Fetch thread ID given name
    async def get_thread_by_name(self, channel, name):
        for thread in channel.threads:
            if thread.name == name:
                return thread
        async for thread in channel.archived_threads(limit=None):
            if thread.name == name:
                return thread
        await self.log(title=f"Could not find discussion thread", description=f"for post **{name}**")
        return None

    # Online notif
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Rewritten bot online as {self.bot.user}")
        await self.log(title="Archiver Bot Online", message="", colour=discord.Color.green())

    # Send chunked messages
    async def send_chunked_messages(self, channel: discord.TextChannel, header: str, items, id_list):
        if not items:
            return
        message_content = header + "\n"
        for item in items:
            if len(message_content) + len(item) + 2 > DISCORD_CHAR_LIMIT:
                sent_message  = await channel.send(message_content)
                id_list.append(sent_message.id)
                message_content = ""
            message_content += item + "\n"
        if len(message_content) > 2:
            sent_message = await channel.send(message_content)
            id_list.append(sent_message.id)

    # Generate difflib messages
    def get_diff_block(self, old_text, new_text):
        if old_text == new_text: return None

        diff = difflib.unified_diff(
            str(old_text or "").splitlines(), 
            str(new_text or "").splitlines(), 
            n=1, 
            lineterm=''
        )
        
        lines = list(diff)[2:]
        ansi_lines = []
        current_len = 0
        
        for line in lines:
            if line.startswith('+'):
                formatted = f"\u001b[0;32m{line}\u001b[0m"
            elif line.startswith('-'):
                formatted = f"\u001b[0;31m{line}\u001b[0m"
            elif line.startswith('@@'):
                formatted = f"\u001b[0;34m{line}\u001b[0m"
            else:
                formatted = line
                
            if current_len + len(formatted) > 950:
                ansi_lines.append("\u001b[0;33m... [Truncated for length]\u001b[0m")
                break
                
            ansi_lines.append(formatted)
            current_len += len(formatted) + 1

        return "\n".join(ansi_lines)
    
    # Restart command
    @app_commands.command(name="restart", description="Restarts and updates the bot")
    @app_commands.describe(do_update="If it should restart without updating (True = update, False = no update)")
    @app_commands.checks.has_role(MODERATOR_ID)
    async def restart(self, interaction: discord.Interaction, do_update:bool=True):
        await interaction.response.defer()
        if do_update:
            await interaction.followup.send(embed = discord.Embed(title="Updating...", colour=discord.Colour.yellow()))

            process = await asyncio.create_subprocess_exec(
                "git", "pull", "origin", "main",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return await interaction.followup.send(embed= discord.Embed(title=f"Update failed", description=f"{stderr.decode().strip()}", color=discord.Color.red()))
            await interaction.followup.send(embed= discord.Embed(title=f"Update successful", description=f"{stdout.decode().strip()}", color=discord.Color.green()))

        else:
            await interaction.followup.send(embed=discord.Embed(title="Restarting...", colour=discord.Colour.yellow()))
        executable = sys.executable
        args = [executable] + sys.argv
        os.execv(executable, args)
    
    # Other archives embed
    @app_commands.command(name="servers", description="Sends the list of other archive servers in a neat embed")
    @app_commands.checks.has_role(MODERATOR_ID)
    async def archives_embed(self, interaction: discord.Interaction):
        archives_embed = discord.Embed(title="Other Archive Servers", color=discord.Color.light_embed(), description=OTHER_ARCHIVES)
        await interaction.channel.send(embed=archives_embed)
        await interaction.response.send_message("Embed sent!", ephemeral=True)

    # Help command
    @app_commands.command(name="help", description="sends a list of commands that Archiver Bot provides")
    @app_commands.checks.has_any_role(*HIGHER_ROLES, HELPER_ID)
    async def help(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(description=COMMANDS_LIST), ephemeral=True)

    # Fetch links command
    @app_commands.command(name="fetch_links", description="Return a list of links to the attachments of a message")
    @app_commands.describe(message_id="The message with the attachments")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def fetch_links(self, interaction: discord.Interaction, message_id: str):
        try: 
            message = await interaction.channel.fetch_message(int(message_id))
            if message.attachments:
                links = []
                for attachment in message.attachments:
                    url = attachment.url
                    index = url.find('?')
                    if index != -1:
                        url = url[:index]
                    links.append(f"- <{url}>")
                links_message = "\n".join(links)              
                await interaction.response.send_message(content=f"The links to the message attachments:\n{links_message}", ephemeral=True)
            else:
                await interaction.response.send_message(content="The selected message has no attachments", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error while running the command: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))