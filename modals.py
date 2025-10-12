from init import *

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
        self.original_content = original_content
        if original_embed:
            self.embed_title = discord.ui.TextInput(
                label="Embed title:",
                default=original_embed.title,
                style=discord.TextStyle.short,
                required=False
            )
            self.embed_text = discord.ui.TextInput(
                label="Embed description:",
                default=original_embed.description,
                style=discord.TextStyle.long,
                required=False
            )
            self.add_item(self.embed_title)
            self.add_item(self.embed_text)

    async def on_submit(self, interaction: discord.Interaction):
        new_content=self.message_text.value
        logs = bot.get_channel(LOG_CHANNEL)
        if hasattr(self,'embed_title'):
            new_embed = self.original_embed
            new_embed.description = self.embed_text.value
            new_embed.title = self.embed_title.value
            await self.target_message.edit(embed=new_embed)
            await logs.send(embed=discord.Embed(title="Bot embed edited", description=f"**Before:**\nTitle: {self.original_embed.title}\nDescription: {self.original_embed.description}\n**After:**\nTitle: {new_embed.title}\nDescription: {new_embed.description}\n\n**By:** {interaction.user.mention}"))
        await self.target_message.edit(content=new_content)
        await interaction.response.send_message(content="Message successfully edited!", ephemeral=True)
        await logs.send(embed=discord.Embed(title="Bot message edited", description=f"**Before:**\n{self.original_content}\n**After:**\n{new_content}\n\n**By:** {interaction.user.mention}"))

# Draft box
class DraftBox(discord.ui.Modal, title="Draft Post"):
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel
        self.post_title = discord.ui.TextInput(
            label="Post Title", 
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.post_title)
        self.post_content = discord.ui.TextInput(
            label="Post Content",
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.post_content)
    async def on_submit(self, interaction: discord.Interaction):
        logs = bot.get_channel(LOG_CHANNEL)
        await self.channel.send(content=f"# Title: {self.post_title.value}\n{self.post_content.value}")
        await logs.send(embed=discord.Embed(title="Draft made", description=f"For: {self.post_title.value}\n\nIn: <#{self.channel.id}>\n\nBy: {interaction.user.mention}"))
        await interaction.response.send_message(content="Draft sent", ephemeral=True)

class PublishBox(discord.ui.Modal, title="Publish Post"):
    def __init__(self, draft: discord.Message):
        super().__init__()
        draft_tuple = draft.content.partition('\n')
        draft_title = draft_tuple[0].removeprefix('# Title: ')
        draft_content = draft_tuple[2]
        self.channel = discord.ui.TextInput(
            label="Channel ID", 
            placeholder="The ID of the forum channel to post in",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.channel)
        self.post_title = discord.ui.TextInput(
            label="Post Title", 
            default=draft_title,
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.post_title)
        self.post_content = discord.ui.TextInput(
            label="Post Content",
            default=draft_content,
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.post_content)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        logs = bot.get_channel(LOG_CHANNEL)
        archive_channel = bot.get_channel(int(self.channel.value))
        new_thread, start_message = await archive_channel.create_thread(name=self.post_title.value, content=self.post_content.value)
        await logs.send(embed=discord.Embed(title="Post made", description=f"### {new_thread.name}\n\nIn: <#{self.channel.value}>\n\nBy: {interaction.user.mention}"))
        await interaction.followup.send(content="Post published", ephemeral=True)