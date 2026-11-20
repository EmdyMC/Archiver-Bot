import json
import re
from contextvars import ContextVar, Token
from urllib.parse import urlsplit

# import traceback
from collections import Counter, defaultdict
from functools import wraps
from typing import Callable
from typing import get_origin
from dataclasses import dataclass

from MessageDict import Contributor, FileTreeNode, Message
from links import attach_discord_links, discord_target, extract_urls, parse_link

type section = list[str]
type dict_section = dict[str, section]
type parser[U] = Callable[[section], U]


SCHEMA_DEFAULT_UNSET = object()
LIST_ITEM_RE = re.compile(r"(?P<indent> *)(?P<marker>- |\d+\. )(?P<text>.*\S)")
URL = r"https?://[^\s<>\"\x60/?#]+(?:[/?#][^\s<>\"\x60]*)?"
URL_TOKEN = rf"(?:<{URL}>|{URL})"
BARE_LINKS_RE = re.compile(rf"{URL_TOKEN}(?: +{URL_TOKEN})*")
INLINE_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"`]+")
NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
VERSION_RANGE = r"\d+(?:\.\d+)+(?:-\d+(?:\.\d+)+|\+)?"
VERSIONS = rf"{VERSION_RANGE}(?:, {VERSION_RANGE})*"


def line_error(reason: str, text: str) -> ValueError:
    excerpt = text if len(text) <= 180 else text[:177] + "..."
    return ValueError(f"{reason}\nOffending content: {excerpt!r}")


CONTRIBUTOR_USERNAME_LOOKUP: ContextVar[dict[int, str] | None] = ContextVar(
    "contributor_username_lookup", default=None
)


def set_contributor_username_lookup(lookup: dict[int, str] | None) -> Token:
    return CONTRIBUTOR_USERNAME_LOOKUP.set(lookup or {})


def reset_contributor_username_lookup(token: Token) -> None:
    CONTRIBUTOR_USERNAME_LOOKUP.reset(token)


@dataclass
class SchemaItem[T]:
    display_names: list[str]
    name: str
    parser: parser[T]
    required: bool = True
    default: T | None | object = SCHEMA_DEFAULT_UNSET


@dataclass
class ListNode:
    text: str
    children: list["ListNode"]
    list_type: str  # "dashed" | "numbered"

    def to_dict(self) -> dict:
        return {
            "list_type": self.list_type,
            "text": INLINE_URL_RE.sub(lambda match: normalize_cdn_url(match[0]), self.text),
            "children": [c.to_dict() for c in self.children],
        }


def serialize_nodes(nodes: list[ListNode]) -> list[dict]:
    return [n.to_dict() for n in nodes]


def identity[T](x: T) -> T:
    return x


def normalize_cdn_url(url: str) -> str:
    prefixes = (
        "https://media.discordapp.net/",
        "http://media.discordapp.net/",
        "https://cdn.discordapp.com/",
        "http://cdn.discordapp.com/",
    )
    for prefix in prefixes:
        if url.startswith(prefix):
            return "https://cdn.tmcc.dev/" + url[len(prefix) :].lstrip("/")
    return url


def single_line_parser[T](function: Callable[[str], T]) -> parser[T]:
    @wraps(function)
    def wrapper(data: section) -> T:
        if len(data) != 1:
            if len(data) > 1:
                raise line_error("Only one bullet is allowed here.", data[1])
            raise ValueError("Expected one bullet.")
        return function(data[0])

    return wrapper


def list_postprocess_parse[T](
    parser_: parser[list[section]], postprocessor: parser[T]
) -> parser[list[T]]:
    return lambda data: [postprocessor(x) for x in parser_(data)]


def list_postprocess_flattened_parse[T](
    parser_: parser[list[section]], postprocessor: parser[T]
) -> parser[list[T]]:
    return lambda data: [y for x in parser_(data) for y in postprocessor(x)]


def dict_postprocess_parse[T](
    parser_: parser[dict_section], postprocessor: parser[T]
) -> parser[dict[str, T]]:
    return lambda data: {k: postprocessor(v) for k, v in parser_(data).items()}


