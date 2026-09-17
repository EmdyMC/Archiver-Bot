import asyncio
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import aiohttp
import discord
from discord.ext import commands

# Discord attachment URLs, e.g.
# https://cdn.discordapp.com/attachments/<channel_id>/<message_id>/<filename>
ATTACHMENT_PATH_RE = re.compile(r"^/attachments/(\d+)/(\d+)/(.+)$")

IMAGE_SIZE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

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


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 <= len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return (
                int.from_bytes(data[i + 7 : i + 9], "big"),
                int.from_bytes(data[i + 5 : i + 7], "big"),
            )
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    return None


def image_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X":
            return (
                int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1,
            )
        if data[12:16] == b"VP8 ":
            return (
                int.from_bytes(data[26:28], "little") & 0x3FFF,
                int.from_bytes(data[28:30], "little") & 0x3FFF,
            )
        if data[12:16] == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if data[:2] == b"\xff\xd8":
        return _jpeg_size(data)
    return None


class DimensionResolver:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._messages: dict[tuple[int, int], dict[str, MediaInfo]] = {}
        self._fallbacks: dict[str, tuple[int, int] | None] = {}
        self._session: aiohttp.ClientSession | None = None

    async def _image_size_fallback(self, url: str) -> tuple[int, int] | None:
        # Message metadata unavailable (deleted/inaccessible), read the
        # dimensions from the header bytes of the mirrored file instead
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in IMAGE_SIZE_EXTENSIONS:
            return None
        if url in self._fallbacks:
            return self._fallbacks[url]

        if self._session is None:
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.get(
                url, headers={"Range": "bytes=0-65535"}
            ) as response:
                if response.status in (200, 206):
                    size = image_size(await response.content.read(65536))
                else:
                    size = None
        except aiohttp.ClientError:
            size = None

        self._fallbacks[url] = size
        return size

    async def resolve(self, url: str) -> MediaInfo | None:
        path = urlsplit(url).path
        match = ATTACHMENT_PATH_RE.match(path)
        if match is None:
            return None

        attachments = await self._message_attachments(
            (int(match.group(1)), int(match.group(2)))
        )
        info = attachments.get(unquote(path))
        if info is not None:
            return info

        size = await self._image_size_fallback(url)
        if size is None:
            return None
        return MediaInfo(size[0], size[1], url)

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
