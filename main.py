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
        ping_message = await discussion_thread_channel.send("ping pong")
        await ping_message.edit(content="<@&1162049503503863808> boop")
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread_channel.jump_url}")
        await asyncio.gather(
            notif.add_reaction("❌"),
            notif.add_reaction("🔴"),
            notif.add_reaction("🟢"),
            notif.add_reaction("✅")
        )
   
# Other archives embed
@bot.tree.command(name="servers", description="Sends the list of other archive servers in a neat embed")
@app_commands.checks.has_role(MODERATOR_ID)
async def archives_embed(interaction: discord.Interaction):
    archives_embed = discord.Embed(title="Other Archive Servers", color=discord.Color.light_embed())
    archives_embed.add_field(name="<:std:1399677131004580051> [**Storage Tech**](https://discord.gg/JufJ6uf)", value="Item sorting and storage", inline=False)
    archives_embed.add_field(name="<:slime:1399677082472153098> [**Slimestone Tech Archive**](https://discord.gg/QQX5RBaHzK)", value="Flying machines and movable contraptions", inline=False)
    archives_embed.add_field(name="<:mtdr:1399677041946923061> [**Minecraft Tech Discord Recollector**](https://discord.gg/UT8ns46As9)", value="Index of TMC SMP and archive servers", inline=False)
    archives_embed.add_field(name="<:tnt:1399677165104009226> [**TNT Archive**](https://discord.gg/vPyUBcdmZV)", value="TNT cannon tech and projectile physics", inline=False)
    archives_embed.add_field(name="<:tree:1399677175803805696> [**Tree Huggers**](https://discord.gg/8bUbuuS)", value="Tree farm development", inline=False)
    archives_embed.add_field(name="<:hfh:1399677019767312404> [**Huge Fungi Huggers**](https://discord.gg/EKKkyfcPPV)", value="Nether tree and foliage farm development", inline=False)
    archives_embed.add_field(name="<:cart:1399676987928219739> [**Cartchives**](https://discord.gg/8nGNTewveC)", value="Piston bolts and minecart based tech", inline=False)
    archives_embed.add_field(name="<:wither:1399677185870008330> [**Wither Archive**](https://discord.gg/Ea28MyKB3J)", value="Wither tech archive and development ", inline=False)
    archives_embed.add_field(name="<:sos:1399677094169940139> [**Saints of Suppression**](https://discord.gg/xa7QWAeAng)", value="Light and update suppression and skipping", inline=False)
    archives_embed.add_field(name="<:aca:1399676962464600155> [**Autocrafting Archive**](https://discord.gg/guZdbQ9KQe)", value="Crafters and modded autocrafting table tech", inline=False)
    archives_embed.add_field(name="<:comp:1399677007406698516> [**Computational Minecraft Archive**](https://discord.gg/jSe4jR5Kx7)", value="TMC-oriented computational redstone logic", inline=False)
    archives_embed.add_field(name="<:tmcra:1399677154702135328> [**TMC Resources Archive**](https://discord.gg/E4q8WDUc7k)", value="Compilation of TMC tricks, links, and resources", inline=False)
    archives_embed.add_field(name="<:luke:1399677029707808768> [**Luke's Video Archive**](https://discord.gg/KTDacw6JYk)", value="Chinese (BiliBiili) tech recollector", inline=False)
    archives_embed.add_field(name="<:ore:1399677056584781946> [**Open Redstone**](https://discord.gg/zjWRarN)", value="(DiscOREd) Computational redstone community", inline=False)
    archives_embed.add_field(name="<:squid:1399677105033183232> [**Piston Door Catalogue**](https://discord.gg/Khj8MyA)", value="(Redstone Squid's Records Catalogue) Piston door index", inline=False)
    archives_embed.add_field(name="<:ssf:1399677117884534875> [**Structureless Superflat Archive**](https://discord.gg/96Qm6e2AVH)", value="(SSf Archive) Structureless superflat tech", inline=False)
    archives_embed.add_field(name="<:rta:1399677071919288342> [**Russian Technical Minecraft Catalogue**](https://discord.com/invite/bMZYHnXnCA)", value="(RTMC Каталог) Russian TMC archive", inline=False)
    archives_embed.add_field(name="<:tba:1399677142660546620> [**Technical Bedrock Archive**](https://discord.com/invite/technical-bedrock-archive-715182000440475648)", value="Bedrock TMC archive", inline=False)
    await interaction.channel.send(embed=archives_embed)

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