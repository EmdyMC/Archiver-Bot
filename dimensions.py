import asyncio
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import discord
from discord.ext import commands

# Discord attachment URLs, e.g.
# https://cdn.discordapp.com/attachments/<channel_id>/<message_id>/<filename>
ATTACHMENT_PATH_RE = re.compile(r"^/attachments/(\d+)/(\d+)/(.+)$")

MEDIA_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "mp4",
    "mov",
    "webm",
    "mkv",
    "avi",
}


@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    url: str


class DimensionResolver:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._messages: dict[tuple[int, int], dict[str, MediaInfo]] = {}

    async def resolve(self, url: str) -> MediaInfo | None:
        path = urlsplit(url).path
        match = ATTACHMENT_PATH_RE.match(path)
        if match is None:
            return None

        attachments = await self._message_attachments(
            (int(match.group(1)), int(match.group(2)))
        )
        return attachments.get(unquote(path))

    async def prefetch(self, urls: list[str]) -> None:
        keys: set[tuple[int, int]] = set()
        for url in urls:
            match = ATTACHMENT_PATH_RE.match(urlsplit(url).path)
            if match is not None:
                keys.add((int(match.group(1)), int(match.group(2))))
        await asyncio.gather(*(self._message_attachments(key) for key in keys))

    async def _message_attachments(
        self, key: tuple[int, int]
    ) -> dict[str, MediaInfo]:
        if key in self._messages:
            return self._messages[key]

        attachments: dict[str, MediaInfo] = {}
        try:
            channel_id, message_id = key
            message = await self.bot.http.get_message(channel_id, message_id)
            for attachment in message.get("attachments", []):
                width = attachment.get("width")
                height = attachment.get("height")
                if width is None or height is None:
                    continue
                path = unquote(urlsplit(attachment["url"]).path)
                attachments[path] = MediaInfo(
                    int(width), int(height), attachment["url"]
                )
        except discord.HTTPException:
            # Deleted message, missing access, ...
            pass

        self._messages[key] = attachments
        return attachments


def media_file_nodes(nodes: list[dict]) -> list[dict]:
    media: list[dict] = []
    for node in nodes:
        if node["type"] == "folder":
            media.extend(media_file_nodes(node["children"]))
            continue
        name = node["name"]
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension in MEDIA_EXTENSIONS:
            media.append(node)
    return media


async def apply_dimensions(resolver: DimensionResolver, post_data: dict) -> None:
    targets: list[dict] = []

    targets.extend(post_data.get("figures", []))
    targets.extend(post_data.get("video_links", []))

    files = post_data.get("files", {})
    for section in ("schematics", "world_downloads", "images"):
        targets.extend(media_file_nodes(files.get(section, [])))

    await resolver.prefetch([target["url"] for target in targets])

    infos = await asyncio.gather(
        *(resolver.resolve(target["url"]) for target in targets)
    )

    for target, info in zip(targets, infos):
        target["width"] = info.width if info else None
        target["height"] = info.height if info else None
