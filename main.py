import discord
import os
import asyncio
import sys
import constants
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from sys import executable

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Edit tag button
class TagButton(discord.ui.Button):
    def __init__(self, tag, style):
        super().__init__(label = tag.name, style = style)
        self.tag = tag

    async def callback(self, interaction: discord.Interaction):
        new_tags = [self.tag]
        if self.view.forum_id in FORUMS:
            if not self.tag.name in UPPER_TAGS:
                for tag in interaction.channel.applied_tags:
                    if tag.name in UPPER_TAGS:
                        new_tags.append(tag)

        await interaction.channel.edit(applied_tags = new_tags)
        await self.view.on_timeout()

# Edit tag view
class TagView(discord.ui.View):
    def __init__(self, tag_list: list, forum_id:int):
        super().__init__(timeout = 10)
        self.forum_id = forum_id
        self.msg = None
        for tag in tag_list:
            self.add_item(TagButton(tag, discord.ButtonStyle.primary))

    async def set_message(self, msg):
        self.msg = msg

    async def on_timeout(self):
        if self.msg:
            try:
                await self.msg.delete()
            except discord.NotFound:
                pass

# Close resolved posts command
@bot.tree.command(name="close_resolved", description="Closes all solved, rejected and archived posts")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def close_resolved(interaction: discord.Interaction):

    await interaction.response.defer()

    guild = interaction.guild
    closed_posts = 0
    post_list = []
    tags = {'solved', 'rejected', 'archived'}

    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel):
            for thread in channel.threads:
                if thread.archived or thread.locked:
                    continue
                if any(tag.name.lower() in tags for tag in thread.applied_tags):
                    try:
                        await thread.edit(archived=True)
                        closed_posts += 1
                        post_list.append(f"*<#{thread.id}>* in <#{channel.id}>")
                    except discord.Forbidden:
                        await interaction.followup.send(f"Error: Bot does not have manage threads permission in <#{channel.id}>")
                        break
        
    if closed_posts > 0:
        report = f"### Successfully closed {closed_posts} forum post(s):\n"
        report += "\n".join(post_list)
        if len(report) > 1000:
            report = report[:1000] + " . . ."
        await interaction.followup.send(report)
    else:
        await interaction.followup.send("No open forum posts found that were marked as solved/archived/rejected")

# Close archived posts command
@bot.tree.command(name="close_archived", description="Closes all posts in the archive")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def close_archived(interaction: discord.Interaction):

    await interaction.response.defer()

    guild = interaction.guild
    closed_posts = 0
    post_list = []
    
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel) and (channel.category_id not in NON_ARCHIVE_CATEGORIES):
            for thread in channel.threads:
                if thread.archived or thread.locked:
                    continue
                try:
                    await thread.edit(archived=True)
                    closed_posts += 1
                    post_list.append(f"*<#{thread.id}>* in <#{channel.id}>")
                except discord.Forbidden:
                    await interaction.followup.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{channel.id}>")
                    continue
        
    if closed_posts > 0:
        report = f"### Successfully closed {closed_posts} forum post(s):\n"
        report += "\n".join(post_list)
        if len(report) > 1000:
            report = report[:1000] + " . . ."
        await interaction.followup.send(report)
    else:
        await interaction.followup.send("No open forum posts found in the archives")

#Set tag command
@bot.tree.command(name="set_tag", description="Sets the tag for the thread")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def set_tag(interaction: discord.Interaction):
    if not isinstance(interaction.channel.parent, discord.ForumChannel):
        await interaction.response.send_message(embed = discord.Embed(title = "This is not a forum channel"), ephemeral = True)
    view = TagView(interaction.channel.parent.available_tags, interaction.channel.parent.id)
    msg = await interaction.response.send_message("**Which tag would you like to set?**", view = view, ephemeral = True)
    await view.set_message(msg)

