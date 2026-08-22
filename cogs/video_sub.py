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
        self.desc = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.link)
        self.add_item(self.desc)
        self.bot = bot
    async def on_submit(self, interaction: discord.Interaction):
        if "?v=" in self.link.value:
            clean_link = self.link.value.split("&")[0]
        else:
            clean_link = self.link.value.split("?")[0]
        if any(site in clean_link for site in ACCEPTABLE_SITES):
            # Change bilibili embeds
            if "www.bilibili.com" in clean_link:
                parts = clean_link.split("www.")
                clean_link = parts[0]+"www.vx"+parts[1]
                parts = clean_link.split(".com/")
                clean_link = parts[0]+".com/en/"+parts[1]
            # Send to review
            review_channel = self.bot.get_channel(REVIEW_CHANNEL)
            approve_or_deny = ApproveOrDeny(bot=self.bot)
            message = f"{interaction.user.mention} submitted: {clean_link}\nDescription: {self.desc.value if self.desc else 'None'}"
            await review_channel.send(content=message, view=approve_or_deny, allowed_mentions=discord.AllowedMentions.none())
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
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_video")
        self.deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_video")

        self.approve_button.callback = self.approve
        self.deny_button.callback = self.deny

        self.add_item(self.approve_button)
        self.add_item(self.deny_button)

    def _get_link_from_message(self, message_content: str):
        try:
            return message_content.split("submitted: ")[1].split("\n")[0]
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
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Video approved", message=f"{interaction.user.mention} approved the video link {new_video.jump_url}", colour=discord.Color.green())
        # Send new submission prompt
        await video_channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.", color=discord.Color.yellow()), view=submit_prompt)
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
        await interaction.channel.send(embed=discord.Embed(title="Welcome to Video Showcase!", description="This is a channel for sharing technical Minecraft videos with the community.\nClick the button below to submit a video for review.\nAll submissions must be TMC-related.",  color=discord.Color.yellow()), view=submit_prompt)

async def setup(bot: commands.Bot):
    bot.add_view(SubmitPrompt(bot))
    bot.add_view(ApproveOrDeny(bot))
    
    await bot.add_cog(VideoSub(bot))