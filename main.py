import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os 
import asyncio

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

async def setup_hook():
    print("Syncing slash commands...")
    await bot.tree.sync()
    print("Commands synced!")

bot.setup_hook = setup_hook

async def main():
    async with bot:
        await load()
        await bot.start(TOKEN)

async def global_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message(content="Sorry, you don't have the required role to use this command", ephemeral=True)
    else:
        await interaction.response.send_message(content=f"An error occured: {error}", ephemeral=True)
        utility_cog = interaction.client.get_cog("Utility")
        if utility_cog:
            await utility_cog.log(title="An error occured", message=f"for command {interaction.command.name} run by {interaction.user.mention}: {error}", colour=discord.Color.red())

bot.tree.on_error = global_app_command_error

asyncio.run(main())