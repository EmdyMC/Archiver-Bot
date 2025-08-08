import discord
from commands import *
from dotenv import load_dotenv               

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
