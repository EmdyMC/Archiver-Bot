import discord
import aiofiles
import json
import asyncio
from discord.ext import commands
from discord import app_commands
from constants import SUBMISSIONS_TRACKER_CHANNEL, SUBMISSIONS_CHANNEL, TESTING_EMOJI, ACCEPTED_TAG, HIGHER_ROLES, FORUMS, TAG_COLOUR, ARCHIVED_TAG, RESOLVED_TAGS

class Submissions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Update tracker list
    async def update_tracker_list(self):
        pending_messages = []
        awaiting_testing = []
        accepted_posts = []
        tracker_channel = self.bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        utility_cog = self.bot.get_cog("Utility")
        submissions_forum = self.bot.get_channel(SUBMISSIONS_CHANNEL)
        try:
            async with aiofiles.open("messages.json", mode='r') as list:
                content = await list.read()
                message_ids = json.loads(content) if content else []
                for message_id in message_ids:
                    try:
                        message_to_delete = await tracker_channel.fetch_message(message_id)
                        await message_to_delete.delete()
                    except discord.NotFound:
                        continue
            
            async for tracking_message in tracker_channel.history(limit=None):
                reactions = tracking_message.reactions
                if any(TESTING_EMOJI == reaction.emoji for reaction in reactions):
                    awaiting_testing.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")
                else:
                    if tracking_message.content == "":
                        continue
                    pending_messages.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")

            for thread in submissions_forum.threads:
                for tag in thread.applied_tags:
                    if tag.id == ACCEPTED_TAG:
                        accepted_posts.append(f"- **[{thread.name}]({thread.jump_url})**")
        except Exception as e:
            await utility_cog.log(title="Could not fetch messages in tracker channel", description=f"{e}")
        
        tracker_list_messages = []

        if pending_messages or awaiting_testing or accepted_posts:
            pending_messages.reverse()
            awaiting_testing.reverse()
            await utility_cog.send_chunked_messages(tracker_channel, f"## 🕥 Pending Decision ({len(pending_messages)})", pending_messages, tracker_list_messages)
            await utility_cog.send_chunked_messages(tracker_channel, f"## 🧪 Awaiting Testing ({len(awaiting_testing)})", awaiting_testing, tracker_list_messages)
            await utility_cog.send_chunked_messages(tracker_channel, f"## ✅ Pending Archival ({len(accepted_posts)})", accepted_posts, tracker_list_messages)
            try:
                async with aiofiles.open("messages.json", mode='w') as list:
                    await list.write(json.dumps(tracker_list_messages))
            except Exception as e:
                await utility_cog.log(title="Error saving message IDs", description=f"Error: {e}")
        else:
            await utility_cog.log(title="No posts found in tracker channel")

    # Add to tracker
    async def track(self, thread):
        utility_cog = self.bot.get_cog("Utility")
        await utility_cog.log(title=f"Submission created", message=f"{thread.name}")
        # Send to tracker
        tracker_channel = self.bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        discussion_thread = await tracker_channel.create_thread(name=thread.name)
        await discussion_thread.send(f"For discussion and debate regarding the archival status of {thread.jump_url}")
        ping_message = await discussion_thread.send("ping")
        await ping_message.edit(content="<@&1162049503503863808> 🏓 chat away!")
        await ping_message.pin()
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread.jump_url}")
        await asyncio.gather(
            notif.add_reaction("❌"),
            notif.add_reaction("🔴"),
            notif.add_reaction("🟢"),
            notif.add_reaction("✅")
        )
        # Resend tracker list
        await self.update_tracker_list()

    # Submission tracker
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent.id == SUBMISSIONS_CHANNEL and thread.name != "Test":
            await self.track(thread)

    # Tracker list command
    @app_commands.command(name="tracker_list", description="Rechecks and resends the submission tracker list")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def tracker_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.update_tracker_list()
        await interaction.delete_original_response()

    # Track post
    @app_commands.command(name="track", description="Add post to submission tracker")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def track_post(self, interaction: discord.Interaction):
        await interaction.response.defer()
        utility_cog = self.bot.get_cog("Utility")
        if(interaction.channel.type == discord.ChannelType.public_thread and interaction.channel.parent.id == SUBMISSIONS_CHANNEL):
            await self.track(interaction.channel)
            await interaction.followup.send(content="Post tracked", ephemeral=True)
            await utility_cog.log(title="Post tracked", message=f"Post: {interaction.channel.name}\nBy: {interaction.user.mention}")
        else:
            await interaction.followup.send(content="The current thread or channel is not a submission post", ephemeral=True)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        # Edit tracker post if submission post title changes
        if before.parent.id == SUBMISSIONS_CHANNEL and before.name != after.name:
            utility_cog = self.bot.get_cog("Utility")
            await utility_cog.log(title="Submission post title changed", message=f"Before: {before.name}\nAfter: {after.name}")
            tracker_channel = self.bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
            async for message in tracker_channel.history(limit=100, oldest_first=True):
                if before.name in message.content:
                    await utility_cog.log(title="Found tracker post", message="Attempting edit")
                    try:
                        discussion_thread = await utility_cog.get_thread_by_name(tracker_channel, before.name)
                        await message.edit(content=f"## [{after.name}]({after.jump_url})\n{discussion_thread.jump_url}")
                        await discussion_thread.edit(name=f"{after.name}")
                        await utility_cog.log(title=f"Tracker post title updated", description=f"From: **{before.name}**\nTo: **{after.name}**")
                        break
                    except Exception as e:
                        await utility_cog.log(title=f"An error occurred {e}")
                        break
        # Tag updates
        if before.parent.id in FORUMS:
            try:
                tag_before = set(before.applied_tags)
                tag_after = set(after.applied_tags)
                tags_added = list(tag_after - tag_before)
            except:
                return
            if tags_added:
                tag_list = []
                for tag_added in tags_added:
                    tag_emote = tag_added.emoji or ""
                    tag_name = tag_added.name

                    # Pick the embed colour
                    embed_colour = TAG_COLOUR.get(tag_name, None)
                    if embed_colour is None:
                        embed_colour = discord.Colour.light_gray()
                    tag_list.append(f"{tag_emote} {tag_name}".strip())
                    
                    # Resend tracker list when a design is archived
                    if tag_added.id == ARCHIVED_TAG and before.parent.id == SUBMISSIONS_CHANNEL:
                        await self.update_tracker_list()

                    # Submission accepted or rejected
                    if tag_added.id in RESOLVED_TAGS and before.parent.id == SUBMISSIONS_CHANNEL:
                        # Find tracker message
                        tracker_channel = self.bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
                        async for message in tracker_channel.history(limit=100, oldest_first=True):
                            if str(before.id) in message.content:
                                utility_cog = self.bot.get_cog("Utility")
                                # Send vote results in thread
                                tracker_thread = await utility_cog.get_thread_by_name(tracker_channel, before.name)
                                vote_results = "**Votes as of submission resolution:**\n"
                                for reaction in message.reactions:
                                    vote_results += f"{reaction.emoji} - "
                                    users = [user.mention async for user in reaction.users() if user.id != self.bot.user.id]
                                    vote_results += ", ".join(users)
                                    vote_results += "\n"
                                await tracker_thread.send(content=vote_results, allowed_mentions=discord.AllowedMentions.none())
                                # Delete tracker message
                                try:
                                    await message.delete()
                                    await utility_cog.log(title=f"Tracker post removed", message=f"**{before.name}**")
                                except Exception as e:
                                    await utility_cog.log(title=f"An error occurred", message=f"{e}")
                                # Update tracker list
                                await self.update_tracker_list()
                                break

                await after.send(embed = discord.Embed(title = f"Marked as {",  ".join(tag_list)}", color = embed_colour))

async def setup(bot: commands.Bot):
    await bot.add_cog(Submissions(bot))