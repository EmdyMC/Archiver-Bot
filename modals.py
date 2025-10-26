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
    def __init__(self, original_content: str, original_embeds: list[discord.Embed] = None, original_attachments: list[discord.Attachment] = None):
        super().__init__()
        self.original_embeds = original_embeds or []
        self.original_content = original_content
        self.original_attachments = original_attachments or []
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

# Publish Box
class PublishBox(discord.ui.Modal, title="Publish Post"):
    def __init__(self, draft: discord.Message):
        super().__init__()
        self.channel = discord.ui.TextInput(
            label=f"Channel ID", 
            placeholder="The ID of the forum channel to post in",
            style=discord.TextStyle.short,
            required=True
        )
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
        try:
            channel_id = int(self.channel.value)
        except ValueError:
            await interaction.followup.send(content="Channel ID must be a valid number.", ephemeral=True)
            return
        archive_channel = bot.get_channel(channel_id)
        if not isinstance(archive_channel, discord.ForumChannel) or archive_channel.category.id in NON_ARCHIVE_CATEGORIES:
            await interaction.followup.send(content="The given channel ID is not an archive forum", ephemeral=True)
            return
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Illegal content in post", description=f"```{self.post_content.value[:900]}```\n\nIn: <#{interaction.channel.jump_url}>\nBy: {interaction.user.mention}"))
            return
        try:
            new_thread, start_message = await archive_channel.create_thread(name=self.post_title.value, content=self.post_content.value)
            await logs.send(embed=discord.Embed(title="Post made", description=f"Link: {new_thread.jump_url}\nIn: <#{archive_channel.jump_url}>\nBy: {interaction.user.mention}"))
            if bool(self.update.value.strip()):
                archive_updates = bot.get_channel(ARCHIVE_UPDATES)
                await archive_updates.send(content=f"Archived {new_thread.jump_url} in {archive_channel.jump_url}\n\n[Submission thread]({interaction.channel.jump_url})")
            await interaction.channel.edit(applied_tags=[interaction.channel.parent.get_tag(ARCHIVED_TAG)])
            link = await interaction.channel.send(content=f"Submission archived as {new_thread.jump_url} in {archive_channel.jump_url}")
            await link.pin()
            available_tags = new_thread.parent.available_tags
            await interaction.followup.send(content="Set post tags. . .", view=TagSelectView(tags=available_tags, thread=new_thread), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error publishing post to archive {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error publishing post to archive", description=f"{e}"))

class AppendBox(discord.ui.Modal, title="Append to post"):
    def __init__(self, draft: discord.Message):
        super().__init__()
        self.thread = discord.ui.TextInput(
            label="Thread ID", 
            placeholder="The ID of the archive thread to post in",
            style=discord.TextStyle.short,
            required=True
        )
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
        logs = bot.get_channel(LOG_CHANNEL)
        try:
            thread_id = int(self.thread.value)
        except ValueError:
            await interaction.followup.send(content="Thread ID must be a valid number.", ephemeral=True)
            return
        archive_thread = bot.get_channel(thread_id)
        if not isinstance(archive_thread, discord.Thread):
            await interaction.followup.send(content="The given ID is not a thread", ephemeral=True)
            return
        if not isinstance(archive_thread.parent, discord.ForumChannel) or archive_thread.parent.category.id in NON_ARCHIVE_CATEGORIES:
            await interaction.followup.send(content="The given thread ID is not in an archive forum", ephemeral=True)
            return
        if any(phrase in self.post_content.value for phrase in ILLEGAL_COMPONENTS):
            await interaction.followup.send(content="That message content is not allowed", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Illegal content in post", description=f"```{self.post_content.value}```\n\nIn: <#{interaction.channel_id}>\nBy: {interaction.user.mention}"))
            return
        try:
            appended_post = await archive_thread.send(content=self.post_content.value)
            await logs.send(embed=discord.Embed(title="Post appended", description=f"**{appended_post.content[:900]}**\n\nIn: <#{thread_id}>\n\nBy: {interaction.user.mention}"))
            await interaction.followup.send(content="Post published", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(content=f"Error appending post to archive {e}", ephemeral=True)
            await logs.send(embed=discord.Embed(title="Error appending post to archive", description=f"{e}"))