def prefix_dict_parse(
    prefix: str,
) -> parser[dict_section]:
    def parse(data: section) -> dict_section:
        parsed_data: defaultdict[str, section] = defaultdict(list)
        current_key = ""
        for line in data:
            if not line.strip():
                continue
            if line.startswith(prefix):
                current_key = line[len(prefix) :].strip()
                if not current_key:
                    raise line_error("Expected a heading name.", line)
                parsed_data.setdefault(current_key, [])
            else:
                parsed_data[current_key].append(line)
        return dict(parsed_data)

    return parse


def parse_post_sections(data: section) -> dict_section:
    sections = prefix_dict_parse("## ")(data)
    headings = Counter(line[3:].strip() for line in data if line.startswith("## "))
    for title, lines in sections.items():
        if not title or not lines or not re.match(r"- See (?:\[thread\]|thread\b)", lines[0], re.IGNORECASE):
            continue
        stub = lines[0].rstrip()
        match = re.fullmatch(rf"- See \[thread\]\(({URL_TOKEN})\) for (.+?)\.?", stub, re.IGNORECASE)
        target = discord_target(match[1].strip("<>")) if match else None
        if not target or target.kind != "channel" or not target.message_id or match[2].lower() != title.lower():
            raise line_error(f"Use a linked thread message for the {title} placeholder.", stub)
        if headings[title] < 2 or len(lines) < 2:
            raise line_error(f"Include the full {title} section in the thread.", stub)
        sections[title] = lines[1:]
    return sections


def list_parse() -> parser[list[section]]:
    # Assume one level list
    def parse(data: section) -> list[section]:
        lines = []
        indent = None
        for line in data:
            match = LIST_ITEM_RE.fullmatch(line.rstrip())
            if not match or match["marker"] != "- ":
                raise line_error("Expected a dash bullet with text.", line)
            if indent is None:
                indent = match["indent"]
            if len(indent) > 3 or match["indent"] != indent:
                raise line_error("Inconsistent indentation. Align this bullet with its siblings.", line)
            text = match["text"].strip()
            if BARE_LINKS_RE.fullmatch(text):
                raise line_error("Bare link. Add a caption or a descriptive link label.", line)
            lines.append([text])
        return lines

    return parse


def flattened_list_parse() -> parser[section]:
    def parse(data: section) -> section:
        # All parsers accept a section type, so list_parse returns a list[section] where each section is one line. This parse function is used for the files fields and should be flattened since it's directly stored and not parsed again.
        return [ls[0] for ls in list_parse()(data)]

    return parse


def parse_nested_list(data: list[str], *, allow_numbered: bool = True) -> list[ListNode]:
    nodes: list[ListNode] = []
    levels = []
    for line in data:
        if not line.strip():
            continue
        match = LIST_ITEM_RE.fullmatch(line.rstrip())
        if not match:
            if BARE_LINKS_RE.fullmatch(line.strip()):
                raise line_error("Bare link. Put the URL on a bullet with a caption.", line)
            raise line_error("Expected a bullet or numbered item with text.", line)
        indent = len(match["indent"])
        if not levels:
            if indent > 3:
                raise line_error("Inconsistent indentation. The first item must start within three spaces of the left margin.", line)
            levels.append((indent, nodes))
        current_indent, siblings = levels[-1]
        if indent > current_indent:
            if not siblings or indent - current_indent < 2:
                raise line_error(
                    "Inconsistent indentation. Indent children by at least two spaces.",
                    line,
                )
            siblings = siblings[-1].children
            levels.append((indent, siblings))
        elif indent < current_indent:
            while len(levels) > 1 and levels[-1][0] > indent:
                levels.pop()
            if levels[-1][0] != indent:
                raise line_error("Inconsistent indentation. Align this item with its siblings.", line)
            siblings = levels[-1][1]
        numbered = match["marker"] != "- "
        if numbered and not allow_numbered:
            raise line_error("Expected a dash bullet in this section.", line)
        text = match["text"].strip()
        if BARE_LINKS_RE.fullmatch(text):
            raise line_error("Bare link. Add a caption or a descriptive link label.", line)
        siblings.append(ListNode(text, [], "numbered" if numbered else "dashed"))
    return nodes


