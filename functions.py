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
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title=f"Tag {str(tag.emoji)} {tag.name} added", description=f"To post: **{interaction.channel.name}**\nBy: {interaction.user.mention}")
        await logs.send(embed=embed)
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

# Edit box
class EditBox(discord.ui.Modal, title="Edit Message"):
    def __init__(self, original_content: str, original_embed: discord.Embed = None):
        super().__init__()
        self.message_text = discord.ui.TextInput(
            label="Message content:", 
            default=original_content, 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.message_text)
        self.original_embed = original_embed
        if original_embed:
            self.embed_text = discord.ui.TextInput(
                label="Embed description:",
                default=original_embed.description,
                style=discord.TextStyle.long,
                required=False
            )
            self.add_item(self.embed_text)

    async def on_submit(self, interaction: discord.Interaction):
        new_content=self.message_text.value
        if hasattr(self,'embed_text'):
            new_embed = self.original_embed
            new_embed.description = self.embed_text.value
            await self.target_message.edit(embed=new_embed)
        await self.target_message.edit(content=new_content)
        await interaction.response.send_message(content="Message successfully edited!", ephemeral=True)

# Send chunked messages
async def send_chunked_messages(channel, header, items, id_list):
    if not items:
        return
    message_content = header + "\n"
    for item in items:
        if len(message_content) + len(item) + 2 > DISCORD_CHAR_LIMIT:
            sent_message  = await channel.send(message_content)
            id_list.append(sent_message.id)
            message_content = ""
        message_content += item + "\n"
    if len(message_content) > 2:
        sent_message = await channel.send(message_content)
        id_list.append(sent_message.id)

# Fetch thread ID given name
async def get_thread_by_name(channel, name):
    for thread in channel.threads:
        if thread.name == name:
            return thread
    async for thread in channel.archived_threads(limit=None):
        if thread.name == name:
            return thread
    logs = bot.get_channel(LOG_CHANNEL)
    embed = discord.Embed(title=f"Could not find discussion thread", description=f"for post **{name}**")
    await logs.send(embed=embed)
    return None

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

    if pending_messages or awaiting_testing:
        pending_messages.reverse()
        awaiting_testing.reverse()
        await send_chunked_messages(tracker_channel, "## 🕥 Pending Decision", pending_messages, tracker_list_messages)
        await send_chunked_messages(tracker_channel, "## 🧪 Awaiting Testing", awaiting_testing, tracker_list_messages)
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
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUBMISSIONS_CHANNEL:
        logs = bot.get_channel(LOG_CHANNEL)
        if message.id == message.channel.id:
            try:
                await message.pin()
                embed = discord.Embed(title=f"Message pinned", description=f"in {message.channel.name}")
                await logs.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(title=f"An error occured {e}")
                await logs.send(embed=embed)



# Submission tracker
@bot.event
async def on_thread_create(thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL:
        # Logging
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title=f"Submission created", description=f"{thread.name}")
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

# Thread updates
@bot.event
async def on_thread_update(before, after):
    # Edit tracker post if submission post title changes
    if before.parent.id == SUBMISSIONS_CHANNEL and before.name != after.name:
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title="Submission post title changed")
        await logs.send(embed=embed)
        tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
        async for message in tracker_channel.history(limit=100, oldest_first=True):
            if before.name in message.content:
                embed = discord.Embed(title="Found tracker post", description="Attempting edit")
                await logs.send(embed=embed)
                try:
                    discussion_thread = await get_thread_by_name(tracker_channel, before.name)
                    await message.edit(content=f"## [{after.name}]({after.jump_url})\n{discussion_thread.jump_url}")
                    await discussion_thread.edit(name=f"{after.name}")
                    embed = discord.Embed(title=f"Tracker post title updated", description=f"From: **{before.name}**\nTo: **{after.name}**")
                    await logs.send(embed=embed)
                    break
                except Exception as e:
                    embed = discord.Embed(title=f"An error occured {e}")
                    await logs.send(embed=embed)
                    break
    # Tag updates
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
        if tag_added.id in RESOLVED_TAGS and before.parent.id == SUBMISSIONS_CHANNEL:
            tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
            async for message in tracker_channel.history(limit=100, oldest_first=True):
                if str(before.id) in message.content:
                    logs = bot.get_channel(LOG_CHANNEL)
                    try:
                        await message.delete()
                        embed = discord.Embed(title=f"Tracker post removed", description=f"**{before.name}**")
                        await logs.send(embed=embed)
                    except Exception as e:
                        embed = discord.Embed(title=f"An error occured {e}")
                        await logs.send(embed=embed)
                    # Update tracker list
                    await update_tracker_list()
                    break