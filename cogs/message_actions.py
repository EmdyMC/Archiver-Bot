import discord
import aiofiles
import json
import random
from discord.ext import commands
from discord import app_commands
from constants import BLACKLIST, BOT_DM_THREAD, RANDOM_REPLIES, SNAPSHOT_CHANNEL, NO_CHAT, STAFF_ROLES, TIMEOUT_MESSAGE, SUBMISSIONS_CHANNEL, NO_CHAT_IMAGE, LOG_CHANNEL, SUBMISSION_PROMPT, HOW_TO_PIN, HELP_FORUM, HELP_FORUM_PROMPT

# Reply modal
class ReplyBox(discord.ui.Modal, title="Reply to DM"):
    def __init__(self, DM: discord.Message):
        super().__init__()
        self.message = discord.ui.TextInput(
            label="Message content:",
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.message)
        self.DM = DM
    async def on_submit(self, interaction: discord.Interaction):
        await self.DM.channel.send(self.message.value)
        await interaction.response.send_message(embed=discord.Embed(title="DM Sent", description=f"**{interaction.user.mention} sent the following message to {self.DM.author.name} {self.DM.author.mention} in DMs:**\n{self.message.value}"))

class ReplyButton(discord.ui.View):
    def __init__(self, DM: discord.Message):
        super().__init__(timeout=86400)
        self.DM = DM
        self.reply_button = discord.ui.Button(label="Reply", style=discord.ButtonStyle.blurple, custom_id="reply")
        self.reply_button.callback = self.reply
        self.add_item(self.reply_button)
        self.delete_button = discord.ui.Button(label="Delete", style=discord.ButtonStyle.red, custom_id="delete")
        self.delete_button.callback = self.delete
        self.add_item(self.delete_button)
        self.block_button = discord.ui.Button(label="Block", style=discord.ButtonStyle.red, custom_id="block")
        self.block_button.callback = self.block
        self.add_item(self.block_button)
    async def reply(self, interaction:discord.Interaction):
        await interaction.response.send_modal(ReplyBox(DM=self.DM))
    async def delete(self, interaction:discord.Interaction):
        await interaction.message.delete()
    async def block(self, interaction:discord.Interaction):
        async with aiofiles.open(BLACKLIST, mode='r+') as f:
            content = await f.read()
            users = json.loads(content) if content else []
            if self.DM.author.id not in users:
                users.append(self.DM.author.id)
                # Rewrite the file
                await f.seek(0)
                await f.truncate()
                await f.write(json.dumps(users, indent=4))
                await interaction.response.send_message(embed=discord.Embed(title="User Blocked", description=f"{self.DM.author.name} {self.DM.author.mention} added to blacklist"))
            else:
                await interaction.response.send_message(embed=discord.Embed(title="User Already Blocked", description=f"{self.DM.author.name} {self.DM.author.mention} already in blacklist"))

