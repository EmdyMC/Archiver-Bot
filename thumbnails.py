from urllib.parse import urlsplit

from dimensions import ATTACHMENT_PATH_RE, media_file_nodes

VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "mkv", "gif"}


def url_extension(url: str) -> str:
    name = urlsplit(url).path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def thumbnail_url_for(url: str) -> str | None:
    parts = urlsplit(url)
    if ATTACHMENT_PATH_RE.match(parts.path) is None:
        return None
    if url_extension(url) not in VIDEO_EXTENSIONS:
        return None
    # Same key convention as TMCC_BOT's R2 thumbnail uploads: <video path>_thumb.avif
    return parts._replace(path=parts.path + "_thumb.avif").geturl()


def _set_thumbnail(target: dict) -> None:
    if thumbnail_url := thumbnail_url_for(target["url"]):
        target["thumbnail_url"] = thumbnail_url


def apply_thumbnails(post_data: dict) -> None:
    for figure in post_data.get("figures", []):
        if figure.get("file_type") == "video":
            _set_thumbnail(figure)
    for link in post_data.get("video_links", []):
        _set_thumbnail(link)

    files = post_data.get("files", {})
    for section in ("schematics", "world_downloads", "images"):
        for node in media_file_nodes(files.get(section, [])):
            _set_thumbnail(node)
