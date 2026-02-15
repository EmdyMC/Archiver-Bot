from init import *

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
            embed = discord.Embed(title=f"Tags {",  ".join(log_message)} added", description=f"To post: **{self.thread.jump_url}**\nBy: {interaction.user.mention}")
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
            parsed_file = Path.cwd() / "parsed" / f"{self.target_post_id}.json"
            if parsed_file.exists():
                parsed_file.unlink()
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

# Parse error views
class ParserErrorItem(discord.ui.Container):
    def __init__(self, bot: commands.Bot, thread: discord.Thread, error: Exception, i: int):
        super().__init__()
        self.accent_color = discord.Color.red()
        self.bot = bot
        self.thread = thread
        self.i = i
        self.text_display = discord.ui.TextDisplay(f"{thread.jump_url}: **{type(error).__name__}**: {error}")
        self.action_row = discord.ui.ActionRow()
        self.add_item(self.text_display)
        self.add_item(self.action_row)

    @classmethod
    async def create(cls: Type["ParserErrorItem"], bot: commands.Bot, thread: discord.Thread, error: Exception, i: int):
        reverse_messages = reversed([message async for message in thread.history()])
        instance = cls(bot, thread, error, i)
        for i, message in enumerate(reverse_messages):
            if (i >= 5):
                instance.add_item(discord.ui.TextDisplay("-# Max 5 buttons exceeded, edit directly in thread instead."))
                break
            button = discord.ui.Button(label=f"Edit {i}")
            button.callback = instance.get_editor(message)
            instance.action_row.add_item(button)
        return instance
    
    def get_editor(self, message: discord.Message):
        from modals import PostEditAndParseModal
        async def edit(interaction: discord.Interaction[commands.Bot]):
            if interaction.user.get_role(ARCHIVER_ID) is None:
                raise app_commands.errors.MissingRole(ARCHIVER_ID)
            await interaction.response.send_modal(PostEditAndParseModal(self.bot, message, interaction.message, self.i))
        return edit

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

# Generate difflib messages
def get_diff_block(old_text, new_text):
    if old_text == new_text: return None

    diff = difflib.unified_diff(
        str(old_text or "").splitlines(), 
        str(new_text or "").splitlines(), 
        n=1, 
        lineterm=''
    )
    
    lines = list(diff)[2:]
    ansi_lines = []
    current_len = 0
    
    for line in lines:
        if line.startswith('+'):
            formatted = f"\u001b[0;32m{line}\u001b[0m"
        elif line.startswith('-'):
            formatted = f"\u001b[0;31m{line}\u001b[0m"
        elif line.startswith('@@'):
            formatted = f"\u001b[0;34m{line}\u001b[0m"
        else:
            formatted = line
            
        if current_len + len(formatted) > 950:
            ansi_lines.append("\u001b[0;33m... [Truncated for length]\u001b[0m")
            break
            
        ansi_lines.append(formatted)
        current_len += len(formatted) + 1

    return "\n".join(ansi_lines)

# Timeout user
async def timeout_user(seconds: int, user: discord.Member):
    try:
        until = datetime.now(UTC) + timedelta(seconds=seconds)
        await user.timeout(until, reason="No chat user caught")
    except discord.Forbidden:
        logs = bot.get_channel(LOG_CHANNEL)
        await logs.send(f"Could not timeout user {user.mention}, no permission.")

