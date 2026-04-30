import discord
import difflib
import re
import aiofiles
import json 
import datetime
from pathlib import Path
from discord.ext import commands
from discord import app_commands
from typing import Type
from parser import set_contributor_username_lookup, message_parse, reset_contributor_username_lookup
from constants import ARCHIVER_ID, LOG_CHANNEL, MENTION_RE, HIGHER_ROLES, NON_ARCHIVE_CATEGORIES, MAIN_ARCHIVE_CATEGORIES

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
        async def edit(interaction: discord.Interaction[commands.Bot]):
            if interaction.user.get_role(ARCHIVER_ID) is None:
                raise app_commands.errors.MissingRole(ARCHIVER_ID)
            await interaction.response.send_modal(PostEditAndParseModal(self.bot, message, interaction.message, self.i))
        return edit

class PostEditModal(discord.ui.Modal, title="Edit Post"):
    def __init__(self, bot: commands.Bot, message: discord.Message):
        super().__init__()
        self.bot = bot
        self.message = message
        self.change_notes = discord.ui.TextInput(label="Change Notes", style=discord.TextStyle.long, required=False)
        self.message_input = discord.ui.TextInput(label="Edit Raw Post", style=discord.TextStyle.paragraph, default=message.content)
        self.add_item(self.change_notes)
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction[commands.Bot]):
        assert isinstance(self.message.channel, discord.Thread)
        await self.message.edit(content=self.message_input.value)
        logs = interaction.client.get_channel(LOG_CHANNEL)
        await logs.send(view=ContainedTextView(f"**Updated** {self.message.jump_url}:\n{self.change_notes.value}\nBy: {interaction.user.mention}\n```diff\n{"\n".join(difflib.unified_diff(self.message.content.splitlines(), self.message_input.value.splitlines(), lineterm="")) or "No change."}```"), allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.defer()

class ContainedTextView(discord.ui.LayoutView):
    def __init__(self, text: str, color: discord.Color=discord.Color.yellow()):
        super().__init__()
        self.container = discord.ui.Container(discord.ui.TextDisplay(text), accent_color=color)
        self.add_item(self.container)

class PostEditAndParseModal(PostEditModal):
    def __init__(self, bot: commands.Bot, message: discord.Message, parse_response_message: discord.Message, i: int):
        super().__init__(bot, message)
        self.parse_response_message = parse_response_message
        self.i = i
    
    async def on_submit(self, interaction: discord.Interaction[commands.Bot]):
        await super().on_submit(interaction)
        parser_cog = interaction.client.get_cog("Parser")
        data = await parser_cog.get_post_data(self.message.thread, self.message.channel.parent, self.bot)
        username_lookup = await parser_cog.build_username_lookup_from_messages(data["messages"])
        lookup_token = set_contributor_username_lookup(username_lookup)

        try:
            parse_result = message_parse("\n".join(data["messages"]).split("\n"))
        except Exception as e:
            new_item = await ParserErrorItem.create(self.bot, self.message.thread, e, self.i)
            new_view = discord.ui.LayoutView()
            new_view.add_item(new_item)
            await self.parse_response_message.channel.send(view=new_view)
            return
        finally:
            reset_contributor_username_lookup(lookup_token)
        
        new_item = discord.ui.TextDisplay(f"{self.message.jump_url}: Parse successful.")
        new_view = discord.ui.LayoutView()
        new_view.add_item(new_item)
        await self.parse_response_message.channel.send(view=new_view)
        
        del data["messages"]
        data["variants"] = parse_result
        parsed_path = Path.cwd() / "parsed" / f"{self.message.thread.id}.json"
        
        with open(parsed_path, "w") as f:
            json.dump(data, f, indent=4)

class Parser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_post_metadata(self, thread: discord.Thread, channel: discord.ForumChannel, bot: commands.Bot) -> dict[str, str|list[str]]:
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

    # Discord id->username helper
    async def get_username_from_id(self, user_id: int) -> str | None:
        """Finds the name and ID of a user using their user ID"""
        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None

        return user.display_name if hasattr(user, "display_name") else user.name


    async def build_username_lookup_from_messages(self, messages: list[str]) -> dict[int, str]:
        """Builds a per-request cache of user_id -> username from message mentions."""
        user_ids: set[int] = set()
        for message in messages:
            for match in MENTION_RE.finditer(message):
                user_ids.add(int(match.group(1)))

        username_lookup: dict[int, str] = {}
        for user_id in user_ids:
            username = await self.get_username_from_id(user_id)
            if username:
                username_lookup[user_id] = username

        return username_lookup

    async def get_post_data(self, thread: discord.Thread, channel: discord.ForumChannel, bot: commands.Bot) -> dict[str, str|list[str]]:
        #Gets the metadata for the post along with all the post messages
        # Add all the post messages to the metadata
        metadata = self.get_post_metadata(thread, channel, bot)
        async for message in thread.history(limit=None, oldest_first=True):
            # Add it if the message exists and is not a discord message (pin/rename thread)
            if message.content and message.type == discord.MessageType.default:
                metadata["messages"].append(message.content)
        return metadata

    async def iter_all_threads(self, channel: discord.ForumChannel):
        #Iterates over all threads, active or not
        for thread in channel.threads:
            yield thread

        async for thread in channel.archived_threads(limit=None):
            yield thread

    # Parse given threads to json and write to file
    async def parse_threads_stream(self, thread_iter, interaction: discord.Interaction, reply_to_channel=True):
        exceptions_view = discord.ui.LayoutView(timeout=None)
        errors = total = 0

        (Path.cwd() / "parsed").mkdir(parents=True, exist_ok=True)

        async for thread in thread_iter:
            total += 1
            data = await self.get_post_data(thread=thread, channel=thread.parent, bot=interaction.client)
            username_lookup = await self.build_username_lookup_from_messages(data["messages"])
            lookup_token = set_contributor_username_lookup(username_lookup)

            try:
                parse_result = message_parse("\n".join(data["messages"]).split("\n"))
            except Exception as e:
                error_view = await ParserErrorItem.create(self.bot, thread, e, 1)
                exceptions_view.add_item(error_view)
                if reply_to_channel:
                    await interaction.channel.send(view=exceptions_view)
                    exceptions_view = discord.ui.LayoutView(timeout=None)
                errors += 1
                continue
            finally:
                reset_contributor_username_lookup(lookup_token)

            tags_serializable = []
            for tag in thread.applied_tags:
                tag_dict = {
                    "id": tag.id,
                    "name": tag.name,
                }
                tags_serializable.append(tag_dict)

            json_data = {
                "parsed_at": datetime.utcnow().isoformat(),
                "channel_id": str(thread.parent_id),
                "thread_id": str(thread.id),
                "slug": self.slugify(thread.name),
                "title": thread.name,
                "tags": tags_serializable,
                "post_data": parse_result
            }

            file_path = Path.cwd() / "parsed" / f"{thread.id}.json"
            json_string = json.dumps(json_data, indent=4)
            async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
                await f.write(json_string)

        return errors, total

    def slugify(self, text: str):
        # Lowercase
        text = text.lower()
        # Replace spaces and underscores with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        # Remove all non-alphanumeric characters except hyphens
        text = re.sub(r'[^a-z0-9-]', '', text)
        # Remove consecutive hyphens
        text = re.sub(r'-{2,}', '-', text)
        # Remove leading/trailing hyphens
        text = text.strip('-')
        return text
    
    #Parse post
    @app_commands.command(name="parse_post", description="Parse the selected post and check for errors")
    @app_commands.describe(thread="The post to be parsed")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def parse_post(self, interaction: discord.Interaction, thread: discord.Thread):
        if thread.parent.category_id in NON_ARCHIVE_CATEGORIES:
            await interaction.response.send_message("That is not an archive thread, it cannot be parsed.", ephemeral=True)
            return

        # Wrap the single thread in an async generator
        async def single_thread_gen():
            yield thread

        errors, total = await self.parse_threads_stream(single_thread_gen(), interaction, reply_to_channel=False)
        await interaction.response.send_message(content=f"Parsed {thread.name} successfully.\nErrors: {errors}/{total}", ephemeral=True)

    # Parse channel
    @app_commands.command(name="parse_channel", description="Parse the posts in a selected channel and check for errors")
    @app_commands.describe(channel="The channel to be parsed")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def parse_channel(self, interaction: discord.Interaction, channel: discord.ForumChannel):
        if channel.category_id in NON_ARCHIVE_CATEGORIES:
            await interaction.response.send_message("That is not an archive channel, it cannot be parsed.", ephemeral=True)
            return

        await interaction.response.send_message("Beginning parsing. . .")
        errors, total = await self.parse_threads_stream(self.iter_all_threads(channel), interaction)
        await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")


    # Parse archive
    @app_commands.command(name="parse_archive", description="Parse the posts in the archive and check for errors")
    @app_commands.checks.has_any_role(*HIGHER_ROLES)
    async def parse_archive(self, interaction: discord.Interaction):
        await interaction.response.send_message("Beginning parsing. . .")
        parse_channel_list = [
            channel for channel in interaction.guild.channels 
            if isinstance(channel, discord.ForumChannel) and (channel.category_id in MAIN_ARCHIVE_CATEGORIES)
        ]

        parsed_path = Path.cwd() / "parsed"
        for file in parsed_path.glob("*.json"):
            try:
                file.unlink()
            except Exception as e:
                await interaction.channel.send(f"Failed to delete {file}: {e}")

        errors = total = 0
        total_channels = len(parse_channel_list)
        current_channel_index = 1
        embed = discord.Embed(title="Parsing Status", colour=discord.Colour.green())
        update_message_obj = await interaction.channel.send(embed=embed)

        for channel in parse_channel_list:
            embed.description = f"{current_channel_index}/{total_channels} -> {channel.name}"
            await update_message_obj.edit(embed=embed)
            current_channel_index += 1

            channel_errors, channel_total = await self.parse_threads_stream(self.iter_all_threads(channel), interaction)
            errors += channel_errors
            total += channel_total

        await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Parser(bot))