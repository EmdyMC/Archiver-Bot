import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os 
import asyncio

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")

        print("Syncing slash commands...")
        await self.tree.sync()
        print("Commands synced!")

bot = MyBot()

@bot.tree.error
async def global_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message(content="Sorry, you don't have the required role to use this command", ephemeral=True)
    else:
        try:
            await interaction.response.send_message(content=f"An error occured: {error}", ephemeral=True)
        except:
            await interaction.followup.send(content=f"An error occured: {error}", ephemeral=True)
        utility_cog = interaction.client.get_cog("Utility")
        if utility_cog:
            await utility_cog.log(title="An error occured", message=f"for command {interaction.command.name} run by {interaction.user.mention}: {error}", colour=discord.Color.red())

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())