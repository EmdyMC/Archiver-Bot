import discord
from discord.ext import commands
from discord import app_commands
from constants import VIDEO_CHANNEL, REVIEW_CHANNEL, HIGHER_ROLES, ACCEPTABLE_SITES

class Submit(discord.ui.Modal, title="Submit a video link"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.link = discord.ui.TextInput(
            label="Video link",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.link)
        self.bot = bot
    async def on_submit(self, interaction: discord.Interaction):
        if "?v=" in self.link.value:
            clean_link = self.link.value.split("&")[0]
        else:
            clean_link = self.link.value.split("?")[0]
        if any(site in clean_link for site in ACCEPTABLE_SITES):
            review_channel = self.bot.get_channel(REVIEW_CHANNEL)
            approve_or_deny = ApproveOrDeny(link=clean_link, bot=self.bot)
            await review_channel.send(content=clean_link, view=approve_or_deny)
            utility_cog = self.bot.get_cog("Utility")
            await utility_cog.log(title=f"Video submitted", message=f"{interaction.user.mention} submitted the video link {clean_link}", colour=discord.Color.yellow())
            await interaction.response.send_message(content="Video submitted!", ephemeral=True)
        else:
            await interaction.response.send_message(content="Invalid link entered, please send a youtube video link", ephemeral=True)

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
    def __init__(self, link: str, bot: commands.Bot):
        super().__init__(timeout=None)

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green)
        self.deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red)

        self.approve_button.callback = self.approve
        self.deny_button.callback = self.deny

        self.add_item(self.approve_button)
        self.add_item(self.deny_button)

        self.link = link
        self.bot = bot
    async def approve(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Remove old submission prompt
        video_channel = self.bot.get_channel(VIDEO_CHANNEL)
        submit_prompt = SubmitPrompt(self.bot)
        async for mess in video_channel.history(limit=1):
            await mess.delete()
        # Send and publish new video link
        new_video = await video_channel.send(self.link)
        await new_video.publish()
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video approved", message=f"{interaction.user.mention} approved the video link {new_video.jump_url}", colour=discord.Color.green())
        # Send new submission prompt
        await video_channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.", color=discord.Color.yellow()), view=submit_prompt)
        # Remove review message
        await interaction.message.delete()
    async def deny(self, interaction: discord.Interaction):
        await interaction.response.defer()
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video denied", message=f"{interaction.user.mention} denied the video link {self.link}", colour=discord.Color.red())
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
        await interaction.channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.",  color=discord.Color.yellow()), view=submit_prompt)

async def setup(bot: commands.Bot):
    await bot.add_cog(VideoSub(bot))