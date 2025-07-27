import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.none()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

HIGHER_ROLES = {1161821342514036776, 1162049503503863808}
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

#Submission tracker
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
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread_channel.jump_url}")
        await notif.add_reaction("❌")
        await notif.add_reaction("🔴")
        await notif.add_reaction("🟢")
        await notif.add_reaction("✅")

#Slash command error
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

# STARTUP
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    online_notif = discord.Embed(color=discord.Color.green(), title="Archiver Bot Online")
    LOG_OUTPUT = await bot.fetch_channel(LOG_CHANNEL)
    await LOG_OUTPUT.send(embed=online_notif)
    await bot.tree.sync()

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
bot.run(TOKEN)