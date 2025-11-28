from functions import *

# Send box
class SendBox(discord.ui.Modal, title="Send Message"):
    def __init__(self, has_embed: bool):
        super().__init__()
        self.message_text = discord.ui.TextInput(
            label="Message content:", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.message_text)
        if has_embed:
            self.embed_title = discord.ui.TextInput(
                label="Embed title:",
                style=discord.TextStyle.short,
                required=False
            )
            self.embed_text = discord.ui.TextInput(
                label="Embed description:",
                style=discord.TextStyle.long,
                required=False
            )
            self.embed_colour = discord.ui.TextInput(
                label="Embed colour:",
                style=discord.TextStyle.short,
                default="#FFFFFF",
                required=False
            )
            self.add_item(self.embed_title)
            self.add_item(self.embed_text)
            self.add_item(self.embed_colour)
    async def on_submit(self, interaction: discord.Interaction):
        logs = bot.get_channel(LOG_CHANNEL)
        if hasattr(self,'embed_title'):
            new_embed = discord.Embed(title=self.embed_title.value, description=self.embed_text.value, colour=discord.Colour.from_str(self.embed_colour.value))
            await self.target_channel.send(content=self.message_text.value, embed=new_embed)
            await logs.send(embed=discord.Embed(title="Message sent via bot", description=f"**Message content:**\n{self.message_text.value}\n**Embed content:**\nTitle: {new_embed.title}\nDescription: {new_embed.description}\n\n**By:** {interaction.user.mention}\n\n**In:** {self.target_channel.name}"))
        else:
            await self.target_channel.send(content=self.message_text.value)
            await logs.send(embed=discord.Embed(title="Message sent via bot", description=f"**Message content:**\n{self.message_text.value}\n\n**By:** {interaction.user.mention}\n\n**In:** {self.target_channel.name}"))
        await interaction.response.send_message(content="Message successfully sent!", ephemeral=True)

