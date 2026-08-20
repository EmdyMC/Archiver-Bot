import discord
from discord.ext import commands
from discord import app_commands
from constants import VIDEO_CHANNEL, REVIEW_CHANNEL, HIGHER_ROLES

class Submit(discord.ui.Modal, title="Submit a video link"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.link = discord.ui.TextInput(
            label="Youtube video link",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.link)
        self.bot = bot
    async def on_submit(self, interaction: discord.Interaction):
        review_channel = self.bot.get_channel(REVIEW_CHANNEL)
        approve_or_deny = ApproveOrDeny(link=self.link.value, bot=self.bot)
        await review_channel.send(view=approve_or_deny)
        await interaction.response.send_message(content="Video submitted!", ephemeral=True)

class SubmitPrompt(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=86400)
        self.submit_button = discord.ui.Button(label="Submit a video", style=discord.ButtonStyle.green, custom_id="submit")
        self.submit_button.callback = self.prompt
        self.add_item(self.submit_button)
        self.bot = bot
    async def prompt(self, interaction: discord.Interaction):
        await interaction.response.send_modal(Submit(self.bot))

class ApproveOrDeny(discord.ui.View):
    def __init__(self, link: str, bot: commands.Bot):
        super().__init__(timeout=86400)
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
        review_channel = self.bot.get_channel(VIDEO_CHANNEL)
        await review_channel.send(self.link)
        submit_prompt = SubmitPrompt(self.bot)
        await review_channel.send(view=submit_prompt)
        await interaction.message.delete()
    async def deny(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()


class VideoSub(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="video_submit_prompt", description="Send the initial prompt for video submissions")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def send_submit_prompt(self, interaction: discord.Interaction):
        submit_prompt = SubmitPrompt(self.bot)
        await interaction.response.send_message(view=submit_prompt)


async def setup(bot: commands.Bot):
    await bot.add_cog(VideoSub(bot))