def schema_dict_parse[T](
    parser_: parser[dict_section],
    config: list[SchemaItem],
) -> parser[dict[str, T]]:
    def parse(data: section) -> dict:
        result: dict[str, T] = {}
        parsed_data = parser_(data)
        if parsed_data.get(""):
            raise line_error("Unexpected content before the first heading.", parsed_data[""][0])
        valid_keys = {name for field in config for name in field.display_names}
        for key, lines in parsed_data.items():
            if key not in valid_keys:
                raise ValueError(f"Unexpected heading **{key}**.")
            if not lines:
                raise ValueError(f"Heading **{key}** has no content.")

        used_keys = set()

        for field in config:
            match_found = False
            for display_name in field.display_names:
                if display_name in parsed_data:
                    try:
                        result[field.name] = field.parser(parsed_data[display_name])
                    except ValueError as error:
                        raise ValueError(f"**{display_name}**: {error}") from error
                    used_keys.add(display_name)
                    match_found = True
                    break
            if not match_found:
                if field.required:
                    raise ValueError(
                        f"Required field **{field.name}** not found in the section."
                    )
                else:
                    # Even more sensible empty defaults
                    if field.default is not SCHEMA_DEFAULT_UNSET:
                        result[field.name] = field.default
                    else:
                        return_type = field.parser.__annotations__.get("return", None)
                        origin = get_origin(return_type)

                        if origin is list:
                            result[field.name] = []
                        elif origin is dict:
                            result[field.name] = {}
                        else:
                            result[field.name] = ""

        extra_keys = set(parsed_data.keys()) - used_keys
        if extra_keys:
            raise ValueError(f"Duplicate field headings: {', '.join(sorted(extra_keys))}.")

        return result

    return parse


def version_parse() -> parser[dict[str, str]]:
    @single_line_parser
    def parse(data: str) -> dict[str, str]:
        match = re.fullmatch(
            rf"- (?:(?P<base>{VERSIONS})(?:; (?P<mods>{VERSIONS}) \(with modifications\))?|"
            rf"(?P<mods_only>{VERSIONS}) \(with modifications\))",
            data.rstrip(),
        )
        if not match:
            raise line_error(
                "Expected a version bullet such as '- 1.21+; 1.20+ (with modifications)'.",
                data,
            )
        return {"base": match["base"] or "", "modifications": match["mods"] or match["mods_only"] or ""}

    return parse


def contributors_parse() -> parser[list[Contributor]]:
    DISCORD_ID_RE = re.compile(r"<@(\d+)>")
    MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def parse_contributor(text: str) -> dict:
        result = {
            "id": "",
            "name": "",
            "channel_link": "",
        }

        # Discord ID
        id_match = DISCORD_ID_RE.search(text)
        if id_match:
            result["id"] = id_match.group(1)

            username_lookup = CONTRIBUTOR_USERNAME_LOOKUP.get() or {}
            user_id = int(result["id"])
            name = username_lookup.get(user_id)
            if name:
                result["name"] = name

            text = DISCORD_ID_RE.sub("", text)

            # Remove empty parentheses
            text = re.sub(r"\(\s*\)", "", text)

        text = text.strip()

        # Name + channel
        link_match = MD_LINK_RE.search(text)
        if link_match:
            result["name"] = link_match.group(1).strip()
            result["channel_link"] = normalize_cdn_url(link_match.group(2).strip("<>"))
        else:
            if text:
                result["name"] = text

        if not result["id"] and not result["name"]:
            raise ValueError(f"Invalid contributor: {text!r}")

        return result

    def parse_contribution(text: str) -> dict:
        result = {
            "contribution": "",
            "contribution_link": "",
        }

        link_match = MD_LINK_RE.search(text)
        if link_match:
            result["contribution"] = link_match.group(1).strip()
            result["contribution_link"] = normalize_cdn_url(
                link_match.group(2).strip("<>")
            )
        else:
            result["contribution"] = text.strip()

        return result

    @single_line_parser
    def parse(data: str) -> list[Contributor]:
        text = data

        # Remove leading "- "
        if text.startswith("- "):
            text = text[2:].strip()

        # Split contributors / contributions
        if ": " in text:
            contributors_part, contributions_part = text.split(": ", 1)
        else:
            contributors_part, contributions_part = text, ""

        contributor_chunks = [c.strip() for c in contributors_part.split(",")]
        contribution_chunks = (
            [c.strip() for c in contributions_part.split(",")]
            if contributions_part
            else [""]
        )

        contributors = [parse_contributor(c) for c in contributor_chunks]
        contributions = [parse_contribution(c) for c in contribution_chunks]

        # Cartesian product # ai made that comment but it sounded smart so i kept it
        results: list[Contributor] = []
        for c in contributors:
            for contrib in contributions:
                results.append(
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "channel_link": c["channel_link"],
                        "contribution": contrib["contribution"],
                        "contribution_link": parse_link(contrib["contribution_link"]),
                    }
                )

        return results

    return parse


