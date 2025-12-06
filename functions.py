from init import*

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
            max_values=min(5, len(options)),
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
        log_message = []
        for tag in tags_to_apply:
            emoji = tag.emoji or ""
            log_message.append(f"{emoji} {tag.name}".strip())
        if log_message:
            embed = discord.Embed(title=f"Tags {",  ".join(log_message)} added", description=f"To post: **{self.thread.name}**\nBy: {interaction.user.mention}")
            await logs.send(embed=embed)
        await self.thread.edit(applied_tags=tags_to_apply)
        await interaction.edit_original_response(content="Tags set!", view=None)

# Delete message approval
class DeleteMessageApprovalView(discord.ui.View):
    def __init__(self, target_message_id: int, target_channel_id: int, requester: discord.Member, timeout=3600):
        super().__init__(timeout=timeout)
        self.target_message_id = target_message_id
        self.target_channel_id = target_channel_id
        self.requester = requester
        self.approval_message = None

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve")
        self.reject_button = discord.ui.Button(label="Reject", style=discord.ButtonStyle.red, custom_id="reject")

        self.approve_button.callback = self.approve_callback
        self.reject_button.callback = self.reject_callback

        self.add_item(self.approve_button)
        self.add_item(self.reject_button)

    async def approve_callback(self, interaction: discord.Interaction):
        if interaction.user == self.requester:
            await interaction.response.send_message("You can't approve your own request silly", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            target_channel = await bot.fetch_channel(self.target_channel_id)
            target_message = await target_channel.fetch_message(self.target_message_id)
            message_content = target_message.content
            if target_message.embeds:
                message_embed_title = target_message.embeds[0].title or None
                message_embed_desc = target_message.embeds[0].description or None
                if message_embed_title:
                    message_content+=f"\n**Title:** {message_embed_title}"
                if message_embed_desc:
                    message_content+=f"\n**Description:** {message_embed_desc}"
            log_message = await logs.send(embed=discord.Embed(title="Bot message deleted", description=f"Requested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nContent: {message_content[:1900]}"))
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Message deletion request by {self.requester.mention} approved by {interaction.user.mention}\nLog message: {log_message.jump_url}"), view=None)
            await target_message.delete()
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving message deletion request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error approving message deletion request", description=f"{e}"))
    async def reject_callback(self, interaction: discord.Interaction):
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Message deletion request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting message deletion request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error rejecting message deletion request", description=f"{e}"))
    async def on_timeout(self):
        if self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Message deletion request by {self.requester.mention}"), view=None)

# Delete thread approval
class DeleteThreadApprovalView(discord.ui.View):
    def __init__(self, target_post_id: int, requester: discord.Member, timeout=3600):
        super().__init__(timeout=timeout)
        self.target_post_id = target_post_id
        self.requester = requester
        self.approval_message = None

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve")
        self.reject_button = discord.ui.Button(label="Reject", style=discord.ButtonStyle.red, custom_id="reject")

        self.approve_button.callback = self.approve_callback
        self.reject_button.callback = self.reject_callback

        self.add_item(self.approve_button)
        self.add_item(self.reject_button)

    async def approve_callback(self, interaction: discord.Interaction):
        if interaction.user == self.requester:
            await interaction.response.send_message("You can't approve your own request silly", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            target_post = await bot.fetch_channel(self.target_post_id)
            await logs.send(embed=discord.Embed(title="Thread deleted", description=f"Requested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nThread: {target_post.name}\n In: {target_post.parent.jump_url}"))
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Thread deletion request by {self.requester.mention} approved by {interaction.user.mention}\nThread: {target_post.name} in {target_post.parent.jump_url}"), view=None)
            await target_post.delete()
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving thread deletion request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error approving thread deletion request", description=f"{e}"))
    async def reject_callback(self, interaction: discord.Interaction):
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Thread deletion request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting thread deletion request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error rejecting thread deletion request", description=f"{e}"))
    async def on_timeout(self):
        if self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Thread deletion request by {self.requester.mention}"), view=None)

# Edit thread title approval
class EditTitleApproval(discord.ui.View):
    def __init__(self, post: discord.Thread, requester: discord.Member, title: str, timeout=3600):
        super().__init__(timeout=timeout)
        self.post = post
        self.requester = requester
        self.title = title
        self.approval_message = None

        self.approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve")
        self.reject_button = discord.ui.Button(label="Reject", style=discord.ButtonStyle.red, custom_id="reject")

        self.approve_button.callback = self.approve_callback
        self.reject_button.callback = self.reject_callback

        self.add_item(self.approve_button)
        self.add_item(self.reject_button)
    async def approve_callback(self, interaction: discord.Interaction):
        if interaction.user == self.requester:
            await interaction.response.send_message("You can't approve your own request silly", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            await logs.send(embed=discord.Embed(title="Thread title updated", description=f"From: {self.post.name}\nTo: {self.title}\nRequested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nThread: {self.post.jump_url}"))
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Thread title change request by {self.requester.mention} approved by {interaction.user.mention}\nFrom: {self.post.name}\nTo: {self.title}\nThread: {self.post.jump_url}"), view=None)
            await self.post.edit(name=self.title, archived=False)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving thread title change request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error approving thread title change request", description=f"{e}"))
    async def reject_callback(self, interaction: discord.Interaction):
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Thread title change request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting thread title change request: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error rejecting thread title change request", description=f"{e}"))
    async def on_timeout(self):
        if self.approval_message and self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Thread title change request by {self.requester.mention}"), view=None)

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

# Open all archive threads
async def open_all_archived(interaction: discord.Interaction):
    guild = interaction.guild
    opened_posts = 0
    
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel) and (channel.category_id not in NON_ARCHIVE_CATEGORIES):
            async for thread in channel.archived_threads(limit=None):
                if thread.archived:
                    try:
                        await thread.edit(archived=False)
                        opened_posts += 1
                    except discord.Forbidden:
                        await interaction.followup.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{channel.id}>", ephemeral=True)
                        return
    faq_channel = bot.get_channel(FAQ_CHANNEL)
    async for thread in faq_channel.archived_threads(limit=None):
        if thread.archived:
            try:
                await thread.edit(archived=False)
                opened_posts += 1
            except discord.Forbidden:
                await interaction.followup.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{faq_channel.id}>", ephemeral=True)
                return
    return opened_posts

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
async def on_message(message: discord.Message):
    #Ignore own messages
    if message.author == bot.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        try:
            helper_thread = await bot.fetch_channel(1413793955295920178)
            await helper_thread.send(embed=discord.Embed(title="DM received", description=f"From user: {message.author.mention}\nContent: {message.content}", color=discord.Color.dark_gold()))
        except Exception as e:
            logs = bot.get_channel(LOG_CHANNEL)
            await logs.send(embed=discord.Embed(title="Error forwarding DM", description=f"{e}"))
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
        random_message = random.choice(RANDOM_REPLIES)
        await message.reply(content=random_message, mention_author=False)
    await bot.process_commands(message)
    # Pin first message in submission posts and send info message
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUBMISSIONS_CHANNEL:
        logs = bot.get_channel(LOG_CHANNEL)
        if message.id == message.channel.id:
            try:
                await message.pin()
                embed = discord.Embed(
                    title="Thank you for your submission!",
                    description="""
- 📌 The submitter of the post can pin messages in the thread using the application command shown below. 
- ❌ This thread is for archival-related discussion only. No development or help questions are allowed.
- ⌚ Please be patient, as the archival team has a lot of posts to process. We will review this post as soon as possible."""
                )
                embed.set_image(url="https://cdn.discordapp.com/attachments/1331670749471047700/1428615699378733108/how_to_pin.png")
                await message.channel.send(embed=embed)
                log_embed = discord.Embed(title=f"Message pinned", description=f"In: {message.channel.name}")
                await logs.send(embed=log_embed)
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
async def on_thread_create(thread: discord.Thread):
    if thread.parent.id == SUBMISSIONS_CHANNEL and thread.name != "Test":
        await track(thread)

# Role error handling
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole) or isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message(content="Sorry, you don't have the required role to use this command", ephemeral=True)
    else:
        await interaction.response.send_message(content=f"An error occured: {error}", ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        await logs.send(embed=discord.Embed(title="An error occured", description=f"for command {interaction.command.name} run by {interaction.user.mention}: {error}"))

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
            tag_list = []
            for tag_added in tags_added:
                tag_emote = tag_added.emoji or ""
                tag_name = tag_added.name

                # Pick the embed colour
                embed_colour = TAG_COLOUR.get(tag_name, None)
                if embed_colour is None:
                    embed_colour = discord.Colour.light_gray()
                tag_list.append(f"{tag_emote} {tag_name}".strip())
                
                # Submission accepted or rejected
                if tag_added.id in RESOLVED_TAGS and before.parent.id == SUBMISSIONS_CHANNEL:
                    tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
                    async for message in tracker_channel.history(limit=100, oldest_first=True):
                        if str(before.id) in message.content:
                            logs = bot.get_channel(LOG_CHANNEL)
                            # Send vote results in thread
                            tracker_thread = await get_thread_by_name(tracker_channel, before.name)
                            vote_results = "**Votes as of submission resolution:**\n"
                            for reaction in message.reactions:
                                vote_results += f"{reaction.emoji} - "
                                users = [user.mention async for user in reaction.users() if user.id != bot.user.id]
                                vote_results += ", ".join(users)
                                vote_results += "\n"
                            await tracker_thread.send(content=vote_results, allowed_mentions=discord.AllowedMentions.none())
                            # Delete tracker message
                            try:
                                await message.delete()
                                embed = discord.Embed(title=f"Tracker post removed", description=f"**{before.name}**")
                                await logs.send(embed=embed)
                            except Exception as e:
                                embed = discord.Embed(title=f"An error occurred {e}")
                                await logs.send(embed=embed)
                            # Update tracker list
                            await update_tracker_list()

            await after.send(embed = discord.Embed(title = f"Marked as {",  ".join(tag_list)}", color = embed_colour))