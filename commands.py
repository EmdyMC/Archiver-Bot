import sys
import os
from modals import *
from parser import message_parse
from functions import ParserErrorItem

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

# Open archived posts command
@bot.tree.command(name="open_archived", description="Opens all posts in the archive")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def open_archived(interaction: discord.Interaction):
    await interaction.response.send_message(content="Checking posts. . .", ephemeral=True)
    await open_all_archived(run_channel=interaction.channel)

# Tag selector command
@bot.tree.command(name="tag_selector", description="Edit the tags of a forum post")
async def selector(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(embed = discord.Embed(title = "This is not a forum post"), ephemeral = True)
        return
    if not isinstance(interaction.channel.parent, discord.ForumChannel):
        await interaction.response.send_message(embed = discord.Embed(title = "This is not a thread in a forum channel"), ephemeral = True)
        return
    in_help_forum = interaction.channel.parent_id == HELP_FORUM
    has_higher_role = any(role.id in HIGHER_ROLES for role in interaction.user.roles)
    if (not in_help_forum and not has_higher_role) or (in_help_forum and interaction.user.id != interaction.channel.owner_id):
        await interaction.response.send_message(embed = discord.Embed(title = "You do not have the permissions to run that command here"), ephemeral = True)
        return
    thread = interaction.channel
    available_tags = thread.parent.available_tags
    view = TagSelectView(tags=available_tags, thread=thread)
    await interaction.response.send_message(content="Select the tags:", view=view, ephemeral=True)

# Tracker list command
@bot.tree.command(name="tracker_list", description="Rechecks and resends the submission tracker list")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def tracker_list(interaction: discord.Interaction):
    await interaction.response.defer()
    await update_tracker_list()
    await interaction.delete_original_response()

# Track post
@bot.tree.command(name="track", description="Add post to submission tracker")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def track_post(interaction: discord.Interaction):
    await interaction.response.defer()
    if(interaction.channel.type == discord.ChannelType.public_thread and interaction.channel.parent.id == SUBMISSIONS_CHANNEL):
        logs = bot.get_channel(LOG_CHANNEL)
        await track(interaction.channel)
        await interaction.followup.send(content="Post tracked", ephemeral=True)
        embed = discord.Embed(title="Post tracked", description=f"Post: {interaction.channel.name}\nBy: {interaction.user.mention}")
        await logs.send(embed=embed)
    else:
        await interaction.followup.send(content="The current thread or channel is not a submission post", ephemeral=True)

# Other archives embed
@bot.tree.command(name="servers", description="Sends the list of other archive servers in a neat embed")
@app_commands.checks.has_role(MODERATOR_ID)
async def archives_embed(interaction: discord.Interaction):
    archives_embed = discord.Embed(title="Other Archive Servers", color=discord.Color.light_embed(), description=OTHER_ARCHIVES)
    await interaction.channel.send(embed=archives_embed)
    await interaction.response.send_message("Embed sent!", ephemeral=True)

# Messsage send
@bot.tree.command(name="send", description="Send a message via the bot to the current channel")
@app_commands.describe(has_embed="Enable the embed field")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def send(interaction: discord.Interaction, has_embed:bool=False):
    send_modal = SendBox(has_embed)
    send_modal.target_channel = interaction.channel
    await interaction.response.send_modal(send_modal)

# Message edit
@bot.tree.context_menu(name="Edit")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def edit(interaction: discord.Interaction, message: discord.Message):
    if message.author==bot.user:
        existing_embeds = [embed for embed in message.embeds if embed.type != "link"] or None
        existing_attachments = message.attachments if message.attachments else None
        edit_modal = EditBox(original_content=message.content, original_embeds=existing_embeds, original_attachments=existing_attachments, target_message=message)
        await interaction.response.send_modal(edit_modal)
    else:
        await interaction.response.send_message(content="The given message is not one made by Archiver Bot, editing is not possible", ephemeral=True)

# Message delete
@bot.tree.context_menu(name="Delete")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def delete(interaction: discord.Interaction, message: discord.Message):
    if message.author!=bot.user:
        await interaction.response.send_message("You can only delete bot messages with this command", ephemeral=True)
    else:
        role_ids = [role.id for role in interaction.user.roles]
        if MODERATOR_ID in role_ids:
            await interaction.response.send_message("You know you don't need to use the bot to delete stuff right?", ephemeral=True)
        else:
            archiver_chat = bot.get_channel(ARCHIVER_CHAT)
            embed=discord.Embed(title="Message deletion request", description=f"{interaction.user.mention} wishes to delete {message.jump_url}")
            view = DeleteMessageApprovalView(target_message_id=message.id, target_channel_id=interaction.channel_id, requester=interaction.user)
            approval_message = await archiver_chat.send(embed=embed, view=view)
            view.approval_message = approval_message
            await interaction.response.send_message(content="Message deletion request sent", ephemeral=True)

# Publish post
@bot.tree.context_menu(name="Publish post")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def publish(interaction: discord.Interaction, message: discord.Message):
    publish_modal = PublishBox(draft=message)
    await interaction.response.send_modal(publish_modal)

# Append post
@bot.tree.context_menu(name="Append post")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def append(interaction: discord.Interaction, message: discord.Message):
    last_thread = getattr(interaction.client, "last_archive_thread", None)
    if last_thread is None:
        append_modal = AppendBox(draft=message)
        await interaction.response.send_modal(append_modal)
    else:
        prompt = AppendPrompt(message=message)
        await interaction.response.send_message(content=f"Do you want to append to **{last_thread.name}** or a different thread?", view=prompt, ephemeral=True)

# Delete post
@bot.tree.command(name="delete_post", description="remove a post from the archive")
@app_commands.describe(thread="Post")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def delete_post(interaction: discord.Interaction, thread: discord.Thread):
    archiver_chat = bot.get_channel(ARCHIVER_CHAT)
    embed=discord.Embed(title="Thread deletion request", description=f"{interaction.user.mention} wishes to delete {thread.jump_url}")
    view = DeleteThreadApprovalView(target_post_id=thread.id, requester=interaction.user)
    approval_message = await archiver_chat.send(embed=embed, view=view)
    view.approval_message = approval_message
    await interaction.response.send_message(content="Thread deletion request sent", ephemeral=True)
    
# Edit post title
@bot.tree.command(name="edit_post_title", description="Edit the title of an archive post")
@app_commands.describe(thread="Post")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def edit_post(interaction: discord.Interaction, thread: discord.Thread):
    edit_modal = EditTitleBox(post=thread)
    await interaction.response.send_modal(edit_modal)

# Help
@bot.tree.command(name="help", description="sends a list of commands that Archiver Bot provides")
@app_commands.checks.has_any_role(*HIGHER_ROLES, HELPER_ID)
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(description=COMMANDS_LIST), ephemeral=True)