def strict_subsections(data: section, allowed: set[str]) -> dict_section:
    sections = prefix_dict_parse("### ")(data)
    for heading, lines in sections.items():
        if heading and heading not in allowed:
            raise ValueError(f"Unexpected subsection **{heading}**.")
        if not lines:
            raise ValueError(f"Subsection **{heading}** has no content.")
    return sections


def check_measurement_text(text: str) -> None:
    if re.search(r"\bfigures?\s+\d", text, re.IGNORECASE) or re.match(
        r"(?:see|refer to)\b", text, re.IGNORECASE
    ):
        raise line_error("Put figure, table, and other references under '### Notes'.", text)


def rates_section_parser() -> parser[dict]:
    def parse(data: section) -> dict:
        sections = strict_subsections(data, {"Consumes", "Notes"})
        result = {"drops": [], "consumption": [], "notes": []}
        for heading, key in (("", "drops"), ("Consumes", "consumption")):
            try:
                nodes = parse_nested_list(sections.get(heading, []), allow_numbered=False)
                walk_rates(nodes, [], "", result[key])
            except ValueError as error:
                if heading:
                    raise ValueError(f"**{heading}**: {error}") from error
                raise
        result["notes"] = serialize_nodes(parse_nested_list(sections.get("Notes", [])))
        return result

    return parse


RATE_VALUE = rf"(?P<amount>{NUMBER})(?P<unit>[kKmM]?)/(?P<interval>[^\s(]+)(?:\s+\((?P<note>[^)]+)\))?"
RATE_LINE_RE = re.compile(
    rf"(?:\((?P<version>{VERSIONS})\)\s+)?(?P<items>[^:(]+?)"
    rf"(?:\s*\((?P<condition>[^)]+)\))?\s*:\s*{RATE_VALUE}"
)


def parse_rate_value(match: re.Match, text: str) -> dict:
    interval = match["interval"]
    if any(not part for part in interval.split("/")):
        raise line_error("Rate intervals need a single slash between parts, such as 'plant/h'.", text)
    if not re.fullmatch(r"[\w.+-]+(?:/[\w.+-]+)*", interval):
        raise line_error("Invalid rate interval. Use an interval such as 'h', 'min', or 'plant/h'.", text)
    scale = {"": 1, "k": 1e3, "m": 1e6}[match["unit"].lower()]
    return {
        "amount": float(match["amount"]) * scale,
        "interval": interval,
        "note": match["note"] or "",
    }


def parse_rate_line(text: str) -> dict:
    match = RATE_LINE_RE.fullmatch(text)
    if not match:
        raise line_error("Expected a rate such as 'Iron Ingot: 1.2k/h'.", text)
    return {
        "version": match["version"] or "",
        "items": parse_drop_field()([match["items"].strip()]),
        "conditions": match["condition"] or "",
        **parse_rate_value(match, text),
    }