# Open all archive threads
async def open_all_archived(run_channel: discord.TextChannel):
    opened_posts = 0
    guild = run_channel.guild
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel) and (channel.category_id not in NON_ARCHIVE_CATEGORIES):
            async for thread in channel.archived_threads(limit=None):
                if thread.archived:
                    try:
                        await thread.edit(archived=False)
                        opened_posts += 1
                    except discord.Forbidden:
                        await run_channel.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{channel.id}>")
                        return
    faq_channel = bot.get_channel(FAQ_CHANNEL)
    async for thread in faq_channel.archived_threads(limit=None):
        if thread.archived:
            try:
                await thread.edit(archived=False)
                opened_posts += 1
            except discord.Forbidden:
                await run_channel.send(f"Error: Bot does not have manage threads permission to edit <#{thread.id}> in <#{faq_channel.id}>")
                return
    if opened_posts > 0:
        report = f"**Successfully opened {opened_posts} forum post(s)**"
        await run_channel.send(content=report)
    else:
        await run_channel.send("No closed forum posts found in the archives")

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
    accepted_posts = []
    tracker_channel = bot.get_channel(SUBMISSIONS_TRACKER_CHANNEL)
    logs = bot.get_channel(LOG_CHANNEL)
    submissions_forum = bot.get_channel(SUBMISSIONS_CHANNEL)
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
        async for thread in submissions_forum.archived_threads(limit=None):
            for tag in thread.applied_tags:
                if tag.id == ACCEPTED_TAG:
                    accepted_posts.append(f"- **[{thread.name}]({thread.jump_url})**")
    except Exception as e:
        await logs.send(embed=discord.Embed(title="Could not fetch messages in tracker channel", description=f"{e}"))
    
    tracker_list_messages = []

    if pending_messages or awaiting_testing or accepted_posts:
        pending_messages.reverse()
        awaiting_testing.reverse()
        await send_chunked_messages(tracker_channel, f"## 🕥 Pending Decision ({len(pending_messages)})", pending_messages, tracker_list_messages)
        await send_chunked_messages(tracker_channel, f"## 🧪 Awaiting Testing ({len(awaiting_testing)})", awaiting_testing, tracker_list_messages)
        await send_chunked_messages(tracker_channel, f"## ✅ Pending Archival ({len(accepted_posts)})", accepted_posts, tracker_list_messages)
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
    logs = bot.get_channel(LOG_CHANNEL)
    # Ignore own messages
    if message.author == bot.user:
        return
    # Forward DMs
    if isinstance(message.channel, discord.DMChannel):
        try:
            helper_thread = await bot.fetch_channel(1413793955295920178)
            reply_view = ReplyButton(DM=message)
            forward = discord.Embed(title="DM received", description=f"From user: {message.author.name} {message.author.mention}\nContent: {message.content}", color=discord.Color.dark_gold())
            forward.set_thumbnail(message.author.display_avatar.url)
            attachments = []
            for attachment in message.attachments:
                attachments.append(await attachment.to_file())
            if message.attachments:
                forward.description = f"From user: {message.author.mention}\nContent: {message.content}\nAttachment:"
                forward.set_image(url=f"attachment://{attachments[0].filename}")
            await helper_thread.send(embed=forward, files=attachments, view=reply_view)
        except Exception as e:
            await logs.send(embed=discord.Embed(title="Error forwarding DM", description=f"{e}"))
    # Pin snapshot updates
    if message.flags.is_crossposted and message.channel.id == SNAPSHOT_CHANNEL:
        try:
            pinned_messages = await message.channel.pins(limit=5)
            if pinned_messages:
                await pinned_messages[-1].unpin()
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
    # Catch images sent by no chat users
    if message.author.get_role(NO_CHAT) and not any(role.id in STAFF_ROLES for role in message.author.roles):
        attachments = []
        try:
            for attachment in message.attachments:
                attachments.append(await attachment.to_file())
            message_content = message.content
            jump_url = message.channel.jump_url
            author = message.author
            await message.delete()
            await timeout_user(seconds=20, user=author)
            warn_embed=discord.Embed(
                title="Message blocked", 
                description=f"""
{message.author.mention} Your message on TMCC has been blocked as part of scam prevention efforts as you failed to select the right onboarding option when joining the server (see below) and your account is suspected to be compromised.
If you wish to partake in the server fully make sure to select the correct option in the "Channels and Roles" section and adhere to the rules of the server."""
)
            warn_embed.set_image(url="https://cdn.discordapp.com/attachments/1315522702492172300/1466707151472033954/image.png")
            try:
                await message.author.send(embed=warn_embed)
                await message.channel.send(embed=warn_embed, delete_after=10)
                dm_status = "Notified via DM and in channel"
            except discord.Forbidden:
                await message.channel.send(embed=warn_embed, delete_after=10)
                dm_status = "DMs closed, notified in-channel"
            log_embed = discord.Embed(title="No chat user caught", description=f"User {author.mention} tried to send a message in {jump_url} but has the no chat role. {dm_status}.\nContent: {message_content}", color=discord.Color.red())
            if attachments:
                log_embed.set_image(url=f"attachment://{attachments[0].filename}")
            await logs.send(embed=log_embed, files=attachments)
        except Exception as e:
            await logs.send(embed=discord.Embed(title="Error in no-chat filter", description=f"{e}", color=discord.Color.red()))
    # Pin first message in submission posts and send info message
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id == SUBMISSIONS_CHANNEL:
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
                log_embed = discord.Embed(title=f"Message pinned", description=f"In: {message.channel.jump_url}")
                await logs.send(embed=log_embed)
            except Exception as e:
                embed = discord.Embed(title=f"An error occurred {e}")
                await logs.send(embed=embed)
    # Pin first message in help forum and send info message
    if isinstance(message.channel, discord.Thread) and message.channel.parent_id == HELP_FORUM:
        if message.id == message.channel.id:
            try:
                await message.pin()
                embed = discord.Embed(
                    title="Thank you for submitting your question!",
                    description="""
- ✅ The submitter of this question can mark posts as solved by using `/tag_selector` and selecting `✅ Solved`.
- 📖 Refer to the [guide](https://discord.com/channels/1161803566265143306/1378040485133680772) to get faster and better answers to your questions. Add any relevant information to your post.
- ⌚ Please be patient and polite. Remember that all helpers are volunteers."""
                )
                await message.channel.send(embed=embed)
                log_embed = discord.Embed(title=f"Message pinned", description=f"In: {message.channel.jump_url}")
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
                
                # Resend tracker list when a design is archived
                if tag_added.id == ARCHIVED_TAG and before.parent.id == SUBMISSIONS_CHANNEL:
                    await update_tracker_list()

                # Submission accepted or rejected
                if tag_added.id in RESOLVED_TAGS and before.parent.id == SUBMISSIONS_CHANNEL:
                    # Find tracker message
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
                            break

            await after.send(embed = discord.Embed(title = f"Marked as {",  ".join(tag_list)}", color = embed_colour))

