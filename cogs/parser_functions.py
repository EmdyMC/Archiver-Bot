import discord
import difflib
import re
import aiofiles
import aiohttp
import json
import os
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pymongo import MongoClient
from pathlib import Path
from discord.ext import commands
from discord import app_commands
from typing import Any, Type
from parser import (
    message_parse,
    parse_crosspost,
    reset_contributor_username_lookup,
    set_contributor_username_lookup,
)
from dimensions import DimensionResolver, apply_dimensions
from thumbnails import apply_thumbnails
from links import DiscordTarget, discord_target, iter_discord_links, new_discord_link
from MessageDict import DiscordLink
from constants import ARCHIVER_ID, LOG_CHANNEL, MENTION_RE, HIGHER_ROLES, PARSE_ROLES, NON_ARCHIVE_CATEGORIES, MAIN_ARCHIVE_CATEGORIES, DATABASE_NAME, COLLECTION_NAME
MONGO_URI = os.getenv("MONGO_URI")

class DiscordLinkResolver:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._targets: dict[DiscordTarget, asyncio.Task] = {}
        self._lookups: dict[tuple, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(4)

    async def _lookup(self, key: tuple, fetch: Callable[[], Awaitable[Any]]) -> Any:
        async def load():
            async with self._semaphore:
                try:
                    async with asyncio.timeout(10):
                        return await fetch()
                except (discord.HTTPException, discord.InvalidData,
                        aiohttp.ClientError, TimeoutError):
                    # Missing access, deleted messages, expired invites, or an outage.
                    return None

        if key not in self._lookups:
            self._lookups[key] = asyncio.create_task(load())
        return await self._lookups[key]

    async def _channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            return channel
        return await self._lookup(
            ("channel", channel_id), lambda: self.bot.fetch_channel(channel_id)
        )

    async def _message(self, channel, message_id: int):
        for message in self.bot.cached_messages:
            if message.id == message_id and message.channel.id == channel.id:
                return message
        if not hasattr(channel, "fetch_message"):
            return None
        return await self._lookup(
            ("message", channel.id, message_id),
            lambda: channel.fetch_message(message_id),
        )

    @staticmethod
    def _guild_fields(data: dict, guild) -> None:
        data["server"] = guild.name
        data["server_icon_url"] = str(guild.icon) if guild.icon else None

    async def _resolve(self, target: DiscordTarget) -> dict:
        data = dict(new_discord_link(""))
        del data["url"]
        if target.kind == "invite":
            invite = await self._lookup(
                ("invite", target.invite_code),
                lambda: self.bot.fetch_invite(target.invite_code, with_counts=False),
            )
            if invite is not None and invite.guild is not None:
                self._guild_fields(data, invite.guild)
                if invite.channel is not None:
                    data["channel"] = getattr(invite.channel, "name", None)
            return data

        guild = self.bot.get_guild(target.server_id)
        if guild is not None:
            self._guild_fields(data, guild)
        channel = await self._channel(target.channel_id)
        if channel is None:
            if guild is None:
                preview = await self._lookup(
                    ("guild_preview", target.server_id),
                    lambda: self.bot.fetch_guild_preview(target.server_id),
                )
                if preview is not None:
                    self._guild_fields(data, preview)
            return data
        # Ignore forged server/channel pairs and never preview direct messages.
        guild = getattr(channel, "guild", None)
        if guild is None or guild.id != target.server_id:
            return data
        self._guild_fields(data, guild)

        message_channel = channel
        message_id = target.message_id
        if isinstance(channel, discord.Thread):
            data["title"] = channel.name
            parent = channel.parent
            if parent is None and channel.parent_id is not None:
                parent = await self._channel(channel.parent_id)
            data["channel"] = parent.name if parent is not None else None
            if message_id is None:
                message_id = channel.id
                # Forum starters live inside the thread; ordinary thread starters
                # are messages in the parent text/announcement channel.
                if parent is None:
                    return data
                if not isinstance(parent, discord.ForumChannel):
                    message_channel = parent
        else:
            data["channel"] = channel.name

        if message_id is not None:
            message = await self._message(message_channel, message_id)
            if message is not None:
                data["content"] = message.content or None
        return data

    async def resolve(self, url: str) -> DiscordLink:
        link = new_discord_link(url)
        target = discord_target(url)
        if target is None:
            return link
        if target not in self._targets:
            self._targets[target] = asyncio.create_task(self._resolve(target))
        link.update(await self._targets[target])
        return link


async def apply_discord_links(resolver: DiscordLinkResolver, post_data: dict) -> None:
    links = list(iter_discord_links(post_data))
    resolved = await asyncio.gather(*(resolver.resolve(link["url"]) for link in links))
    for link, metadata in zip(links, resolved):
        link.update(metadata)


@dataclass
class CrosspostReference:
    channel_ids: list[str] = field(default_factory=list)
    source_threads: list[discord.Thread] = field(default_factory=list)

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
        thread = self.message.channel
        assert isinstance(thread, discord.Thread)
        data = await parser_cog.get_post_data(thread, thread.parent, self.bot)
        ephemeral = self.parse_response_message.flags.ephemeral
        try:
            parse_result, _ = await parser_cog.parse_thread_content(data["messages"])
        except Exception as e:
            new_item = await ParserErrorItem.create(self.bot, thread, e, self.i)
            new_view = discord.ui.LayoutView()
            new_view.add_item(new_item)
            await interaction.followup.send(
                view=new_view, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none()
            )
            return

        if parse_result is not None:
            await parser_cog.enrich_post(parse_result, DiscordLinkResolver(self.bot))
            await parser_cog.write_parsed_post(thread, parse_result)

        new_item = discord.ui.TextDisplay(f"{self.message.jump_url}: Parse successful.")
        new_view = discord.ui.LayoutView()
        new_view.add_item(new_item)
        await interaction.followup.send(view=new_view, ephemeral=ephemeral)
        
class Parser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dimension_resolver = DimensionResolver(bot)

    async def enrich_post(self, post_data: dict, link_resolver: DiscordLinkResolver):
        await apply_dimensions(self.dimension_resolver, post_data)
        apply_thumbnails(post_data)
        await apply_discord_links(link_resolver, post_data)

    async def write_parsed_post(self, thread: discord.Thread, post_data: dict):
        json_data = {
            "parsed_at": discord.utils.utcnow().isoformat(),
            "category_name": thread.parent.category.name,
            "channel_ids": [str(thread.parent_id)],
            "thread_id": str(thread.id),
            "slug": self.slugify(thread.name),
            "title": thread.name,
            "tags": [{"id": str(tag.id), "name": tag.name} for tag in thread.applied_tags],
            "post_data": post_data,
        }
        parsed_path = Path.cwd() / "parsed"
        parsed_path.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(parsed_path / f"{thread.id}.json", mode="w", encoding="utf-8") as file:
            await file.write(json.dumps(json_data, indent=4))

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

    async def parse_thread_content(self, messages: list[str]) -> tuple[dict | None, str | None]:
        lines = "\n".join(messages).splitlines()
        if (target := parse_crosspost(lines)) is not None:
            return None, target
        username_lookup = await self.build_username_lookup_from_messages(messages)
        lookup_token = set_contributor_username_lookup(username_lookup)
        try:
            return message_parse(lines), None
        finally:
            reset_contributor_username_lookup(lookup_token)

    async def iter_all_threads(self, channel: discord.ForumChannel):
        #Iterates over all threads, active or not
        for thread in channel.threads:
            yield thread

        async for thread in channel.archived_threads(limit=None):
            yield thread

    # Parse given threads to json and write to file
    async def parse_threads_stream(self, thread_iter, interaction: discord.Interaction, reply_to_channel=True, crossposts: dict[str, CrosspostReference] | None = None, link_resolver: DiscordLinkResolver | None = None):
        errors = total = 0
        link_resolver = link_resolver or DiscordLinkResolver(self.bot)

        (Path.cwd() / "parsed").mkdir(parents=True, exist_ok=True)

        async for thread in thread_iter:
            total += 1
            data = await self.get_post_data(thread=thread, channel=thread.parent, bot=interaction.client)

            try:
                parse_result, crosspost_target_id = await self.parse_thread_content(data["messages"])
            except Exception as error:
                error_view = discord.ui.LayoutView(timeout=None)
                error_view.add_item(await ParserErrorItem.create(self.bot, thread, error, 1))
                mentions = discord.AllowedMentions.none()
                if reply_to_channel:
                    await interaction.channel.send(view=error_view, allowed_mentions=mentions)
                else:
                    await interaction.followup.send(view=error_view, ephemeral=True, allowed_mentions=mentions)
                errors += 1
                continue

            if crosspost_target_id is not None:
                if crossposts is None:
                    continue
                # Preserve archive traversal order and do not add the same
                # forum twice when Discord happens to return a duplicate thread.
                reference = crossposts.setdefault(
                    crosspost_target_id, CrosspostReference()
                )
                channel_id = str(thread.parent_id)
                if channel_id not in reference.channel_ids:
                    reference.channel_ids.append(channel_id)
                if all(source.id != thread.id for source in reference.source_threads):
                    reference.source_threads.append(thread)
                continue

            await self.enrich_post(parse_result, link_resolver)
            await self.write_parsed_post(thread, parse_result)

        return errors, total

    def merge_crosspost_channels(self, crossposts: dict[str, CrosspostReference]) -> list[tuple[discord.Thread, Exception]]:
        parsed_path = Path.cwd() / "parsed"
        errors: list[tuple[discord.Thread, Exception]] = []

        for target_thread_id, reference in crossposts.items():
            file_path = parsed_path / f"{target_thread_id}.json"
            if not file_path.exists():
                for source_thread in reference.source_threads:
                    errors.append(
                        (
                            source_thread,
                            ValueError(
                                f"Crosspost points to {target_thread_id}, but its original post was not parsed."
                            ),
                        )
                    )
                continue

            try:
                with open(file_path, encoding="utf-8") as file:
                    data = json.load(file)

                if not isinstance(data, dict):
                    raise ValueError("parsed output is not a JSON object")

                # The fallback makes this safe if a file created by an older
                # parser run is present during a targeted parse.
                channel_ids = data.get("channel_ids", [data.get("channel_id")])
                if not isinstance(channel_ids, list) or any(channel_id is None for channel_id in channel_ids):
                    raise ValueError("parsed output has no channel IDs")

                for channel_id in reference.channel_ids:
                    if channel_id not in channel_ids:
                        channel_ids.append(channel_id)

                data["channel_ids"] = channel_ids
                data.pop("channel_id", None)
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=4)
            except (OSError, json.JSONDecodeError, ValueError) as error:
                for source_thread in reference.source_threads:
                    errors.append(
                        (
                            source_thread,
                            ValueError(
                                f"Could not merge crosspost for {target_thread_id}: {error}"
                            ),
                        )
                    )

        return errors

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

    def _upload_to_designs(self):
        client = MongoClient(MONGO_URI)
        try:
            DIRECTORY_PATH = Path.cwd() / "parsed"
            db = client[DATABASE_NAME]
            collection = db[COLLECTION_NAME]

            files = [f for f in os.listdir(DIRECTORY_PATH) if f.endswith('.json')]

            docs_to_insert = []
            for filename in files:
                file_path = os.path.join(DIRECTORY_PATH, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, dict):
                            data['file_origin'] = filename
                            docs_to_insert.append(data)
                        elif isinstance(data, list):
                            docs_to_insert.extend(data)
                    except json.JSONDecodeError:
                        continue

            if docs_to_insert:
                # Wipe existing files
                collection.delete_many({})
                # Push new files
                collection.insert_many(docs_to_insert)

        finally:
            client.close()
    
    #Parse post
    @app_commands.command(name="parse_post", description="Parse the selected post and check for errors")
    @app_commands.describe(thread="The post to be parsed")
    @app_commands.checks.has_any_role(*PARSE_ROLES)
    async def parse_post(self, interaction: discord.Interaction, thread: discord.Thread):
        if thread.parent.category_id in NON_ARCHIVE_CATEGORIES:
            await interaction.response.send_message("That is not an archive thread, it cannot be parsed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Wrap the single thread in an async generator
        async def single_thread_gen():
            yield thread

        errors, total = await self.parse_threads_stream(single_thread_gen(), interaction, reply_to_channel=False)
        if not errors:
            await interaction.followup.send(content=f"Parsed {thread.name} successfully.\nErrors: {errors}/{total}", ephemeral=True)

    # Parse channel
    @app_commands.command(name="parse_channel", description="Parse the posts in a selected channel and check for errors")
    @app_commands.describe(channel="The channel to be parsed")
    @app_commands.checks.has_any_role(*PARSE_ROLES)
    async def parse_channel(self, interaction: discord.Interaction, channel: discord.ForumChannel):
        if channel.category_id in NON_ARCHIVE_CATEGORIES:
            await interaction.response.send_message("That is not an archive channel, it cannot be parsed.", ephemeral=True)
            return

        await interaction.response.send_message("Beginning parsing. . .")
        errors, total = await self.parse_threads_stream(self.iter_all_threads(channel), interaction)
        await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")


    # Parse archive
    @app_commands.command(name="parse_archive", description="Parse the posts in the archive and check for errors")
    @app_commands.checks.has_any_role(*PARSE_ROLES)
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
        crossposts: dict[str, CrosspostReference] = {}
        link_resolver = DiscordLinkResolver(self.bot)
        total_channels = len(parse_channel_list)
        current_channel_index = 1
        embed = discord.Embed(title="Parsing Status", colour=discord.Colour.green())
        update_message_obj = await interaction.channel.send(embed=embed)

        for channel in parse_channel_list:
            embed.description = f"{current_channel_index}/{total_channels} -> {channel.name}"
            await update_message_obj.edit(embed=embed)
            current_channel_index += 1

            channel_errors, channel_total = await self.parse_threads_stream(
                self.iter_all_threads(channel), interaction, crossposts=crossposts,
                link_resolver=link_resolver,
            )
            errors += channel_errors
            total += channel_total

        crosspost_errors = self.merge_crosspost_channels(crossposts)
        errors += len(crosspost_errors)
        for thread, error in crosspost_errors:
            error_item = await ParserErrorItem.create(self.bot, thread, error, 1)
            error_view = discord.ui.LayoutView(timeout=None)
            error_view.add_item(error_item)
            await interaction.channel.send(view=error_view)

        await interaction.channel.send(f"Done parsing.\nErrors: {errors}/{total}.")

        # Push parsed files to DB
        await interaction.channel.send("Uploading parsed results to the database. . .")
        await asyncio.to_thread(self._upload_to_designs)
        await interaction.channel.send("Database updated")

async def setup(bot: commands.Bot):
    await bot.add_cog(Parser(bot))