def walk_rates(nodes: list[ListNode], variants: list[str], version: str, out: list[dict]):
    for node in nodes:
        text = node.text
        check_measurement_text(text)
        version_match = re.fullmatch(rf"\(({VERSIONS})\)", text)
        if version_match or text.endswith(":"):
            if not node.children or text == ":":
                raise line_error("A rate group needs a label and at least one nested rate.", text)
            if version_match:
                walk_rates(node.children, variants, version_match[1], out)
            else:
                walk_rates(node.children, [*variants, text[:-1].rstrip()], version, out)
            continue

        rate = parse_rate_line(text)
        rate["variants"] = variants
        rate["version"] = rate["version"] or version
        out.append(rate)

        for child in node.children:
            check_measurement_text(child.text)
            match = re.fullmatch(RATE_VALUE, child.text)
            if not match or child.children:
                raise line_error("Only an alternate interval such as '12/min' may follow a rate as a child bullet.", child.text)
            out.append({**rate, **parse_rate_value(match, child.text)})


def parse_drop_field() -> parser[dict[str, list[str] | str]]:
    @single_line_parser
    def parse(data: str) -> dict[str, list[str] | str]:
        text = data.strip()
        if "/" in text:
            item_names = [x.strip() for x in text.split("/")]
            _type = "exclusive"
        elif "," in text:
            item_names = [x.strip() for x in text.split(",")]
            _type = "concurrent"
        else:
            item_names = [text]
            _type = "concurrent"  # single drop can be treated as concurrent
        if not all(item_names):
            raise line_error("Rate item names cannot be empty.", text)
        return {"type": _type, "names": item_names}

    return parse


LAG_ENVIRONMENT_RE = re.compile(
    rf"Test environment: CPU ((?:(?! with | in | using ).)+?)"
    rf"( with Lithium)?(?: in ({VERSIONS}))?(?: using (.+))?"
)


def parse_lag_section(data: section) -> dict:
    result = {
        "environment": {"cpu": "", "has_lithium": False, "version": ""},
        "idle": [],
        "active": [],
        "notes": [],
    }
    sections = strict_subsections(data, {"Notes"})
    nodes = parse_nested_list(sections.get("", []), allow_numbered=False)

    default_variant = ""
    seen = set()
    for index, node in enumerate(nodes):
        text = node.text
        check_measurement_text(text)
        if text.startswith("Test environment"):
            match = LAG_ENVIRONMENT_RE.fullmatch(text)
            if not match or node.children or index != 0:
                raise line_error(
                    "Start Lag Info with 'Test environment: CPU model', optionally followed by 'with Lithium', 'in VERSION', or 'using VARIANT'.",
                    text,
                )
            cpu, lithium, version, variant = match.groups()
            result["environment"] = {"cpu": cpu, "has_lithium": bool(lithium), "version": version or ""}
            default_variant = variant or ""
            continue

        label, colon, value = text.partition(":")
        if not colon or label not in {"Idle", "Active"}:
            raise line_error("Expected an Idle or Active reading. Put variants under 'Idle:' or 'Active:'.", text)
        if label in seen:
            raise line_error(f"Combine duplicate {label} entries under a single '{label}:' heading.", text)
        seen.add(label)
        readings = result[label.lower()]
        if not value.strip() and node.children:
            walk_lag(node.children, [], readings, default_variant)
            continue

        match = re.fullmatch(rf" *({NUMBER})mspt", value)
        if not match or node.children:
            raise line_error(f"Expected '{label}: 1.2mspt' or an indented list of {label.lower()} readings.", text)
        readings.append({"conditions": [default_variant] if default_variant else [], "lag": float(match[1])})

    result["notes"] = serialize_nodes(parse_nested_list(sections.get("Notes", [])))
    return result


def walk_lag(nodes: list[ListNode], conditions: list[str], out: list[dict], default_variant: str):
    for node in nodes:
        text = node.text
        check_measurement_text(text)
        match = re.fullmatch(rf"(.+?):\s*({NUMBER})mspt", text)
        if match and not node.children:
            out.append({"conditions": [*conditions, match[1].strip()], "lag": float(match[2])})
        elif (match := re.fullmatch(rf"({NUMBER})mspt", text)) and not node.children:
            suffix = [default_variant] if default_variant else []
            out.append({"conditions": conditions + suffix, "lag": float(match[1])})
        elif text.endswith(":") and text != ":" and node.children:
            walk_lag(node.children, [*conditions, text[:-1].rstrip()], out, default_variant)
        else:
            raise line_error("Expected a variant reading such as 'Base version: 1.2mspt'.", text)


