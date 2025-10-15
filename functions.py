from modals import*

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
        embed = discord.Embed(title=f"Tag {str(self.tag.emoji)} {self.tag.name} added", description=f"To post: **{interaction.channel.name}**\nBy: {interaction.user.mention}")
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

# Create tags selector
class TagSelectView(discord.ui.View):
    def __init__(self, tags: list[discord.ForumTag], thread: discord.Thread):
        super().__init__()
        self.selected_tags = []
        self.thread = thread
        self.all_tags = tags
        options = [discord.SelectOption(label=tag.name, emoji=tag.emoji, value=str(tag.id)) for tag in tags[:25]]
        self.tag_select = discord.ui.Select(
            placeholder="Choose the tags for the post. . .",
            min_values=1,
            max_values=5,
            options=options
        )
        self.tag_select.callback = self.select_callback
        self.add_item(self.tag_select)
    async def select_callback(self, interaction:discord.Interaction):
        await interaction.response.defer()
        self.tag_select.disabled = True
        self.selected_tags = self.tag_select.values
        tags_to_apply =  [tag for tag in self.all_tags if str(tag.id) in self.selected_tags]
        logs = bot.get_channel(LOG_CHANNEL)
        for tag in tags_to_apply:
            embed = discord.Embed(title=f"Tag {str(tag.emoji)} {tag.name} added", description=f"To post: **{self.thread.name}**\nBy: {interaction.user.mention}")
            await logs.send(embed=embed)
        await self.thread.edit(applied_tags=tags_to_apply)
        await interaction.edit_original_response(content="Tags set!", view=None)

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
        await logs.send(embed=discord.Embed(title="Could not fetch messages in tracker channel", description="Error opening the messages.json file"))
    
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

# Message actions
@bot.event
async def on_message(message):
    #Ignore own messages
    if message.author == bot.user:
        return
    # Pin snapshot updates
    if message.flags.is_crossposted and message.channel.id == SNAPSHOT_CHANNEL:
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            pinned_messages = await message.channel.pins(limit=1)
            if pinned_messages:
                await pinned_messages[0].unpin()
                embed = discord.Embed(title=f"Old pinned message removed", description=f"In: {message.channel.name}")
                await logs.send(embed=embed)
            await message.pin()
            embed = discord.Embed(title=f"Snapshot update message pinned", description=f"In: {message.channel.name}")
            await logs.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(title=f"An error occurred {e}")
            await logs.send(embed=embed)
    # Reply to pings
    if bot.user in message.mentions:
        await message.channel.send(f'{message.author.mention} 🏓')
    await bot.process_commands(message)
    # Pin first message in submission posts
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUBMISSIONS_CHANNEL:
        logs = bot.get_channel(LOG_CHANNEL)
        if message.id == message.channel.id:
            try:
                await message.pin()
                embed = discord.Embed(title=f"Message pinned", description=f"In: {message.channel.name}")
                await logs.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(title=f"An error occurred {e}")
                await logs.send(embed=embed)

# Add to tracker
async def track(thread):
    logs = bot.get_channel(LOG_CHANNEL)
    embed = discord.Embed(title=f"Submission created", description=f"{thread.name}")
    await logs.send(embed=embed)
    # Send to tracker
    tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
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
    await update_tracker_list()

# Submission tracker
@bot.event
async def on_thread_create(thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL:
        await track(thread)

# Role error handling
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(content="Sorry, you don't have the required role to use this command", ephemeral=True)
    else:
        await interaction.response.send_message(content=f"An error occured: {error}", ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        await logs.send(embed=discord.Embed(title="An error occured", description=f"for command {interaction.command.name}: {error}"))

# Thread updates
@bot.event
async def on_thread_update(before, after):
    # Edit tracker post if submission post title changes
    if before.parent.id == SUBMISSIONS_CHANNEL and before.name != after.name:
        logs = bot.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title="Submission post title changed", description=f"Before: {before.name}\nAfter: {after.name}")
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
                    embed = discord.Embed(title=f"An error occurred {e}")
                    await logs.send(embed=embed)
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
            for tag_added in tags_added:
                tag_emote = str(tag_added.emoji).strip("_")
                tag_name = str(tag_added)

                # Pick the embed colour
                embed_colour = TAG_COLOUR.get(tag_name, None)
                if embed_colour is None:
                    embed_colour = discord.Colour.light_gray()
                await after.send(embed = discord.Embed(title = f"Marked as {tag_emote} {tag_name}", color = embed_colour))

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
                        embed = discord.Embed(title=f"An error occurred {e}")
                        await logs.send(embed=embed)
                    # Update tracker list
                    await update_tracker_list()
                    break