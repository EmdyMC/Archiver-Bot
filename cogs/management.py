import discord
import asyncio
from discord.ext import tasks
from datetime import timedelta
from discord.utils import snowflake_time
from discord.ext import commands
from discord import app_commands
from constants import HIGHER_ROLES, HELP_FORUM, STAFF_ROLES, ALLOWED_FORUMS, NON_ARCHIVE_CATEGORIES, FORUMS, FAQ_CHANNEL, PENDING_TAGS, INACTIVE_TAG, UNSOLVED_TAG, SUBMISSIONS_CHANNEL, CLOSING_TAGS, LOG_CHANNEL
from cogs.utility import TagSelectView

class Management(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.archive_management.start()
        self.pin_ctx = app_commands.ContextMenu(name="Pin", callback=self.pin_message)
        self.bot.tree.add_command(self.pin_ctx)

    def cog_unload(self):
        self.bot.tree.remove_command(self.pin_ctx.name, type=self.pin_ctx.type)
        self.archive_management.cancel()
    
    # Open all archive threads
    async def open_all_archived(self, run_channel: discord.TextChannel):
        await run_channel.send("Running open archived loop")
        opened_posts = 0
        guild = run_channel.guild
        # Archive channels
        for channel in guild.channels:
            if isinstance(channel, discord.ForumChannel) and (channel.category_id not in NON_ARCHIVE_CATEGORIES):
                async for thread in channel.archived_threads(limit=None):
                    if thread.archived and not thread.flags.pinned:
                        try:
                            await thread.edit(archived=False)
                            opened_posts += 1
                            await asyncio.sleep(1)
                        except discord.Forbidden:
                            await run_channel.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{channel.id}>")
                            return
        faq_channel = self.bot.get_channel(FAQ_CHANNEL)
        # FAQ channel
        async for thread in faq_channel.archived_threads(limit=None):
            if thread.archived and not thread.flags.pinned:
                try:
                    await thread.edit(archived=False)
                    opened_posts += 1
                    await asyncio.sleep(1)
                except discord.Forbidden:
                    await run_channel.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{faq_channel.id}>")
                    return
        # Submissions, corrections, help
        for forum in FORUMS:
            channel = self.bot.get_channel(forum)
            async for thread in channel.archived_threads(limit=None):
                if thread.archived and any(tag.id in PENDING_TAGS for tag in thread.applied_tags) and not thread.flags.pinned:
                    try:
                        await thread.edit(archived=False)
                        opened_posts += 1
                        await asyncio.sleep(1)
                    except discord.Forbidden:
                        await run_channel.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{channel.id}>")
                        return

        if opened_posts > 0:
            report = f"**Successfully opened {opened_posts} forum post(s)**"
            await run_channel.send(content=report)
        else:
            await run_channel.send("No closed forum posts found in the archives")

    async def close_all_resolved(self, run_channel: discord.TextChannel):
        await run_channel.send("Running close resolved loop")
        guild = run_channel.guild
        closed_posts = 0
        post_list = []
        tags = {'solved', 'rejected', 'archived', 'inactive', 'off-topic'}

        for channel in guild.channels:
            if isinstance(channel, discord.ForumChannel):
                for thread in channel.threads:
                    if thread.archived or thread.flags.pinned:
                        continue
                    if thread.locked and not thread.archived:
                        await thread.edit(locked=False)
                        await thread.edit(archived=True, locked=True)
                        await asyncio.sleep(1)
                    if any(tag.name.lower() in tags for tag in thread.applied_tags):
                        try:
                            await thread.edit(archived=True)
                            closed_posts += 1
                            post_list.append(f"*<#{thread.id}>* in <#{channel.id}>")
                            await asyncio.sleep(1)
                        except discord.Forbidden:
                            await run_channel.send(f"Error: Bot does not have manage threads permission in <#{channel.id}>")
                            break
            
        if closed_posts > 0:
            report = f"### Successfully closed {closed_posts} forum post(s):\n"
            report += "\n".join(post_list)
            if len(report) > 1000:
                report = report[:1000] + " . . ."
            await run_channel.send(report)
        else:
            await run_channel.send("No open forum posts found that were marked as solved/archived/rejected")

    async def mark_inactive(self, run_channel: discord.TextChannel):
        await run_channel.send("Running mark inactive loop")
        help_forum = self.bot.get_channel(HELP_FORUM)
        now = discord.utils.utcnow()
        inactive_tag = help_forum.get_tag(INACTIVE_TAG)
        new_tags = []
        new_tags.append(inactive_tag)
        count = 0
        for thread in help_forum.threads:
            if not any(tag.id == UNSOLVED_TAG for tag in thread.applied_tags):
                continue
            if thread.last_message_id:
                last_activity = snowflake_time(thread.last_message_id)
            else:
                last_activity = thread.created_at
            elapsed_time = now - last_activity
            if elapsed_time > timedelta(weeks=1):
                await thread.edit(archived=True, applied_tags=new_tags)
                count += 1
                continue
            '''    
            if elapsed_time > timedelta(days=3):
                last_msg = thread.last_message
                if last_msg is None and thread.last_message_id is not None:
                    try:
                        last_msg = await thread.fetch_message(thread.last_message_id)
                    except discord.NotFound:
                        pass

                if last_msg and last_msg.author != bot.user:
                    await thread.send(content=f"{thread.owner.mention} was this help request solved?\nIf so please make sure to mark it as solved using `/tag_selector`")
            '''
        await run_channel.send(content=f"Marked **{count}** help threads as inactive")

    async def lock_submissions(self, run_channel: discord.TextChannel):
        await run_channel.send("Running lock submissions loop")
        submissions = self.bot.get_channel(SUBMISSIONS_CHANNEL)
        count = 0
        for thread in submissions.threads:
            if any(tag.id in CLOSING_TAGS for tag in thread.applied_tags) and not thread.locked:
                if thread.last_message_id:
                    last_activity = snowflake_time(thread.last_message_id)
                else:
                    last_activity = thread.created_at
                elapsed_time = discord.utils.utcnow() - last_activity
                if elapsed_time > timedelta(days=1):
                    await thread.edit(archived=False, locked=True)
                    await thread.edit(archived=True)
                    count += 1
        await run_channel.send(content=f"Locked {count} Rejected/Archived submissions posts")

    @tasks.loop(hours=12)
    async def archive_management(self):
        await self.bot.wait_until_ready()
        utility_cog = self.bot.get_cog("Utility")
        logs = self.bot.get_channel(LOG_CHANNEL)
        await utility_cog.log(title="Maintenence", message="Running periodic archive post open and resolved thread close commands", colour=discord.Color.green())
        await self.mark_inactive(run_channel=logs)
        await self.lock_submissions(run_channel=logs)
        await self.open_all_archived(run_channel=logs)
        await self.close_all_resolved(run_channel=logs)

    # Close resolved posts command
    @app_commands.command(name="close_resolved", description="Closes all solved, rejected and archived posts")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def close_resolved(self, interaction: discord.Interaction):
        await interaction.response.send_message(content="Checking posts. . .", ephemeral=True)
        await self.close_all_resolved(run_channel=interaction.channel)

    # Open archived posts command
    @app_commands.command(name="open_archived", description="Opens all posts in the archive")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def open_archived(self, interaction: discord.Interaction):
        await interaction.response.send_message(content="Checking posts. . .", ephemeral=True)
        await self.open_all_archived(run_channel=interaction.channel)

    # Tag selector command
    @app_commands.command(name="tag_selector", description="Edit the tags of a forum post")
    async def selector(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(embed = discord.Embed(title = "This is not a forum post"), ephemeral = True)
            return
        if not isinstance(interaction.channel.parent, discord.ForumChannel):
            await interaction.response.send_message(embed = discord.Embed(title = "This is not a thread in a forum channel"), ephemeral = True)
            return
        in_help_forum = interaction.channel.parent_id == HELP_FORUM
        has_higher_role = any(role.id in STAFF_ROLES for role in interaction.user.roles)
        if (not in_help_forum and not has_higher_role) or (in_help_forum and interaction.user.id != interaction.channel.owner_id and not has_higher_role):
            await interaction.response.send_message(embed = discord.Embed(title = "You do not have the permissions to run that command here"), ephemeral = True)
            return
        thread = interaction.channel
        available_tags = thread.parent.available_tags
        view = TagSelectView(tags=available_tags, thread=thread)
        await interaction.response.send_message(content="Select the tags:", view=view, ephemeral=True)
    
    # Pin context command
    async def pin_message(self, interaction: discord.Interaction, message: discord.Message):
        if not isinstance(message.channel, discord.Thread) or message.channel.parent.id not in ALLOWED_FORUMS:
            await interaction.response.send_message(content="This command can only be run in a submission or development thread", ephemeral=True)
            return
        if interaction.user.id != interaction.channel.owner_id:
            await interaction.response.send_message(content="You can only pin messages in your submission or development post", ephemeral=True)
            return
        try:
            await message.pin()
            await interaction.response.send_message(content="Message pinned!", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(content=f"An error occured: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))