def videos_parse() -> parser[list[dict[str, str]]]:
    def parse(data: list[str]) -> list[dict[str, str]]:
        result = []
        for line in data:
            if not line.startswith("- "):
                raise line_error("Expected an unindented video link bullet.", line)

            text = line[2:].strip()

            m = re.fullmatch(rf"\[([^\]]+)\]\(<({URL})>\)", text)
            if not m or not m[1].strip():
                raise line_error("Expected '[Video Title](<https://…>)' with a caption.", line)

            result.append(
                {
                    "name": m.group(1),
                    "url": normalize_cdn_url(m.group(2)),
                }
            )

        return result

    return parse


FILE_HEADINGS = {
    "Schematic": "schematics", "Schematics": "schematics",
    "World Download": "world_downloads", "World Downloads": "world_downloads",
    "Image": "images", "Images": "images",
}
MARKDOWN_FILE_LINK_RE = re.compile(rf"\[([^\]]+)\]\((<{URL}>|https?://[^\s<>()]+)\)")


def read_file_links(text: str, *, images: bool, group_caption: str = "") -> list[FileTreeNode]:
    caption = ""
    text = text.strip()
    source = text
    if not MARKDOWN_FILE_LINK_RE.fullmatch(text):
        version = re.fullmatch(rf"(\({VERSIONS}\))\s+({URL_TOKEN})", text)
        prefix = re.fullmatch(r"([^<>]+?): +(.+)", text)
        if label := version or prefix:
            caption, text = label.groups()
            caption = caption.strip(": ")
    if match := MARKDOWN_FILE_LINK_RE.fullmatch(text):
        caption = match[1].strip() or caption
        urls = [match[2].strip("<>")]
    elif BARE_LINKS_RE.fullmatch(text):
        urls = [token.strip("<>") for token in text.split()]
    else:
        raise line_error("Expected a caption followed by a file URL, or a labeled Markdown link.", source)
    if not (caption or group_caption):
        raise line_error("A file link needs a caption, version, or descriptive link label.", source)
    if len(urls) > 1 and not images:
        raise line_error("List each schematic or world download on its own captioned bullet.", source)
    files = []
    for url in urls:
        url = normalize_cdn_url(url)
        files.append({"type": "file", "name": url.split("/")[-1], "url": parse_link(url), "note": caption})
    return files


def files_from_nodes(nodes: list[ListNode], *, images: bool) -> list[FileTreeNode]:
    files = []
    for node in nodes:
        text = node.text
        if node.children:
            if extract_urls(text) or not (text.endswith(":") or re.fullmatch(rf"\({VERSIONS}\)", text)):
                raise line_error("Use a caption or version as a group heading, with file links below it.", text)
            name = text.removesuffix(":").strip()
            if not name:
                raise line_error("A file group needs a caption.", text)
            files.append({"type": "folder", "name": name, "children": files_from_nodes(node.children, images=images)})
            continue

        files.extend(read_file_links(text, images=images))
    return files


def parse_files(data: section) -> dict:
    result = {"schematics": [], "world_downloads": [], "images": []}
    seen = set()
    for node in parse_nested_list(data, allow_numbered=False):
        label, colon, links = node.text.partition(":")
        if label not in FILE_HEADINGS or not colon:
            raise line_error("Expected a file-type caption such as 'Schematic:', 'World Download:', or 'Image:'.", node.text)
        kind = FILE_HEADINGS[label]
        if kind in seen:
            raise line_error(f"Combine duplicate {label} captions into one file group.", node.text)
        seen.add(kind)
        links = links.strip()
        if links and not node.children:
            result[kind] = read_file_links(links, group_caption=label, images=kind == "images")
        elif not links and node.children:
            result[kind] = files_from_nodes(node.children, images=kind == "images")
        else:
            raise line_error("Provide inline file links or an indented file list under this caption.", node.text)

    for required in ("schematics", "images"):
        if not result[required]:
            raise ValueError(f"Missing required file group **{required}**.")
    return result