# Fetch links
@bot.tree.command(name="fetch_links", description="Return a list of links to the attachments of a message")
@app_commands.describe(message_id="The message with the attachments")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def fetch_links(interaction: discord.Interaction, message_id: str):
    try: 
        message = await interaction.channel.fetch_message(int(message_id))
        if message.attachments:
            links = []
            for attachment in message.attachments:
                url = attachment.url
                index = url.find('?')
                if index != -1:
                    url = url[:index]
                links.append(f"- <{url}>")
            links_message = "\n".join(links)              
            await interaction.response.send_message(content=f"The links to the message attachments:\n{links_message}", ephemeral=True)
        else:
            await interaction.response.send_message(content="The selected message has no attachments", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error while running the command: {e}", ephemeral=True)

# Pin context command
@bot.tree.context_menu(name="Pin")
async def pin_message(interaction: discord.Interaction, message: discord.Message):
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

# Grant role command
@bot.tree.command(name="grant_role", description="Bestow the archived designer or submitter role on someone")
@app_commands.describe(member="The designer")
@app_commands.choices(role=[app_commands.Choice(name="Archived Designer", value=1), app_commands.Choice(name="Submitter", value=2)])
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def archived_designer(interaction: discord.Interaction, member: discord.Member, role: app_commands.Choice[int]):
    try:
        if role.value == 1:
            designer_role = interaction.guild.get_role(ARCHIVED_DESIGNER)
            await member.add_roles(designer_role)
        else:
            submitter_role = interaction.guild.get_role(SUBMITTER)
            await member.add_roles(submitter_role)
        await interaction.response.send_message(content="Role granted successfully", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error while trying to grant the role to {member.name}: {e}", ephemeral=True)

# Upload files
@bot.tree.command(name="upload", description="Upload files straight to the file link dump thread and get the links")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def upload(interaction: discord.Interaction):
    upload_modal = UploadFilesBox()
    await interaction.response.send_modal(upload_modal)

# Parse thread
@bot.tree.command(name="parse_post", description="Checks for errors and parses the selected post")
@app_commands.describe(thread="The post to be parsed")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def parse_thread(interaction: discord.Interaction, thread: discord.Thread):
    exceptions_view = discord.ui.LayoutView(timeout=None)
    (Path.cwd() / "parsed").mkdir(parents=True, exist_ok=True)
    data = get_post_data(thread)
    try:
        parse_result = message_parse("\n".join(data["messages"]).split("\n"))
    except Exception as e:
        error_view = await ParserErrorItem.create(bot, thread, e, 1)
        exceptions_view.add_item(error_view)
        await interaction.channel.send(view=exceptions_view)
        return
    del data["messages"]
    data["variants"] = parse_result
    file_path = Path.cwd() / "parsed" / f"{thread.id}.json"
    json_string = json.dumps(data, indent=4)
    async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
        await f.write(json_string)
    interaction.response.send_message(content=f"Parsed {thread.name} successfully", ephemeral=True)

# Parse channel
@bot.tree.command(name="parse_channel", description="Parse the posts in a selected channel")
@app_commands.describe(channel="The channel to be parsed")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def parse(interaction: discord.Interaction, channel: discord.ForumChannel):
    await interaction.response.send_message("Beginning parsing. . .")
    exceptions_view = discord.ui.LayoutView(timeout=None)
    count = errors = total = 0
    (Path.cwd() / "parsed").mkdir(parents=True, exist_ok=True)

    # Process every thread in the forum channel
    async for thread in iter_all_threads(channel):
        data = await get_post_data(thread, channel, bot)
        total += 1
        try:
            parse_result = message_parse("\n".join(data["messages"]).split("\n"))
        except Exception as e:
            error_view = await ParserErrorItem.create(bot, thread, e, count)
            if exceptions_view.total_children_count < 40 - error_view._total_count:
                exceptions_view.add_item(error_view)
                if exceptions_view.content_length() > 4000:
                    exceptions_view.remove_item(error_view)
                    await interaction.channel.send(view=exceptions_view)
                    error_view.i = 0
                    exceptions_view = discord.ui.LayoutView(timeout=None)
                    exceptions_view.add_item(error_view)
                    count = 0
                count += 1
            else:
                await interaction.channel.send(view=exceptions_view)
                count = 0
                exceptions_view = discord.ui.LayoutView(timeout=None)
            errors += 1
            continue
        del data["messages"]
        data["variants"] = parse_result
        file_path = Path.cwd() / "parsed" / f"{thread.id}.json"
        json_string = json.dumps(data, indent=4)
        async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
            await f.write(json_string)
    await interaction.channel.send(view=exceptions_view)
    await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")

# Parse archive
@bot.tree.command(name="parse_archive", description="Parse the posts in the archive to check for errors")
@app_commands.checks.has_any_role(*HIGHER_ROLES)
async def parse(interaction: discord.Interaction):
    await interaction.response.send_message("Beginning parsing. . .")
    parse_channel_list = [channel for channel in interaction.guild.channels if isinstance(channel, discord.ForumChannel) and (channel.category_id in MAIN_ARCHIVE_CATEGORIES)]
    exceptions_view = discord.ui.LayoutView(timeout=None)
    count = errors = total = 0
    (Path.cwd() / "parsed").mkdir(parents=True, exist_ok=True)

    # Status update message variables
    total_channels = len(parse_channel_list)
    current_channel_index = 1
    embed = discord.Embed(title="Parsing Status",colour=discord.Colour.green())
    reply_channel_obj = interaction.channel
    update_message_obj = await reply_channel_obj.send(embed=embed)

    # Iterate over every thread in the post and parse it
    for channel in parse_channel_list:
        # Update the status message
        embed.description = f"{current_channel_index}/{total_channels} -> {channel.name}"
        await update_message_obj.edit(embed=embed)
        current_channel_index += 1

        # Process every thread in the forum channel
        async for thread in iter_all_threads(channel):
            data = await get_post_data(thread, channel, bot)
            total += 1
            try:
                parse_result = message_parse("\n".join(data["messages"]).split("\n"))
            except Exception as e:
                error_view = await ParserErrorItem.create(bot, thread, e, count)
                if exceptions_view.total_children_count < 40 - error_view._total_count:
                    exceptions_view.add_item(error_view)
                    if exceptions_view.content_length() > 4000:
                        exceptions_view.remove_item(error_view)
                        await interaction.channel.send(view=exceptions_view)
                        error_view.i = 0
                        exceptions_view = discord.ui.LayoutView(timeout=None)
                        exceptions_view.add_item(error_view)
                        count = 0
                    count += 1
                else:
                    await interaction.channel.send(view=exceptions_view)
                    count = 0
                    exceptions_view = discord.ui.LayoutView(timeout=None)
                errors += 1
                continue
            del data["messages"]
            data["variants"] = parse_result
            file_path = Path.cwd() / "parsed" / f"{thread.id}.json"
            json_string = json.dumps(data, indent=4)
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write(json_string)
    await interaction.channel.send(view=exceptions_view)
    await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")

# Restarts the bot and updates code from git if specified.
@bot.tree.command(name="restart", description="Restarts and updates the bot")
@app_commands.describe(do_update="If it should restart without updating (True = update, False = no update)")
@app_commands.checks.has_role(MODERATOR_ID)
async def restart(interaction: discord.Interaction, do_update:bool=True):
    await interaction.response.defer()
    if do_update:
        await interaction.followup.send(embed = discord.Embed(title="Updating...", colour=discord.Colour.yellow()))

        process = await asyncio.create_subprocess_exec(
            "git", "pull", "origin", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return await interaction.followup.send(embed= discord.Embed(title=f"Update failed", description=f"{stderr.decode().strip()}", color=discord.Color.red()))
        await interaction.followup.send(embed= discord.Embed(title=f"Update successful", description=f"{stdout.decode().strip()}", color=discord.Color.green()))

    else:
        await interaction.followup.send(embed=discord.Embed(title="Restarting...", colour=discord.Colour.yellow()))
    executable = sys.executable
    args = [executable] + sys.argv
    os.execv(executable, args)