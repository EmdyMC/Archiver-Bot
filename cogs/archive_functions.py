import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from constants import HIGHER_ROLES, ARCHIVER_CHAT, MODERATOR_ID, ILLEGAL_COMPONENTS, ARCHIVE_UPDATES, SUBMISSIONS_CHANNEL, ARCHIVED_TAG, NON_ARCHIVE_CATEGORIES, ARCHIVED_DESIGNER, SUBMITTER
from utility import TagSelectView

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
        utility_cog = interaction.client.get_cog("Utility")
        if hasattr(self,'embed_title'):
            new_embed = discord.Embed(title=self.embed_title.value, description=self.embed_text.value, colour=discord.Colour.from_str(self.embed_colour.value))
            await self.target_channel.send(content=self.message_text.value, embed=new_embed)
            await utility_cog.log(title="Message sent via bot", message=f"**Message content:**\n{self.message_text.value}\n**Embed content:**\nTitle: {new_embed.title}\nDescription: {new_embed.description}\n\n**By:** {interaction.user.mention}\n\n**In:** {self.target_channel.jump_url}")
        else:
            await self.target_channel.send(content=self.message_text.value)
            await utility_cog.log(title="Message sent via bot", description=f"**Message content:**\n{self.message_text.value}\n\n**By:** {interaction.user.mention}\n\n**In:** {self.target_channel.jump_url}")
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
        utility_cog = interaction.client.get_cog("Utility")
        new_embeds = []
        log_embed = discord.Embed(
            title="Bot Message Edited", 
            description=f"**Message:** {self.target_message.jump_url}\n**By:** {interaction.user.mention}",
            color=discord.Color.yellow()
        )
        content_diff = utility_cog.get_diff_block(self.original_content, new_content)
        if content_diff:
            log_embed.add_field(name="Content Change", value=f"```ansi\n{content_diff}\n```", inline=False)
        try:
            if self.rich_embeds:
                new_embeds = []
                for i, embed in enumerate(self.rich_embeds):
                    cloned = discord.Embed.from_dict(embed.to_dict())
                    if i == 0 and hasattr(self, 'embed_title'):
                        cloned.title = self.embed_title.value
                        cloned.description = self.embed_text.value
                    new_embeds.append(cloned)

                title_diff = utility_cog.get_diff_block(self.rich_embeds[0].title, new_embeds[0].title)
                desc_diff = utility_cog.get_diff_block(self.rich_embeds[0].description, new_embeds[0].description)

                if title_diff:
                    log_embed.add_field(name="Embed Title Change", value=f"```ansi\n{title_diff}\n```", inline=False)
                if desc_diff:
                    log_embed.add_field(name="Embed Description Change", value=f"```ansi\n{desc_diff}\n```", inline=False)
            else:
                pass
            await self.target_message.edit(content=new_content, embeds=new_embeds, attachments=self.original_attachments, allowed_mentions=discord.AllowedMentions.none())
            if log_embed:
                await utility_cog.log_embed(embed=log_embed)
            await interaction.response.send_message(content="Message successfully edited!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(content=f"Error running edit command: {e}", ephemeral=True)
            await utility_cog.log(title="Error running edit command", message=f"{e}")

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
        try:
            target_channel = await interaction.client.fetch_channel(self.target_channel_id)
            target_message = await target_channel.fetch_message(self.target_message_id)
            utility_cog = interaction.client.get_cog("Utility")
            message_content = target_message.content
            if target_message.embeds:
                message_embed_title = target_message.embeds[0].title or None
                message_embed_desc = target_message.embeds[0].description or None
                if message_embed_title:
                    message_content+=f"\n**Title:** {message_embed_title}"
                if message_embed_desc:
                    message_content+=f"\n**Description:** {message_embed_desc}"
            log_message = await utility_cog.log(title="Bot message deleted", message=f"Requested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nContent: {message_content[:1900]}")
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Message deletion request by {self.requester.mention} approved by {interaction.user.mention}\nLog message: {log_message.jump_url}"), view=None)
            await target_message.delete()
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving message deletion request: {e}", ephemeral=True)
            await utility_cog.log(title="Error approving message deletion request", description=f"{e}")
    async def reject_callback(self, interaction: discord.Interaction):
        utility_cog = interaction.client.get_cog("Utility")
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Message deletion request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting message deletion request: {e}", ephemeral=True)
            await utility_cog.log(title="Error rejecting message deletion request", message=f"{e}")
    async def on_timeout(self):
        if self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Message deletion request by {self.requester.mention}"), view=None)

# Publish Box
class PublishBox(discord.ui.Modal, title="Publish Post"):
    def __init__(self, draft: discord.Message):
        super().__init__()
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Choose the channel to publish to. . .",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.forum]
        )
        self.channel = discord.ui.Label(text="Channel to publish to", component=self.channel_select)
        self.add_item(self.channel)
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
        self.update = discord.ui.Select(
            placeholder="Announce Update?",
            options=[discord.SelectOption(label="Yes", value="true"), discord.SelectOption(label="No", value="false", default=True)],
            min_values=1,
            max_values=1,
            custom_id="announce_update"
        )
        self.update_selector = discord.ui.Label(text="Announce Updates?", component=self.update)
        self.add_item(self.update_selector)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        utility_cog = interaction.client.get_cog("Utility")
        channel = self.channel_select.values[0]
        archive_channel = await interaction.client.fetch_channel(channel.id)
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await utility_cog.log(title="Illegal content in post", message=f"```{self.post_content.value[:900]}```\n\nIn: <#{interaction.channel.jump_url}>\nBy: {interaction.user.mention}")
            return
        try:
            thread_with_message = await archive_channel.create_thread(name=self.post_title.value, content=self.post_content.value, allowed_mentions=discord.AllowedMentions.none())
            new_thread = thread_with_message.thread
            interaction.client.last_archive_thread = new_thread
            await utility_cog.log(title="Post made", message=f"Link: {new_thread.jump_url}\nIn: {archive_channel.jump_url}\nBy: {interaction.user.mention}")
            if self.update.values[0] == "true":
                archive_updates = interaction.client.get_channel(ARCHIVE_UPDATES)
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
            await utility_cog.log(title="Error publishing post to archive", description=f"{e}")