def figures_parse() -> parser[list[dict]]:
    file_types = {
        "mov": "video",
        "mp4": "video",
        "webm": "video",
        "jpg": "image",
        "png": "image",
        "gif": "video",
    }

    def parse(data: section) -> list[dict]:
        figures: list[dict] = []

        seen = set()
        for line in data:
            match = re.fullmatch(rf"- \*Figure +([1-9]\d*)\.\* +({URL_TOKEN})", line.rstrip(), re.IGNORECASE)
            if not match:
                raise line_error("Expected one figure link in the form '- *Figure 1.* https://…'.", line)
            figure_number = int(match[1])
            if figure_number in seen:
                raise line_error(f"Duplicate figure number {figure_number}.", line)
            seen.add(figure_number)
            normalized_url = normalize_cdn_url(match[2].strip("<>"))
            name = urlsplit(normalized_url).path.rsplit("/", 1)[-1]
            extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if extension not in file_types:
                raise line_error(f"Unsupported figure file extension {extension or '(none)'!r}.", line)
            figures.append({
                "url": normalized_url,
                "name": name,
                "figure_number": figure_number,
                "file_type": file_types[extension],
            })
        return figures

    return parse


message_parse_schema = dict_postprocess_parse(
    prefix_dict_parse("# "),
    schema_dict_parse(
        parse_post_sections,
        [
            SchemaItem(
                ["Designer", "Designers", "Designer(s)"],
                "designers",
                list_postprocess_flattened_parse(list_parse(), contributors_parse()),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Credits", "Credit"],
                "credits",
                list_postprocess_flattened_parse(list_parse(), contributors_parse()),
                required=False,
                default=[],
            ),
            SchemaItem(["Versions"], "versions", version_parse()),
            SchemaItem(
                ["Rates"],
                "rates",
                rates_section_parser(),
                required=False,
                default={"drops": [], "consumption": [], "notes": []},
            ),
            SchemaItem(
                ["Lag Info"],
                "lag_info",
                parse_lag_section,  # Pass the section directly
                required=False,
                default=None,
            ),
            SchemaItem(
                ["Video Links", "Video Link"],
                "video_links",
                videos_parse(),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Files"],
                "files",
                parse_files,
            ),
            SchemaItem(
                ["Description"],
                "description",
                lambda data: serialize_nodes(parse_nested_list(data)),
            ),
            SchemaItem(
                ["Positives"],
                "positives",
                lambda data: serialize_nodes(parse_nested_list(data)),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Negatives"],
                "negatives",
                lambda data: serialize_nodes(parse_nested_list(data)),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Design Specifications"],
                "design_specifications",
                lambda data: serialize_nodes(parse_nested_list(data)),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Instructions"],
                "instructions",
                schema_dict_parse(
                    prefix_dict_parse("### "),
                    [
                        SchemaItem(
                            ["Notes"],
                            "notes",
                            lambda data: serialize_nodes(parse_nested_list(data)),
                            required=False,
                            default=[],
                        ),
                        SchemaItem(
                            ["Build"],
                            "build",
                            lambda data: serialize_nodes(parse_nested_list(data)),
                            required=False,
                            default=[],
                        ),
                        SchemaItem(
                            ["How to Use", "How to use", "Usage"],
                            "usage",
                            lambda data: serialize_nodes(parse_nested_list(data)),
                            required=False,
                            default=[],
                        ),
                    ],
                ),
                required=False,
                default=[],
            ),
            SchemaItem(
                ["Figures"], "figures", figures_parse(), required=False, default=[]
            ),
        ],
    ),
)


def parse_crosspost(data: section) -> str | None:
    """Validate a crosspost and return the thread ID of its original post."""
    lines = [line.rstrip() for line in data if line.strip()]
    if not lines or not re.fullmatch(r"## +Original Post", lines[0].lstrip()):
        return None
    if len(lines) < 3 or lines[2] != "## Image":
        unexpected = lines[2] if len(lines) >= 3 else "(missing heading)"
        raise line_error("Crossposts need a single '## Image' section after the original post link.", unexpected)
    if len(lines) != 4:
        unexpected = lines[4] if len(lines) > 4 else "(missing image link)"
        raise line_error("Crossposts must contain exactly one image link.", unexpected)
    original = re.fullmatch(rf"- ({URL_TOKEN})", lines[1])
    target = discord_target(original[1].strip("<>")) if original else None
    if not target or target.kind != "channel":
        raise line_error("Expected one Discord thread link under '## Original Post'.", lines[1])
    if not re.fullmatch(rf"- {URL_TOKEN}", lines[3]):
        raise line_error("Expected one image URL under '## Image'.", lines[3])
    return str(target.channel_id)


