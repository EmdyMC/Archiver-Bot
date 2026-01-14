import discord
from commands import *
from dotenv import load_dotenv               

# Startup
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    online_notif = discord.Embed(color=discord.Color.green(), title="Archiver Bot Online")
    LOG_OUTPUT = await bot.fetch_channel(LOG_CHANNEL)
    await LOG_OUTPUT.send(embed=online_notif)
    await bot.tree.sync()
    if not archive_management.is_running():
        archive_management.start()

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# Running
if __name__ == "__main__":
    bot.run(TOKEN)