class MessageActions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    # DM forwarding
    async def forwardDM(self, message: discord.Message):
        async with aiofiles.open(BLACKLIST, mode='r') as f:
                content = await f.read()
                users = json.loads(content) if content else []
                # Blacklist check
                if message.author.id not in users:
                    try:
                        helper_thread = await self.bot.fetch_channel(BOT_DM_THREAD)
                        reply_view = ReplyButton(DM=message)
                        forward = discord.Embed(title="DM received", description=f"From user: {message.author.name} {message.author.mention}\nContent: {message.content}", color=discord.Color.dark_gold())
                        forward.set_thumbnail(url=message.author.display_avatar.url)
                        attachments = []
                        for attachment in message.attachments:
                            attachments.append(await attachment.to_file())
                        if message.attachments:
                            forward.description = f"From user: {message.author.name} {message.author.mention}\nContent: {message.content}\nAttachment:"
                        await helper_thread.send(embed=forward, files=attachments, view=reply_view)
                    except Exception as e:
                        utility_cog = self.bot.get_cog("Utility")
                        await utility_cog.log(title="Error forwarding DM", message=f"{e}")

    # Pin snapshot messages
    async def pin_snapshot_messages(self, message: discord.Message):
        utility_cog = self.bot.get_cog("Utility")
        try:
            pinned_messages = await message.channel.pins(limit=5)
            if pinned_messages:
                await pinned_messages[-1].unpin()
                await utility_cog.log(title="Old pinned message removed", message=f"In: {message.channel.name}")
            await message.pin()
            await utility_cog.log(title="Snapshot update message pinned", message=f"In: {message.channel.name}")
        except Exception as e:
            await utility_cog.log(title="An error occurred", message=f"{e}")

    # No chat notifier
    async def handle_no_chat_users(self, message: discord.Message):
        attachments = []
        utility_cog = self.bot.get_cog("Utility")
        try:
            for attachment in message.attachments:
                attachments.append(await attachment.to_file())
            message_content = message.content
            jump_url = message.channel.jump_url
            author = message.author
            await message.delete()
            await utility_cog.timeout_user(seconds=20, user=author)
            warn_embed=discord.Embed(
                title="Message blocked", 
                description=f"{message.author.mention}{TIMEOUT_MESSAGE}"
            )
            warn_embed.set_image(url=NO_CHAT_IMAGE)
            try:
                await message.author.send(embed=warn_embed)
                await message.channel.send(embed=warn_embed, delete_after=20)
                dm_status = "Notified via DM and in channel"
            except discord.Forbidden:
                await message.channel.send(embed=warn_embed, delete_after=20)
                dm_status = "DMs closed, notified in-channel"
            log_embed = discord.Embed(title="No chat user caught", 
            description=f"User {author.mention} tried to send a message in {jump_url} but has the no chat role. {dm_status}.\nContent: {message_content}", colour=discord.Color.red())
            logs = self.bot.get_channel(LOG_CHANNEL)
            await logs.send(embed=log_embed, files=attachments)
        except Exception as e:
            await utility_cog.log(title="Error in no-chat filter", message=f"{e}", colour=discord.Color.red())

    # First submission post message handling
    async def submission_post_prompt(self, message: discord.Message):
        utility_cog = self.bot.get_cog("Utility")
        try:
            await message.pin()
            embed = discord.Embed(
                title="Thank you for your submission!",
                description=SUBMISSION_PROMPT
            )
            embed.set_image(url=HOW_TO_PIN)
            await message.channel.send(embed=embed)
            await utility_cog.log(title=f"Message pinned", message=f"In: {message.channel.jump_url}")
        except Exception as e:
            await utility_cog.log(title=f"An error occurred", message=f"{e}")

    # Help forum prompt handling
    async def help_forum_prompt(self, message: discord.Message):
        utility_cog = self.bot.get_cog("Utility")
        try:
            await message.pin()
            embed = discord.Embed(
                title="Thank you for submitting your question!",
                description=HELP_FORUM_PROMPT
            )
            await message.channel.send(embed=embed)
            await utility_cog.log(title=f"Message pinned", message=f"In: {message.channel.jump_url}")
        except Exception as e:
            await utility_cog.log(title=f"An error occurred", message=f"{e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore own messages
        if message.author == self.bot.user:
            return
        # Forward DMs
        if isinstance(message.channel, discord.DMChannel):
            await self.forwardDM(message)
        # Pin snapshot updates
        if message.flags.is_crossposted and message.channel.id == SNAPSHOT_CHANNEL:
            await self.pin_snapshot_messages(message)
        # Reply to pings
        if self.bot.user in message.mentions:
            random_message = random.choice(RANDOM_REPLIES)
            await message.reply(content=random_message, mention_author=False)
        # Catch images sent by no chat users
        if message.author.get_role(NO_CHAT) and not any(role.id in STAFF_ROLES for role in message.author.roles):
            await self.handle_no_chat_users(message)
        # Pin first message in submission posts and send info message
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUBMISSIONS_CHANNEL:
            if message.id == message.channel.id:
                await self.submission_post_prompt(message)
        # Pin first message in help forum and send info message
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == HELP_FORUM:
            if message.id == message.channel.id:
                await self.help_forum_prompt(message)
        await self.bot.process_commands(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageActions(bot))