# Append to last view
class AppendPrompt(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        self.yes = discord.ui.Button(
            label="Same thread",
            custom_id="yes",
            style=discord.ButtonStyle.green
        )
        self.yes.callback = self.append_to_last
        self.no = discord.ui.Button(
            label="Different thread",
            custom_id="no",
            style=discord.ButtonStyle.gray
        )
        self.no.callback = self.append_to_new
        self.add_item(self.yes)
        self.add_item(self.no)
    async def append_to_new(self, interaction: discord.Interaction):
        append_modal = AppendBox(draft=self.message)
        await interaction.response.send_modal(append_modal)
    async def append_to_last(self, interaction: discord.Interaction):
        await interaction.response.defer()
        archive_thread = getattr(interaction.client, "last_archive_thread", None)
        utility_cog = interaction.client.get_cog("Utility")
        try:
            appended_post = await archive_thread.send(content=self.message.content, allowed_mentions=discord.AllowedMentions.none())
            await utility_cog.log(title="Post appended", message=f"**{appended_post.content[:900]}**\n\nIn: <#{archive_thread.id}>\n\nBy: {interaction.user.mention}")
            await interaction.followup.send(content="Post published", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error appending post to archive {e}", ephemeral=True)
            await utility_cog.log(title="Error appending post to archive", message=f"{e}")

# Append Box
class AppendBox(discord.ui.Modal, title="Append to post"):
    def __init__(self, draft: discord.Message):
        super().__init__()
        self.thread_select = discord.ui.ChannelSelect(
            placeholder="Choose the thread to append post to. . .",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.public_thread]
        )
        self.thread = discord.ui.Label(text="Select post to append to", component=self.thread_select)
        self.add_item(self.thread)
        self.post_content = discord.ui.TextInput(
            label="Post Content",
            default=draft.content,
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.post_content)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        utility_cog = interaction.client.get_cog("Utility")
        archive_thread = interaction.client.get_channel(self.thread_select.values[0].id)
        if archive_thread.parent.category.id in NON_ARCHIVE_CATEGORIES:
            await interaction.followup.send(content="The given thread ID is not in an archive forum", ephemeral=True)
            return
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await utility_cog.log(title="Illegal content in post", message=f"```{self.post_content.value}```\n\nIn: <#{interaction.channel_id}>\nBy: {interaction.user.mention}")
            return
        try:
            appended_post = await archive_thread.send(content=self.post_content.value, allowed_mentions=discord.AllowedMentions.none())
            await utility_cog.log(title="Post appended", message=f"**{appended_post.content[:900]}**\n\nIn: <#{archive_thread.id}>\n\nBy: {interaction.user.mention}")
            await interaction.followup.send(content="Post published", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error appending post to archive {e}", ephemeral=True)
            await utility_cog.log(title="Error appending post to archive", description=f"{e}")

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
            archiver_chat = interaction.client.get_channel(ARCHIVER_CHAT)
            embed=discord.Embed(title="Thread title change request", description=f"{interaction.user.mention} wishes to edit the title of {self.post.jump_url}\nFrom: {self.post.name}\nTo: {self.new_title.value}")
            view = EditTitleApproval(post=self.post, requester=interaction.user, title=self.new_title.value)
            approval_message = await archiver_chat.send(embed=embed, view=view)
            view.approval_message = approval_message
            await interaction.response.send_message(content="Thread title change request sent", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occured: {e}", ephemeral=True)

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
        utility_cog = interaction.client.get_cog("Utility")
        try:
            await utility_cog.log(title="Thread title updated", message=f"From: {self.post.name}\nTo: {self.title}\nRequested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nThread: {self.post.jump_url}")
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Thread title change request by {self.requester.mention} approved by {interaction.user.mention}\nFrom: {self.post.name}\nTo: {self.title}\nThread: {self.post.jump_url}"), view=None)
            await self.post.edit(name=self.title, archived=False)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving thread title change request: {e}", ephemeral=True)
            await utility_cog.log(title="Error approving thread title change request", message=f"{e}")
    async def reject_callback(self, interaction: discord.Interaction):
        utility_cog = interaction.client.get_cog("Utility")
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Thread title change request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting thread title change request: {e}", ephemeral=True)
            await utility_cog.log(title="Error rejecting thread title change request", description=f"{e}")
    async def on_timeout(self):
        if self.approval_message and self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Thread title change request by {self.requester.mention}"), view=None)

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
        utility_cog = interaction.client.get_cog("Utility")
        try:
            target_post = await interaction.client.fetch_channel(self.target_post_id)
            parsed_file = Path.cwd() / "parsed" / f"{self.target_post_id}.json"
            if parsed_file.exists():
                parsed_file.unlink()
            await utility_cog.log(title="Thread deleted", message=f"Requested by: {self.requester.mention}\nApproved by: {interaction.user.mention}\nThread: {target_post.name}\n In: {target_post.parent.jump_url}")
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="✅ Approved",description=f"Thread deletion request by {self.requester.mention} approved by {interaction.user.mention}\nThread: {target_post.name} in {target_post.parent.jump_url}"), view=None)
            await target_post.delete()
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error approving thread deletion request: {e}", ephemeral=True)
            await utility_cog.log(title="Error approving thread deletion request", message=f"{e}")
    async def reject_callback(self, interaction: discord.Interaction):
        utility_cog = interaction.client.get_cog("Utility")
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=discord.Embed(title="❌ Rejected", description=f"Thread deletion request by {self.requester.mention} rejected by {interaction.user.mention}"), view=None)
            self.stop()
        except Exception as e:
            await interaction.followup.send(content=f"Error rejecting thread deletion request: {e}", ephemeral=True)
            await utility_cog.log(title="Error rejecting thread deletion request", message=f"{e}")
    async def on_timeout(self):
        if self.approval_message:
            await self.approval_message.edit(embed=discord.Embed(title="⌛ Timed Out",description=f"Thread deletion request by {self.requester.mention}"), view=None)