# Edit box
class EditBox(discord.ui.Modal, title="Edit Message"):
    def __init__(self, original_content: str, target_message: discord.Message, original_embeds: list[discord.Embed] = None, original_attachments: list[discord.Attachment] = None):
        super().__init__()
        self.original_embeds = original_embeds or []
        self.original_content = original_content
        self.original_attachments = original_attachments or []
        self.target_message = target_message
        self.message_text = discord.ui.TextInput(
            label="Message content:", 
            default=original_content, 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.message_text)
        self.rich_embeds = [embed for embed in self.original_embeds if embed.type == 'rich']
        if self.rich_embeds:
            first_embed = self.rich_embeds[0]
            self.embed_title = discord.ui.TextInput(
                label="Embed title:",
                default=first_embed.title,
                style=discord.TextStyle.short,
                required=False
            )
            self.embed_text = discord.ui.TextInput(
                label="Embed description:",
                default=first_embed.description,
                style=discord.TextStyle.long,
                required=False
            )
            self.add_item(self.embed_title)
            self.add_item(self.embed_text)
                
    async def on_submit(self, interaction: discord.Interaction):
        new_content = self.message_text.value
        logs = bot.get_channel(LOG_CHANNEL)
        new_embeds = []
        log_embed = None
        try:
            if not self.rich_embeds:
                log_embed = discord.Embed(title="Bot message edited", description=f"**Before:**\n{self.original_content}\n**After:**\n{new_content}\n\n**By:** {interaction.user.mention}")
            else:
                for i, embed in enumerate(self.rich_embeds):
                    cloned = discord.Embed.from_dict(embed.to_dict())
                    if i == 0 and hasattr(self, 'embed_title'):
                        cloned.title = self.embed_title.value
                        cloned.description = self.embed_text.value
                    new_embeds.append(cloned)
                log_embed = discord.Embed(title="Bot message edited", description=f"**Before:**\nContent: {self.original_content}\nEmbed title: {self.rich_embeds[0].title}\nDescription: {self.rich_embeds[0].description}\n**After:**\nContent: {new_content}\nEmbed title: {new_embeds[0].title}\nDescription: {new_embeds[0].description}\n\n**By:** {interaction.user.mention}")
            
            await self.target_message.edit(content=new_content, embeds=new_embeds, attachments=self.original_attachments)
            if log_embed:
                await logs.send(embed=log_embed)
            await interaction.response.send_message(content="Message successfully edited!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(content=f"Error running edit command: {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error running edit command", description=f"{e}"))      

# Channel selector view
class PublishChannelSelectView(discord.ui.View):
    def __init__(self, draft):
        super().__init__()
        self.draft = draft
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Choose the channel to publish to. . .",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.forum]
        )
        self.channel_select.callback = self.select_callback
        self.add_item(self.channel_select)
    async def select_callback(self, interaction: discord.Interaction):
        selected_channel = self.channel_select.values[0]
        publish_modal = PublishBox(draft=self.draft, channel=selected_channel)
        await interaction.response.send_modal(publish_modal)

# Publish Box
class PublishBox(discord.ui.Modal, title="Publish Post"):
    def __init__(self, draft: discord.Message, channel: discord.ForumChannel):
        super().__init__()
        self.channel = channel
        self.post_title = discord.ui.TextInput(
            label="Post Title", 
            default=draft.channel.name,
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.post_title)
        self.post_content = discord.ui.TextInput(
            label="Post Content",
            default=draft.content,
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.post_content)
        self.update = discord.ui.TextInput(
            label="Announce update",
            placeholder="Leave empty for False, write something for True",
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.update)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        archive_channel = await bot.fetch_channel(self.channel.id)
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Illegal content in post", description=f"```{self.post_content.value[:900]}```\n\nIn: <#{interaction.channel.jump_url}>\nBy: {interaction.user.mention}"))
            return
        try:
            thread_with_message = await archive_channel.create_thread(name=self.post_title.value, content=self.post_content.value)
            new_thread = thread_with_message.thread
            await logs.send(embed=discord.Embed(title="Post made", description=f"Link: {new_thread.jump_url}\nIn: {archive_channel.jump_url}\nBy: {interaction.user.mention}"))
            if bool(self.update.value.strip()):
                archive_updates = bot.get_channel(ARCHIVE_UPDATES)
                await archive_updates.send(content=f"Archived {new_thread.jump_url} in {archive_channel.jump_url}\n\n[Submission thread]({interaction.channel.jump_url})")
            # Handle reposting from the archive and not a submission thread
            if interaction.channel.parent.id == SUBMISSIONS_CHANNEL:
                await interaction.channel.edit(applied_tags=[interaction.channel.parent.get_tag(ARCHIVED_TAG)])
                link = await interaction.channel.send(content=f"Submission archived as {new_thread.jump_url} in {archive_channel.jump_url}")
                await link.pin()
            available_tags = new_thread.parent.available_tags
            await interaction.followup.send(content="Set post tags. . .", view=TagSelectView(tags=available_tags, thread=new_thread), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error publishing post to archive {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error publishing post to archive", description=f"{e}"))

# Channel selector view
class AppendThreadSelectView(discord.ui.View):
    def __init__(self, draft):
        super().__init__()
        self.draft = draft
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Choose the thread to append post to. . .",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.public_thread]
        )
        self.channel_select.callback = self.select_callback
        self.add_item(self.channel_select)
    async def select_callback(self, interaction: discord.Interaction):
        selected_thread = self.channel_select.values[0]
        append_modal = AppendBox(draft=self.draft, channel=selected_thread)
        await interaction.response.send_modal(append_modal)

# Append Box
class AppendBox(discord.ui.Modal, title="Append to post"):
    def __init__(self, draft: discord.Message, thread: discord.Thread):
        super().__init__()
        self.thread = thread
        self.post_content = discord.ui.TextInput(
            label="Post Content",
            default=draft.content,
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.post_content)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        archive_thread = bot.get_channel(self.thread.id)
        if archive_thread.parent.category.id in NON_ARCHIVE_CATEGORIES:
            await interaction.followup.send(content="The given thread ID is not in an archive forum", ephemeral=True)
            return
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Illegal content in post", description=f"```{self.post_content.value}```\n\nIn: <#{interaction.channel_id}>\nBy: {interaction.user.mention}"))
            return
        try:
            appended_post = await archive_thread.send(content=self.post_content.value)
            await logs.send(embed=discord.Embed(title="Post appended", description=f"**{appended_post.content[:900]}**\n\nIn: <#{archive_thread.id}>\n\nBy: {interaction.user.mention}"))
            await interaction.followup.send(content="Post published", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error appending post to archive {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error appending post to archive", description=f"{e}"))

# Edit Title Box
class EditTitleBox(discord.ui.Modal, title="Edit Post Title"):
    def __init__(self, post=discord.Thread):
        super().__init__()
        self.post = post
        self.new_title = discord.ui.TextInput(
            label="Title",
            default=post.name,
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.new_title)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            archiver_chat = bot.get_channel(ARCHIVER_CHAT)
            embed=discord.Embed(title="Thread title change request", description=f"{interaction.user.mention} wishes to edit the title of {self.post.jump_url}\nFrom: {self.post.name}\nTo: {self.new_title.value}")
            view = EditTitleApproval(post=self.post, requester=interaction.user, title=self.new_title.value)
            approval_message = await archiver_chat.send(embed=embed, view=view)
            view.approval_message = approval_message
            await interaction.response.send_message(content="Thread title change request sent", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occured: {e}", ephemeral=True)