def message_parse(data: section) -> Message:
    if parse_crosspost(data) is not None:
        raise ValueError("Crosspost")

    parsed = message_parse_schema(data)

    if len(parsed) != 1:
        raise ValueError("Multiple variants in post")

    post_data = next(iter(parsed.values()))
    attach_discord_links(post_data)
    return post_data


if __name__ == "__main__":
    metadata_map = {
        "channel_id": "channel_id",
        "id": "thread_id",
        "slug": "",
        "title": "thread_name",
        "author": "author_id",
        "author_name": "author_name",
        "created_at": "created_at",
        "tags": "tags",
    }

    whitelisted_channels = {
        # Monsters
        1374185936564256768,  # overworld-monsters
        1310484985546805319,  # slime
        1374189324626821141,  # nether-monsters
        1262787177432092783,  # gold-and-barter
        1311841461029044326,  # fortress-monsters
        1374193787437322322,  # end-monsters
        # Creatures
        1162390388976394240,  # villagers
        1162119562922315856,  # iron
        1374195641374347344,  # animals
        1374197188791631883,  # bees
        1374199361751482470,  # aquatic-creatures
        # Agriculture
        1366955484401242192,  # trees-and-leaves
        1375250019216523264,  # mushrooms-and-fungi
        1358146379708370984,  # moss-and-aquatic-plants
        1358146101353381978,  # tall-plants
        1358145991169147133,  # crops
        1358146247680327902,  # flowers-and-grasses
        # Blocks & Items
        1376314653788868669,  # stone
        1376642039256711329,  # gravity-blocks
        1374233269171916841,  # block-converters
        1374233112841682974,  # obsidian-and-lava
        1374233064384757800,  # snow-and-ice
        1374233292332732498,  # item-dupers
        1376632527703375973,  # dirts
        # Item Processing
        1378800846250184944,  # storage-systems
        1379588677948408012,  # furnace-arrays
        1379704764471967785,  # potion-brewers
        1266037379920167073,  # crafting
        # Infrastructure
        1383836451980050442,  # chunk-loading
        1431068303228669952,  # mob-switches
        1386442783338004501,  # infrastructure
        1386748149531541698,  # terrain-clearing
        1431451350826487940,  # entity-transport
    }

    failed: Counter[str] = Counter()
    authors: Counter[str] = Counter()

    def decode_entry(entry: dict[str, str | int | section]) -> dict | None:
        channel_id = int(entry["channel_id"])
        if channel_id not in whitelisted_channels:
            return None

        result = {k: entry.get(v, None) for k, v in metadata_map.items()}

        try:
            messages = entry["messages"]
            if not messages:
                raise ValueError("No messages")

            lines = "\n".join(messages).split("\n")
            if parse_crosspost(lines) is not None:
                return None
            parsed = message_parse(lines)

            if not parsed:
                raise ValueError("No parsable content")

            # Merge parsed message content
            result.update(parsed)
            return result

        except Exception as e:
            print(
                f"{entry['author_id']}, "
                f"https://discord.com/channels/1161803566265143306/{entry['thread_id']}, "
                f'"{type(e).__name__}: {e}"'
            )
            authors[f"<@{entry['author_id']}>"] += 1
            failed[
                f"https://discord.com/channels/1161803566265143306/{channel_id}"
            ] += 1
            return None

    # Load Archive
    with open("data/archive_backup.json", encoding="utf-8") as file:
        data = json.load(file)

    # Process entries
    for entry in data:
        result = decode_entry(entry)
        if result is None:
            continue

        out_path = f"data/out/{result['id']}.json"
        with open(out_path, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=4)

    # Summary
    print(f"Failed posts: {failed.total()}")
    print("Failures by channel:")
    for k, v in failed.items():
        print(f"  {k}: {v}")

    print("\nFailures by author:")
    for author, count in authors.most_common():
        print(f"  {author}: {count}")