# Update tracker list
async def update_tracker_list():
    pending_messages = []
    awaiting_testing = []
    tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
    logs = bot.get_channel(LOG_CHANNEL)
    try:
        async for tracking_message in tracker_channel.history(limit=None):
            if CLOCK_EMOJI in tracking_message.content or TESTING_EMOJI in tracking_message.content:
                try:
                    await tracking_message.delete()
                except:
                    await logs.send(embed=discord.Embed(title="Could not delete the previous tracker list"))
                continue
            if CROSS_EMOJI in tracking_message.content:
                continue
            reactions = tracking_message.reactions
            if any(TESTING_EMOJI == reaction.emoji for reaction in reactions):
                awaiting_testing.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")
            else:
                if tracking_message.content == "":
                    continue
                pending_messages.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")
    except:
        await logs.send(embed=discord.Embed(title="Could not fetch messages in tracker channel"))

    if len(pending_messages) + len(awaiting_testing) > 0:
        pending_messages.reverse()
        awaiting_testing.reverse()
        pending_list = f"## 🕥 Pending Decision\n "
        pending_list += "\n ".join(pending_messages)
        await tracker_channel.send(pending_list)
        awaiting_list = f"## 🧪 Awaiting Testing\n "
        awaiting_list += "\n ".join(awaiting_testing)
        await tracker_channel.send(awaiting_list)
    else:
        await logs.send(embed=discord.Embed(title="No posts found in tracker channel"))

# Submission tracker
@bot.event
async def on_thread_create(thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL:
        # Logging
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title=f"Submission created: {thread.name}")
        await logs.send(embed=embed)
        # Send to tracker
        tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        discussion_thread = await tracker_channel.create_thread(name=thread.name)
        await discussion_thread.send(f"For discussion and debate regarding the archival staus of {thread.jump_url}")
        ping_message = await discussion_thread.send("ping")
        await ping_message.edit(content="<@&1162049503503863808> 🏓 chat away!")
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread.jump_url}")
        await asyncio.gather(
            notif.add_reaction("❌"),
            notif.add_reaction("🔴"),
            notif.add_reaction("🟢"),
            notif.add_reaction("✅")
        )
        # Resend tracker list
        await update_tracker_list()

# Tracker list command
@bot.tree.command(name="tracker_list", description="rechecks and resends the submission tracker list")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def tracker_list(interaction: discord.Interaction):
    await interaction.response.defer()
    await update_tracker_list()
    await interaction.delete_original_response()

# Remove tracker post on archival/reject and update notifs
@bot.event
async def on_thread_update(before, after):
    if before.parent.id in FORUMS:
        try:
            tag_before = set(before.applied_tags)
            tag_after = set(after.applied_tags)
            tag_added = list(tag_after - tag_before)[0]
        except:
            return
        if tag_added:
            tag_emote = str(tag_added.emoji).strip("_")
            tag_name = str(tag_added)

            # Pick the embed colour
            embed_colour = TAG_COLOUR.get(tag_name, None)
            if embed_colour is None:
                embed_colour = discord.Colour.light_gray()
            await after.send(embed = discord.Embed(title = f"Marked as {tag_emote} {tag_name}", color = embed_colour))
            # Close posts if resolved
            if tag_added.id in GENERAL_RESOLVED_TAGS:
                await after.edit(archived=True)

        # Remove the tracker channel message
        if tag_added.id in RESOLVED_TAGS:
            tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
            async for message in tracker_channel.history(limit=None):
                if str(before.id) in message.content:
                    logs = bot.get_channel(LOG_CHANNEL)
                    try:
                        await logs.send(f"Attempting to delete tracker message for submission id {before.id}, found message {message.id}")
                        await message.delete()
                        embed = discord.Embed(title=f"Submission tracker post of **{before.name}** removed")
                        await logs.send(embed=embed)
                    except Exception as e:
                        embed = discord.Embed(title=f"An error occured {e}")
                        await logs.send(embed=embed)
                    # Update tracker list
                    await update_tracker_list()
                    break                    

