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
        self.post_title = discord.ui.TextInput(
            label="Post Title", 
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.post_title)
        self.designers = discord.ui.TextInput(
            label="Designers", 
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.designers)
        self.credits = discord.ui.TextInput(
            label="Credits", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.credits)
        self.version = discord.ui.TextInput(
            label="Versions", 
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.version)
        self.rates = discord.ui.TextInput(
            label="Rates", 
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.rates)
        self.links = discord.ui.TextInput(
            label="Video Links", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.links)
        self.files = discord.ui.TextInput(
            label="Files", 
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.files)
        self.description = discord.ui.TextInput(
            label="Description", 
            style=discord.TextStyle.long,
            required=True
        )
        self.add_item(self.description)
        self.positives = discord.ui.TextInput(
            label="Positives", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.positives)
        self.negatives = discord.ui.TextInput(
            label="Negatives", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.negatives)
        self.specs = discord.ui.TextInput(
            label="Design Specifications", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.specs)
        self.instructions = discord.ui.TextInput(
            label="Instructions", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.instructions)
        self.figures = discord.ui.TextInput(
            label="Figures", 
            style=discord.TextStyle.long,
            required=False
        )
        self.add_item(self.figures)