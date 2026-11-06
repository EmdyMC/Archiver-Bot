from constants import VIDEO_CHANNEL, REVIEW_CHANNEL, HIGHER_ROLES, ACCEPTABLE_SITES
from urllib.parse import urlparse, parse_qs
from discord.ext import commands
from discord import app_commands
import discord, re

YT_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
BILI_HOSTS = frozenset({"bilibili.com", "www.bilibili.com", "m.bilibili.com", "vxbilibili.com", "www.vxbilibili.com"})
YT_ID = re.compile(r"^[\w-]{11}$")
BILI_ID = re.compile(r"/video/(BV[0-9A-Za-z]+|av\d+)")
YOUTUBE_LINK = "https://www.youtube.com/watch?v={}"
BILI_LINK = "https://www.vxbilibili.com/en/video/{}/"

def clean_video_link(raw_link: str) -> str|None:
    """Return a normalised link."""

    raw_link = raw_link.strip()
    url = urlparse(raw)
    host = (url.hostname or "").lower()
    query = parse_qs(url.query)
    segments = [s for s in url.path.split("/") if s]

    # YouTube
    video_id = None
    if host == "youtu.be" and segments:
        video_id = segments[0]
    elif host in YT_HOSTS:
        if url.path == "/watch":
            video_id = query.get("v", [None])[0]
        elif len(segments) >= 2 and segments[0] == "shorts":
            video_id = segments[1]
    if video_id and YT_ID.match(video_id):
        return YOUTUBE_LINK.format(video_id)

    # Bilibili
    if host in BILI_HOSTS:
        if m := BILI_ID.search(url.path):
            return BILI_LINK.format(m.group(1))

class Submit(discord.ui.Modal, title="Submit a video link"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.link = discord.ui.TextInput(
            label="Video link",
            style=discord.TextStyle.short,
            required=True
        )
        self.desc = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.link)
        self.add_item(self.desc)
        self.bot = bot
    async def on_submit(self, interaction: discord.Interaction):
        if clean_link := clean_video_link(self.link.value):
            # Send to review
            review_channel = self.bot.get_channel(REVIEW_CHANNEL)
            approve_or_deny = ApproveOrDeny(bot=self.bot)
            message = f"{interaction.user.mention} submitted: {clean_link}\nDescription: {self.desc.value if self.desc else 'None'}"
            await review_channel.send(content=message, view=approve_or_deny, allowed_mentions=discord.AllowedMentions.none())
            utility_cog = self.bot.get_cog("Utility")
            await utility_cog.log(title=f"Video submitted", message=f"{interaction.user.mention} submitted the video link {clean_link}", colour=discord.Color.yellow())
            await interaction.response.send_message(content="Video submitted!", ephemeral=True)
        else:
            await interaction.response.send_message(content="Invalid link entered, please send a youtube/bilibili video link", ephemeral=True)

class SubmitPrompt(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.submit_button = discord.ui.Button(label="Submit a video", style=discord.ButtonStyle.green, custom_id="submit")
        self.submit_button.callback = self.prompt

        self.add_item(self.submit_button)
        self.bot = bot
    async def prompt(self, interaction: discord.Interaction):
        await interaction.response.send_modal(Submit(self.bot))

class ApproveOrDeny(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_video")
        self.approve_with_desc_button = discord.ui.Button(label="Approve with description", style=discord.ButtonStyle.green, custom_id="approve_with_desc")
        self.deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_video")

        self.approve_button.callback = self.approve
        self.approve_with_desc_button.callback = self.approve_with_desc
        self.deny_button.callback = self.deny

        self.add_item(self.approve_button)
        self.add_item(self.approve_with_desc_button)
        self.add_item(self.deny_button)

    def _get_link_from_message(self, message_content: str):
        try:
            return message_content.split("submitted: ")[1].split("\n")[0]
        except IndexError:
            return ""

    def _get_desc_from_message(self, message_content: str):
        try:
            return message_content.split("Description: ")[1]
        except IndexError:
            return ""

    async def approve(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Remove old submission prompt
        link = self._get_link_from_message(interaction.message.content)
        video_channel = self.bot.get_channel(VIDEO_CHANNEL)
        submit_prompt = SubmitPrompt(self.bot)
        async for mess in video_channel.history(limit=1):
            await mess.delete()
        # Send and publish new video link
        new_video = await video_channel.send(link)
        await new_video.publish()
        await new_video.create_thread(name=new_video.embeds[0].title, auto_archive_duration=60)
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video approved", message=f"{interaction.user.mention} approved the video link {new_video.jump_url}", colour=discord.Color.green())
        # Send new submission prompt
        await video_channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.", color=discord.Color.green()), view=submit_prompt)
        # Remove review message
        await interaction.message.delete()

    async def approve_with_desc(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Remove old submission prompt
        link = self._get_link_from_message(interaction.message.content)
        desc = self._get_desc_from_message(interaction.message.content)
        video_channel = self.bot.get_channel(VIDEO_CHANNEL)
        submit_prompt = SubmitPrompt(self.bot)
        async for mess in video_channel.history(limit=1):
            await mess.delete()
        # Send and publish new video link
        new_video = await video_channel.send(f"{link}\n{desc}")
        await new_video.publish()
        await new_video.create_thread(name=new_video.embeds[0].title, auto_archive_duration=60)
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video approved", message=f"{interaction.user.mention} approved the video link {new_video.jump_url}", colour=discord.Color.green())
        # Send new submission prompt
        await video_channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.", color=discord.Color.green()), view=submit_prompt)
        # Remove review message
        await interaction.message.delete()
        
    async def deny(self, interaction: discord.Interaction):
        await interaction.response.defer()
        link = self._get_link_from_message(interaction.message.content)
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video denied", message=f"{interaction.user.mention} denied the video link {link}", colour=discord.Color.red())
        # Remove review message
        await interaction.message.delete()


class VideoSub(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="video_submit_prompt", description="Send the initial prompt for video submissions")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def send_submit_prompt(self, interaction: discord.Interaction):
        submit_prompt = SubmitPrompt(self.bot)
        # Reply to user to satisfy interaction
        await interaction.response.send_message("Done", ephemeral=True)
        # Send prompt in channel seperately
        await interaction.channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.",  color=discord.Color.green()), view=submit_prompt)

async def setup(bot: commands.Bot):
    bot.add_view(SubmitPrompt(bot))
    bot.add_view(ApproveOrDeny(bot))
    
    await bot.add_cog(VideoSub(bot))
