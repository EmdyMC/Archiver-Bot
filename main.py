import discord
import os
import asyncio
import sys
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from sys import executable

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
HIGHER_ROLES = {1161821342514036776, 1162049503503863808}
MODERATOR_ID = 1161821342514036776
LOG_CHANNEL = 1343664979831820368
NON_ARCHIVE_CATEGORIES = {1355756508394160229, 1358435852153258114, 1163087048173965402, 1378966923152195655, 1182932696662560798, 1374225342948053032, 1161803873317568583}
SUBMISSIONS_CHANNEL = 1161814713496256643
SUBMISSIONS_TRACKER_CHANNEL = 1394308822926889060
OTHER_ARCHIVES_CHANNEL = 1266791891710513222

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

# Submission tracker
@bot.event
async def on_thread_create(thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL:
        #terminal notif
        print(f"New submission {thread.name} created")
        #send to tracker
        tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        discussion_thread = await tracker_channel.create_thread(name=thread.name)
        discussion_thread_channel = bot.get_channel(discussion_thread.id)
        await discussion_thread_channel.send(f"For discussion and debate regarding the archival staus of {thread.jump_url}")
        #await archivers = bot.get_all_members()
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread_channel.jump_url}")
        await asyncio.gather(
            notif.add_reaction("❌"),
            notif.add_reaction("🔴"),
            notif.add_reaction("🟢"),
            notif.add_reaction("✅")
        )

"""     
# Other archives embed
@bot.tree.command(name="archive_embed", description="Sends the list of other archive servers in a neat embed")
@app_commands.checks.has_role(MODERATOR_ID)
async def archives_embed():
    archives_channel = bot.get_channel(OTHER_ARCHIVES_CHANNEL)
    archives_embed = discord.Embed(title="Other Archive Servers", color=discord.Color.light_embed(), description=
        '''<:pridetech:849361224319238174> [**Storage Tech**](https://discord.gg/JufJ6uf) Item sorting and storage
        <:slimestonetech:1397669158505807953> [**Slimestone Tech Archive**](https://discord.gg/QQX5RBaHzK) Flying machines and movable contraptions
        <:mtdr:977912177337962556> [**Minecraft Tech Discord Recollector**](https://discord.gg/UT8ns46As9) Index of TMC SMP and archive servers
        <:tntarchive:1397670149368053800> [**TNT Archive**](https://discord.gg/vPyUBcdmZV) TNT cannon tech and projectile physics
        <:treehuggers:1397670997355921448> [**Tree Huggers**](https://discord.gg/8bUbuuS) Tree farm development
        <:hugefungihuggers:1397672034300985434> [**Huge Fungi Huggers**](https://discord.gg/EKKkyfcPPV) Nether tree and foliage farm development
        <:cartchives:1397672526229803028> [**Cartchives**](https://discord.gg/8nGNTewveC) Piston bolts and minecart based tech
        <:witherhead:913636413503848478> [**Wither Archive**](https://discord.gg/Ea28MyKB3J) Wither tech archive and development 
        <:suppression:1397673704191692901> [**Saints of Suppression**](https://discord.gg/xa7QWAeAng) Light and update suppression and skipping
        <:aca:1397674339004055752> [**Autocrafting Archive**](https://discord.gg/guZdbQ9KQe) Crafters and modded autocrafting table tech
        <:comparchive:1397674846036430848> [**Computational Minecraft Archive**](https://discord.gg/jSe4jR5Kx7) TMC-oriented computational redstone logic
        <:tmcra:1397675452415606804> [**TMC Resources Archive**](https://discord.gg/E4q8WDUc7k) Compilation of TMC tricks, links, and resources
        <:lukearchive:1397675957933969509> [**Luke's Video Archive**](https://discord.gg/KTDacw6JYk) Chinese (BiliBiili) tech recollector

        <:ored:1397677889305968752> [**Open Redstone**](https://discord.gg/zjWRarN) (DiscOREd) Computational redstone community
        <:pistondoor:1397678277493264414> [**Piston Door Catalogue**](https://discord.gg/Khj8MyA) (Redstone Squid's Records Catalogue) Piston door index
        <:ssf:1397678984715833386> [**Structureless Superflat Archive**](https://discord.gg/96Qm6e2AVH) (SSf Archive) Structureless superflat tech
        <:rutmc:1305855498515386368> [**Russian Technical Minecraft Catalogue**](https://discord.com/invite/bMZYHnXnCA) (RTMC Каталог) Russian TMC archive
        <:tba:1397679666373988533> [**Technical Bedrock Archive**](https://discord.com/invite/technical-bedrock-archive-715182000440475648) Bedrock TMC archive')''')
    await archives_channel.send(embed=archives_embed)
"""

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
            "An error occurred while trying to execute this command.",
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
    if message.author == bot.user:
        return
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