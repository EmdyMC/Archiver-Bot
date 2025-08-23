from init import *

# Edit tag button
class TagButton(discord.ui.Button):
    def __init__(self, tag, style):
        super().__init__(label = tag.name, style = style)
        self.tag = tag

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_tags = [self.tag]
        if self.view.forum_id in FORUMS:
            if not self.tag.name in UPPER_TAGS:
                for tag in interaction.channel.applied_tags:
                    if tag.name in UPPER_TAGS:
                        new_tags.append(tag)

        await interaction.channel.edit(applied_tags = new_tags)
        await interaction.delete_original_response()

# Edit tag view
class TagView(discord.ui.View):
    def __init__(self, tag_list: list, forum_id:int):
        super().__init__(timeout = 30)
        self.forum_id = forum_id
        self.msg = None
        for tag in tag_list:
            self.add_item(TagButton(tag, discord.ButtonStyle.primary))

    async def set_message(self, msg):
        self.msg = msg

    async def on_timeout(self):
        pass

# Update tracker list
async def update_tracker_list():
    pending_messages = []
    awaiting_testing = []
    tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
    logs = bot.get_channel(LOG_CHANNEL)
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
            if CROSS_EMOJI in tracking_message.content:
                continue
            reactions = tracking_message.reactions
            if any(TESTING_EMOJI == reaction.emoji for reaction in reactions):
                awaiting_testing.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")
            else:
                if tracking_message.content == "":
                    continue
                pending_messages.append("- **"+tracking_message.content[3:].replace("\n", " ")+" **")
    except:
        await logs.send(embed=discord.Embed(title="Could not fetch messages in tracker channel"))

    tracker_list_messages = []

    if len(pending_messages) + len(awaiting_testing) > 0:
        pending_messages.reverse()
        awaiting_testing.reverse()
        pending_list = f"## 🕥 Pending Decision\n "
        for pending_message in pending_messages:
            if len(pending_list) < DISCORD_CHAR_LIMIT:
                pending_list += "\n ".join(pending_message)
            else:
                sent = await tracker_channel.send(pending_list)
                pending_list = f""
                tracker_list_messages.append(sent.id)

        awaiting_list = f"## 🧪 Awaiting Testing\n "
        for awaiting_message in awaiting_testing:
            if len(awaiting_list) < DISCORD_CHAR_LIMIT:
                awaiting_list += "\n ".join(awaiting_message)
            else:
                sent = await tracker_channel.send(awaiting_list)
                awaiting_list = f""
                tracker_list_messages.append(sent.id)
        try:
            async with aiofiles.open("messages.json", mode='w') as list:
                await list.write(json.dumps(tracker_list_messages))
        except Exception as e:
            await logs.send(embed=discord.Embed(title="Error saving message IDs", description=f"Error: {e}"))

    else:
        await logs.send(embed=discord.Embed(title="No posts found in tracker channel"))

# Ping reply
@bot.event
async def on_message(message):
    #Ignore own messages
    if message.author == bot.user:
        return
    # Reply to pings
    if bot.user in message.mentions:
        await message.channel.send(f'{message.author.mention} 🏓')
    await bot.process_commands(message)


# Submission tracker
@bot.event
async def on_thread_create(thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL:
        # Logging
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title=f"Submission created: {thread.name}")
        await logs.send(embed=embed)
        # Send to tracker
        tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        discussion_thread = await tracker_channel.create_thread(name=thread.name)
        await discussion_thread.send(f"For discussion and debate regarding the archival staus of {thread.jump_url}")
        ping_message = await discussion_thread.send("ping")
        await ping_message.edit(content="<@&1162049503503863808> 🏓 chat away!")
        notif = await tracker_channel.send(f"## [{thread.name}]({thread.jump_url})\n{discussion_thread.jump_url}")
        await asyncio.gather(
            notif.add_reaction("❌"),
            notif.add_reaction("🔴"),
            notif.add_reaction("🟢"),
            notif.add_reaction("✅")
        )
        # Resend tracker list
        await update_tracker_list()

# Remove tracker post on archival/reject and update notifs
@bot.event
async def on_thread_update(before, after):
    if before.parent.id in FORUMS:
        try:
            tag_before = set(before.applied_tags)
            tag_after = set(after.applied_tags)
            tag_added = list(tag_after - tag_before)[0]
        except:
            return
        if tag_added:
            tag_emote = str(tag_added.emoji).strip("_")
            tag_name = str(tag_added)

            # Pick the embed colour
            embed_colour = TAG_COLOUR.get(tag_name, None)
            if embed_colour is None:
                embed_colour = discord.Colour.light_gray()
            await after.send(embed = discord.Embed(title = f"Marked as {tag_emote} {tag_name}", color = embed_colour))
            # Close posts if resolved
            if tag_added.id in GENERAL_RESOLVED_TAGS:
                await after.edit(archived=True)

        # Remove the tracker channel message
        if tag_added.id in RESOLVED_TAGS:
            tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
            async for message in tracker_channel.history(limit=100, oldest_first=True):
                if str(before.id) in message.content:
                    logs = bot.get_channel(LOG_CHANNEL)
                    try:
                        await message.delete()
                        embed = discord.Embed(title=f"Submission tracker post of **{before.name}** removed")
                        await logs.send(embed=embed)
                    except Exception as e:
                        embed = discord.Embed(title=f"An error occured {e}")
                        await logs.send(embed=embed)
                    # Update tracker list
                    await update_tracker_list()
                    break     