# Other archives embed
@bot.tree.command(name="servers", description="Sends the list of other archive servers in a neat embed")
@app_commands.checks.has_role(MODERATOR_ID)
async def archives_embed(interaction: discord.Interaction):
    archives_embed = discord.Embed(title="Other Archive Servers", color=discord.Color.light_embed(), description=
'''<:std:1399677131004580051> [**Storage Tech**](https://discord.gg/JufJ6uf) Item sorting and storage
<:slime:1399677082472153098> [**Slimestone Tech Archive**](https://discord.gg/QQX5RBaHzK) Flying machines and movable contraptions
<:mtdr:1399677041946923061> [**Minecraft Tech Discord Recollector**](https://discord.gg/UT8ns46As9) Index of TMC SMP and archive servers
<:tnt:1399677165104009226> [**TNT Archive**](https://discord.gg/vPyUBcdmZV) TNT cannon tech and projectile physics
<:tree:1399677175803805696> [**Tree Huggers**](https://discord.gg/8bUbuuS) Tree farm development
<:hfh:1399677019767312404> [**Huge Fungi Huggers**](https://discord.gg/EKKkyfcPPV) Nether tree and foliage farm development
<:cart:1399676987928219739> [**Cartchives**](https://discord.gg/8nGNTewveC) Piston bolts and minecart based tech
<:wither:1399677185870008330> [**Wither Archive**](https://discord.gg/Ea28MyKB3J) Wither tech archive and development 
<:sos:1399677094169940139> [**Saints of Suppression**](https://discord.gg/xa7QWAeAng) Light and update suppression and skipping
<:aca:1399676962464600155> [**Autocrafting Archive**](https://discord.gg/guZdbQ9KQe) Crafters and modded autocrafting table tech
<:comp:1399677007406698516> [**Computational Minecraft Archive**](https://discord.gg/jSe4jR5Kx7) TMC-oriented computational redstone logic
<:tmcra:1399677154702135328> [**TMC Resources Archive**](https://discord.gg/E4q8WDUc7k) Compilation of TMC tricks, links, and resources
<:luke:1399677029707808768> [**Luke's Video Archive**](https://discord.gg/KTDacw6JYk) Chinese (BiliBiili) tech recollector

<:ore:1399677056584781946> [**Open Redstone**](https://discord.gg/zjWRarN) (DiscOREd) Computational redstone community
<:squid:1399677105033183232> [**Piston Door Catalogue**](https://discord.gg/Khj8MyA) (Redstone Squid's Records Catalogue) Piston door index
<:ssf:1399677117884534875> [**Structureless Superflat Archive**](https://discord.gg/96Qm6e2AVH) (SSf Archive) Structureless superflat tech
<:rta:1399677071919288342> [**Russian Technical Minecraft Catalogue**](https://discord.com/invite/bMZYHnXnCA) (RTMC Каталог) Russian TMC archive
<:tba:1399677142660546620> [**Technical Bedrock Archive**](https://discord.com/invite/technical-bedrock-archive-715182000440475648) Bedrock TMC archive''')
    await interaction.channel.send(embed=archives_embed)
    await interaction.response.send_message("Embed sent!", ephemeral=True)

# Slash command error
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: commands.CommandInvokeError):
    if isinstance(error, commands.MissingRole) or isinstance(error, commands.MissingAnyRole):
        await interaction.followup.send(
            "You don't have the necessary roles to use this command",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"An error occurred while trying to execute this command: {error}",
            ephemeral=True
        )

# Restarts the bot and updates code from git if specified.
@bot.tree.command(name="restart", description="Restarts and updates the bot")
@app_commands.describe(do_update="If it should restart without updating (True = update, False = no update)")
@app_commands.checks.has_role(1161821342514036776)
async def restart(interaction: discord.Interaction, do_update:bool=True):
    await interaction.response.defer()
    if do_update:
        await interaction.followup.send(embed = discord.Embed(title="Updating...", colour=discord.Colour.random()))

        process = await asyncio.create_subprocess_exec(
            "git", "pull", "origin", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return await interaction.followup.send(embed= discord.Embed(title=f"Update failed: {stderr.decode().strip()}", color=discord.Color.red()))
        await interaction.followup.send(embed= discord.Embed(title=f'Update successful: {stdout.decode().strip()}', color=discord.Color.green()))

    else:
        await interaction.followup.send(embed=discord.Embed(title="Restarting...", colour=discord.Colour.random()))
    executable = sys.executable
    args = [executable] + sys.argv
    os.execv(executable, args)

# Ping reply
@bot.event
async def on_message(message):
    #Ignore own messages
    if message.author == bot.user:
        return
    # Reply to pings
    if bot.user in message.mentions:
        await message.channel.send(f'{message.author.mention} 🏓')
    await bot.process_commands(message)

# Startup
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    online_notif = discord.Embed(color=discord.Color.green(), title="Archiver Bot Online")
    LOG_OUTPUT = await bot.fetch_channel(LOG_CHANNEL)
    await LOG_OUTPUT.send(embed=online_notif)
    await bot.tree.sync()

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# Running
if __name__ == "__main__":
    bot.run(TOKEN)
