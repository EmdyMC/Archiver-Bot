import re
from dataclasses import dataclass
from typing import Iterator, Literal
from urllib.parse import urlsplit

from MessageDict import DiscordLink, Link

DISCORD_HOSTS = {
    "discord.com", "www.discord.com", "ptb.discord.com", "canary.discord.com",
    "discordapp.com", "www.discordapp.com", "ptb.discordapp.com", "canary.discordapp.com",
}
INVITE_CODE_RE = re.compile(r"[A-Za-z0-9_-]+")
CHANNEL_PATH_RE = re.compile(r"/channels/(\d+)/(\d+)(?:/(\d+))?")
DISCORD_URL_RE = re.compile(
    r"(?<![\w@./-])(?:https?://)?"
    r"(?:(?:www\.)?discord\.gg|(?:(?:www|ptb|canary)\.)?discord(?:app)?\.com)"
    r"/[^\s<>()\[\]{}\"'`]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscordTarget:
    kind: Literal["invite", "channel"]
    invite_code: str | None = None
    server_id: int | None = None
    channel_id: int | None = None
    message_id: int | None = None


def discord_target(url: str) -> DiscordTarget | None:
    try:
        parts = urlsplit(url if "://" in url else "https://" + url)
        if parts.scheme.lower() not in {"http", "https"}:
            return None
        if parts.username or parts.password or parts.port is not None:
            return None
        host = (parts.hostname or "").lower()
        path = parts.path.rstrip("/")
        if host in {"discord.gg", "www.discord.gg"}:
            code = path.removeprefix("/")
        elif host in DISCORD_HOSTS:
            if match := CHANNEL_PATH_RE.fullmatch(path):
                return DiscordTarget(
                    kind="channel",
                    server_id=int(match[1]),
                    channel_id=int(match[2]),
                    message_id=int(match[3]) if match[3] else None,
                )
            if not path.startswith("/invite/"):
                return None
            code = path[len("/invite/"):]
        else:
            return None
        if INVITE_CODE_RE.fullmatch(code):
            return DiscordTarget(kind="invite", invite_code=code)
    except ValueError:
        pass
    return None


def new_discord_link(url: str) -> DiscordLink:
    return {
        "url": url,
        "server": None,
        "channel": None,
        "title": None,
        "content": None,
        "server_icon_url": None,
    }


def link_url(link: Link) -> str:
    """Read either an ordinary URL or an enriched Discord link."""
    return link["url"] if isinstance(link, dict) else link


def parse_link(url: str) -> Link:
    if discord_target(url) is not None:
        return new_discord_link(url)
    return url


def extract_urls(text: str) -> list[str]:
    """Read URLs in bare, Markdown, or angle-bracket form."""
    urls = []
    for match in re.finditer(r"https?://[^\s<>\"`]+", text):
        url = match[0]
        if re.search(r"\[[^\]\n]*\]\(\s*$", text[: match.start()]):
            # The first unmatched closing parenthesis ends a Markdown destination.
            depth = 0
            for index, char in enumerate(url):
                if char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        url = url[:index]
                        break
                    depth -= 1
        urls.append(url)
    return urls


def embedded_discord_links(texts: list[str]) -> list[DiscordLink]:
    urls: dict[str, None] = {}
    for text in texts:
        for match in DISCORD_URL_RE.finditer(text):
            url = match[0].rstrip(".,;:!?")
            if discord_target(url) is not None:
                urls.setdefault(url, None)
    return [new_discord_link(url) for url in urls]


def _attach_text_links(item: dict, fields: tuple[str, ...]) -> None:
    texts: list[str] = []
    for field in fields:
        value = item.get(field, "")
        texts.extend(value if isinstance(value, list) else [value])
    item["discord_links"] = embedded_discord_links(texts)


def _attach_nodes(nodes: list[dict]) -> None:
    for node in nodes:
        _attach_text_links(node, ("text",))
        _attach_nodes(node.get("children", []))


def attach_discord_links(post_data: dict) -> None:
    """Attach link objects at their owning fields; leave the source text intact."""
    _attach_nodes(post_data.get("rates", {}).get("notes", []))

    if lag_info := post_data.get("lag_info"):
        _attach_nodes(lag_info.get("notes", []))

    for field in ("description", "positives", "negatives", "design_specifications"):
        _attach_nodes(post_data.get(field, []))
    instructions = post_data.get("instructions") or {}
    for field in ("notes", "build", "usage"):
        _attach_nodes(instructions.get(field, []))


def iter_discord_links(value: object) -> Iterator[DiscordLink]:
    """Walk only the parsed tree, never the fetched contents of a link preview."""
    if isinstance(value, dict):
        if "url" in value and "server" in value and "content" in value:
            yield value
        else:
            for child in value.values():
                yield from iter_discord_links(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_discord_links(child)