@tasks.loop(hours=12)
async def archive_management():
    await bot.wait_until_ready()
    logs = bot.get_channel(LOG_CHANNEL)
    await logs.send(embed=discord.Embed(title="Maintenence", description="Running periodic archive post open and resolved thread close commands", color=discord.Color.green()))
    await open_all_archived(run_channel=logs)

def get_post_metadata(thread: discord.Thread, channel: discord.ForumChannel, bot: commands.Bot) -> dict[str, str|list[str]]:
    #Returns a dict of metadata to add on top of the post message
    return {
        "thread_id": str(thread.id),
        "thread_name": thread.name,
        "channel_id": str(channel.id),
        "channel_name": channel.name,
        "author_id": str(thread.owner_id),
        "created_at": str(thread.created_at),
        "tags": [tag.name for tag in thread.applied_tags],
        "messages": []
    }

async def get_post_data(thread: discord.Thread, channel: discord.ForumChannel, bot: commands.Bot) -> dict[str, str|list[str]]:
    #Gets the metadata for the post along with all the post messages
    # Add all the post messages to the metadata
    metadata = get_post_metadata(thread, channel, bot)
    async for message in thread.history(limit=None, oldest_first=True):
        # Add it if the message exists and is not a discord message (pin/rename thread)
        if message.content and message.type == discord.MessageType.default:
            metadata["messages"].append(message.content)
    return metadata

async def iter_all_threads(channel: discord.ForumChannel):
    #Iterates over all threads, active or not
    for thread in channel.threads:
        yield thread

    async for thread in channel.archived_threads(limit=None):
        yield thread

# Reply view
class ReplyButton(discord.ui.View):
    def __init__(self, DM: discord.Message):
        super().__init__(timeout=None)
        self.DM = DM
        self.reply_button = discord.ui.Button(label="Reply", style=discord.ButtonStyle.blurple, custom_id="reply")
        self.reply_button.callback = self.reply
        self.add_item(self.reply_button)
    async def reply(self, interaction:discord.Interaction):
        await interaction.response.send_modal(ReplyBox(DM=self.DM))

# Reply modal
class ReplyBox(discord.ui.Modal, title="Reply to DM"):
    def __init__(self, DM: discord.Message):
        super().__init__()
        self.message = discord.ui.TextInput(
            label="Message content:",
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.message)
        self.DM = DM
    async def on_submit(self, interaction: discord.Interaction):
        helper_thread = await bot.fetch_channel(1413793955295920178)
        await self.DM.channel.send(self.message.value)
        await interaction.response.send_message(embed=discord.Embed(title="DM Sent", description=f"**{interaction.user.mention} sent the following message to {self.DM.author.mention} in DMs:**\n{self.message.value}"))