class ArchiveFunctions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Messsage send
    @app_commands.command(name="send", description="Send a message via the bot to the current channel")
    @app_commands.describe(has_embed="Enable the embed field")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def send(self, interaction: discord.Interaction, has_embed:bool=False):
        send_modal = SendBox(has_embed)
        send_modal.target_channel = interaction.channel
        await interaction.response.send_modal(send_modal)

    # Message edit
    @app_commands.context_menu(name="Edit")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def edit(self, interaction: discord.Interaction, message: discord.Message):
        if message.author==interaction.client.user:
            existing_embeds = [embed for embed in message.embeds if embed.type != "link"] or None
            existing_attachments = message.attachments if message.attachments else None
            edit_modal = EditBox(original_content=message.content, original_embeds=existing_embeds, original_attachments=existing_attachments, target_message=message)
            await interaction.response.send_modal(edit_modal)
        else:
            await interaction.response.send_message(content="The given message is not one made by Archiver Bot, editing is not possible", ephemeral=True)

    # Message delete
    @app_commands.context_menu(name="Delete")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def delete(self, interaction: discord.Interaction, message: discord.Message):
        if message.author!=interaction.client.user:
            await interaction.response.send_message("You can only delete bot messages with this command", ephemeral=True)
        else:
            role_ids = [role.id for role in interaction.user.roles]
            archiver_chat = interaction.client.get_channel(ARCHIVER_CHAT)
            embed=discord.Embed(title="Message deletion request", description=f"{interaction.user.mention} wishes to delete {message.jump_url}")
            view = DeleteMessageApprovalView(target_message_id=message.id, target_channel_id=interaction.channel_id, requester=interaction.user)
            approval_message = await archiver_chat.send(embed=embed, view=view)
            view.approval_message = approval_message
            if MODERATOR_ID in role_ids:
                await interaction.response.send_message(content="Message deletion request sent. . . you know you don't need to use the bot to delete stuff right?", ephemeral=True)
            else:
                await interaction.response.send_message(content="Message deletion request sent", ephemeral=True)

    # Publish post
    @app_commands.context_menu(name="Publish post")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def publish(self, interaction: discord.Interaction, message: discord.Message):
        publish_modal = PublishBox(draft=message)
        await interaction.response.send_modal(publish_modal)

    # Append post
    @app_commands.context_menu(name="Append post")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def append(self, interaction: discord.Interaction, message: discord.Message):
        last_thread = getattr(interaction.client, "last_archive_thread", None)
        if last_thread is None:
            append_modal = AppendBox(draft=message)
            await interaction.response.send_modal(append_modal)
        else:
            prompt = AppendPrompt(message=message)
            await interaction.response.send_message(content=f"Do you want to append to **{last_thread.name}** or a different thread?", view=prompt, ephemeral=True)

    # Delete post
    @app_commands.command(name="delete_post", description="remove a post from the archive")
    @app_commands.describe(thread="Post")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def delete_post(self, interaction: discord.Interaction, thread: discord.Thread):
        archiver_chat = interaction.client.get_channel(ARCHIVER_CHAT)
        embed=discord.Embed(title="Thread deletion request", description=f"{interaction.user.mention} wishes to delete {thread.jump_url}")
        view = DeleteThreadApprovalView(target_post_id=thread.id, requester=interaction.user)
        approval_message = await archiver_chat.send(embed=embed, view=view)
        view.approval_message = approval_message
        await interaction.response.send_message(content="Thread deletion request sent", ephemeral=True)
        
    # Edit post title
    @app_commands.command(name="edit_post_title", description="Edit the title of an archive post")
    @app_commands.describe(thread="Post")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def edit_post(self, interaction: discord.Interaction, thread: discord.Thread):
        edit_modal = EditTitleBox(post=thread)
        await interaction.response.send_modal(edit_modal)

    # Grant role command
    @app_commands.command(name="grant_role", description="Bestow the archived designer or submitter role on someone")
    @app_commands.describe(member="The designer")
    @app_commands.choices(role=[app_commands.Choice(name="Archived Designer", value=1), app_commands.Choice(name="Submitter", value=2)])
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def archived_designer(self, interaction: discord.Interaction, member: discord.Member, role: app_commands.Choice[int]):
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

async def setup(bot: commands.Bot):
    await bot.add_cog(ArchiveFunctions(bot))