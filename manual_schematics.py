"""Validate and replace manually reviewed schematic ZIPs in parsed posts."""

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from links import link_url
from MessageDict import FileTreeNode
from parser import normalize_cdn_url

MANUAL_SCHEMATICS_PATH = Path(__file__).with_name("manual_schematics.json")
SCHEMATIC_EXTENSIONS = {".litematic", ".schematic", ".schem", ".nbt"}


class ManualSchematicsError(ValueError):
    """A manual schematic entry could not be loaded or applied."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManualSchematicsError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def attachment_url(url):
    """Use the archive's permanent CDN URL, ignoring signed Discord query strings."""
    if not isinstance(url, str) or any(c.isspace() for c in url):
        raise ManualSchematicsError("Expected an attachment URL")
    parts = urlsplit(normalize_cdn_url(url))
    if parts.scheme != "https" or parts.netloc != "cdn.tmcc.dev" or not re.fullmatch(
        r"/attachments/[0-9]+/[0-9]+/[^/]+", parts.path
    ):
        raise ManualSchematicsError(f"Invalid archive attachment URL: {url!r}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def url_filename(url):
    return unquote(urlsplit(url).path.rsplit("/", 1)[-1])


def discord_attachment_filename(filename):
    """Discord's ASCII CDN basename for a Unicode or punctuated upload name.

    Discord may preserve the original stem in attachment.title while the URL
    uses this compatibility-normalized spelling. The reviewed name is stored
    separately rather than rewritten to the CDN basename.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "", unicodedata.normalize("NFKD", filename).replace(" ", "_"))


def matches_attachment_filename(filename, url_name):
    return url_name == filename or url_name == discord_attachment_filename(filename)


def valid_text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and not any(
        ord(c) < 32 or ord(c) == 127 for c in value
    )


def valid_filename(name):
    return valid_text(name) and not any(c in name for c in '/\\:*?"<>|') and Path(name).suffix.lower() in SCHEMATIC_EXTENSIONS


def walk_files(nodes: list[FileTreeNode]):
    for node in nodes:
        if node["type"] == "folder":
            yield from walk_files(node["children"])
        else:
            yield node


def validate_tree(nodes: object, *, allow_empty=False):
    if not isinstance(nodes, list) or (not nodes and not allow_empty):
        raise ManualSchematicsError("Expected a nonempty replacement file tree")
    for node in nodes:
        if not isinstance(node, dict) or not valid_text(node.get("name")):
            raise ManualSchematicsError("Invalid file or folder name")
        if node.get("type") == "folder" and node.keys() == {"type", "name", "children"}:
            if any(c in node["name"] for c in "<>") or node["name"].endswith(":"):
                raise ManualSchematicsError("Invalid folder caption")
            validate_tree(node["children"])
        elif node.get("type") == "file" and node.keys() == {"type", "name", "note", "url"}:
            if (not valid_filename(node["name"]) or not valid_text(node["note"])
                    or any(c in node["note"] for c in "[]<>")):
                raise ManualSchematicsError("Invalid schematic filename or display label")
            url = attachment_url(node["url"])
            if node["url"] != url or not matches_attachment_filename(node["name"], url_filename(url)):
                raise ManualSchematicsError("Expected a permanent attachment URL matching the finalized filename")
        else:
            raise ManualSchematicsError("Unexpected schematic node fields")


def validate_entries(entries):
    if not isinstance(entries, dict):
        raise ManualSchematicsError("Expected an object keyed by Discord thread ID")
    for thread_id, entry in entries.items():
        try:
            if not re.fullmatch(r"[1-9][0-9]*", thread_id):
                raise ManualSchematicsError("Invalid Discord thread ID")
            if not isinstance(entry, dict) or entry.keys() != {"bundles"} or not isinstance(entry["bundles"], list) or not entry["bundles"]:
                raise ManualSchematicsError("Expected a nonempty bundles list")
            sources, destinations = set(), set()
            for bundle in entry["bundles"]:
                if not isinstance(bundle, dict) or bundle.keys() != {"source_url", "tree"}:
                    raise ManualSchematicsError("Expected source_url and tree")
                source = attachment_url(bundle["source_url"])
                if not url_filename(source).lower().endswith(".zip") or source in sources:
                    raise ManualSchematicsError("Expected unique original ZIP URLs")
                sources.add(source)
                validate_tree(bundle["tree"], allow_empty=True)
                for f in walk_files(bundle["tree"]):
                    if f["url"] in destinations:
                        raise ManualSchematicsError("Duplicate replacement attachment URL")
                    destinations.add(f["url"])
        except ValueError as error:
            raise ManualSchematicsError(f"Thread {thread_id}: {error}") from error
    return entries


def load_manual_schematics(path=MANUAL_SCHEMATICS_PATH, *, missing_ok=False):
    try:
        with Path(path).open(encoding="utf-8") as file:
            return validate_entries(json.load(file, object_pairs_hook=unique_object))
    except FileNotFoundError as error:
        if missing_ok:
            return {}
        raise ManualSchematicsError(f"{path} is missing") from error
    except (OSError, ValueError) as error:
        raise ManualSchematicsError(f"{path}: {error}") from error


def merge_manual_schematics(thread_id, post_data, entries):
    """Replace exactly one original schematic ZIP per bundle, preserving its position."""
    if (entry := entries.get(thread_id)) is None:
        return
    replacements = {attachment_url(b["source_url"]): b["tree"] for b in entry["bundles"]}
    seen = set()
    def replace(nodes):
        result = []
        for node in nodes:
            if node["type"] == "folder":
                children = replace(node["children"])
                if children:
                    result.append({**node, "children": children})
                continue
            try:
                url = attachment_url(link_url(node["url"]))
            except ManualSchematicsError:
                result.append(node)
                continue
            if url not in replacements:
                result.append(node)
            elif url in seen:
                raise ManualSchematicsError(f"Duplicate source ZIP: {url}")
            else:
                seen.add(url)
                result.extend(deepcopy(replacements[url]))
        return result
    try:
        trees = replace(post_data["files"]["schematics"])
        if missing := replacements.keys() - seen:
            raise ManualSchematicsError(f"Source ZIP missing or changed: {', '.join(sorted(missing))}")
        if not trees:
            raise ManualSchematicsError("Replacement would remove every schematic from the post")
        # Reject collisions with existing schematic attachments, but allow unrelated
        # pre-existing archive repetitions.
        new_urls = {f["url"] for tree in replacements.values() for f in walk_files(tree)}
        counts = dict.fromkeys(new_urls, 0)
        for f in walk_files(trees):
            try:
                url = attachment_url(link_url(f["url"]))
            except ManualSchematicsError:
                continue
            if url in counts:
                counts[url] += 1
        if any(n != 1 for n in counts.values()):
            raise ManualSchematicsError("Replacement attachment conflicts with another schematic")
    except ValueError as error:
        raise ManualSchematicsError(f"Thread {thread_id}: {error}") from error
    post_data["files"]["schematics"] = trees
