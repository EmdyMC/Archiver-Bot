import json
import re

# import traceback
from collections import Counter, defaultdict
from functools import wraps
from typing import Callable
from dataclasses import dataclass

from MessageDict import Message

type section = list[str]
type dict_section = dict[str, section]
type parser[U] = Callable[[section], U]


@dataclass
class SchemaItem[T]():
    display_names: list[str]
    name: str
    parser: parser[T]
    required: bool = True
    default: T | None = None


@dataclass
class ListNode:
    text: str
    children: list["ListNode"]
    list_type: str  # "dashed" | "numbered"

    def to_dict(self) -> dict:
        return {
            "list_type": self.list_type,
            "text": self.text,
            "children": [c.to_dict() for c in self.children],
        }


def serialize_nodes(nodes: list[ListNode]) -> list[dict]:
    return [n.to_dict() for n in nodes]


def identity[T](x: T) -> T:
    return x


def safe_predicate(data: section) -> bool:
    parsed_dict = list_dict_parse()(data)
    if not parsed_dict:
        return False
    first_val = next(iter(parsed_dict.values()), [])
    return bool(first_val and ": " in first_val[0])


def single_line_parser[T](function: Callable[[str], T]) -> parser[T]:
    @wraps(function)
    def wrapper(data: section) -> T:
        if len(data) != 1:
            raise ValueError(
                f"Single line parse for expected one line of input, got {data!r}."
            )
        return function(data[0])

    return wrapper


def list_postprocess_parse[T](
    parser_: parser[list[section]], postprocessor: parser[T]
) -> parser[list[T]]:
    return lambda data: [postprocessor(x) for x in parser_(data)]


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
            if line.startswith(prefix):
                current_key = line[len(prefix) :].strip()
            else:
                parsed_data[current_key].append(line)
        return dict(parsed_data)

    return parse


def list_parse() -> parser[list[section]]:
    # Assume one level list
    def parse(data: section) -> list[section]:
        if not all(line.lstrip().startswith("- ") for line in data):
            raise ValueError("Incorrect list formatting.")
        return [[line.lstrip()[2:]] for line in data]

    return parse


def flattened_list_parse() -> parser[section]:
    def parse(data: section) -> section:
        # All parsers accept a section type, so list_parse returns a list[section] where each section is one line. This parse function is used for the files fields and should be flattened since it's directly stored and not parsed again.
        return [ls[0] for ls in list_parse()(data)]

    return parse


def parse_nested_list(data: list[str], indent: int = 0) -> list[ListNode]:
    nodes: list[ListNode] = []
    i = 0

    while i < len(data):
        line = data[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        if current_indent < indent:
            i += 1
            continue

        LIST_ITEM_RE = re.compile(r"(?P<prefix>- |\d+\. )(?P<text>.*)")
        m = LIST_ITEM_RE.match(stripped)
        if not m:
            i += 1
            continue

        prefix = m.group("prefix")
        text = m.group("text").strip()

        list_type = "dashed" if prefix == "- " else "numbered"

        i += 1

        # collect children
        children_lines = []
        while i < len(data):
            next_line = data[i]
            next_stripped = next_line.lstrip()
            next_indent = len(next_line) - len(next_stripped)

            if next_indent <= current_indent:
                break

            children_lines.append(next_line)
            i += 1

        nodes.append(
            ListNode(
                text=text,
                list_type=list_type,
                children=parse_nested_list(children_lines, current_indent + 2),
            )
        )

    return nodes


def list_dict_parse() -> parser[dict_section]:
    def parse(data: section) -> dict_section:
        result: defaultdict[str, section] = defaultdict(list)
        current_key = ""
        for line in data:
            if line.startswith("- "):
                if ": " in line:
                    # print(line[2:].split(": ", 1))
                    current_key, value = line[2:].split(": ", 1)
                    if value.strip() != "":
                        result[current_key].append("- " + value)
                else:
                    current_key = line[2:]
                    if current_key.endswith(":"):
                        current_key = current_key[:-1]
            else:
                result[current_key].append(line[2:])
        return dict(result)

    return parse


def schema_dict_parse[T](
    parser_: parser[dict_section],
    config: list[SchemaItem],
) -> parser[dict[str, T]]:
    def parse(data: section) -> dict:
        result: dict[str, T] = {}
        parsed_data = parser_(data)

        used_keys = set()

        for field in config:
            match_found = False
            for display_name in field.display_names:
                if display_name in parsed_data:
                    result[field.name] = field.parser(parsed_data[display_name])
                    used_keys.add(display_name)
                    match_found = True
                    break           
            if not match_found:
                if field.required:
                    raise ValueError(f"Required field **{field.name}** not found in the section.")
                else:
                    # Infer empty default if none provided
                    if field.default is not None:
                        result[field.name] = field.default
                    else:
                        # Sensible empty defaults
                        result[field.name] = (
                            [] if field.parser.__annotations__.get("return", None) in (list, list[str], list[dict])
                            else {} if field.parser.__annotations__.get("return", None) == dict
                            else ""
                        )
        
        extra_keys = set(parsed_data.keys()) - used_keys
        if extra_keys:
            extra_keys.discard("")
            if extra_keys:
                raise ValueError(f"Extra or unrecognised fields found: {', '.join(extra_keys)}")
        
        return result
    return parse


def variant_parse[T](
    parser_: Callable[[str], parser[list[T]]], predicate: Callable[[section], bool]
) -> parser[list[T]]:
    def parse(data: section) -> list[T]:
        # Skip rate tables
        if data[0].startswith("- See"):
            return []

        if predicate(data):
            result: list[T] = []
            for variant, data_ in list_dict_parse()(data).items():
                result.extend(parser_(variant)(data_))
            return result
        else:
            return parser_("")(data)

    return parse


def version_parse() -> parser[dict[str, str]]:
    @single_line_parser
    def parse(data: str) -> dict[str, str]:
        if not data.startswith("- "):
            raise ValueError("Incorrect version field formatting.")
        versions = data[2:].split("; ")
        result = {
            "base": "",
            "modifications": "",
        }
        for version_raw in versions:
            if "(" not in version_raw:
                version = version_raw
                section = "base"
            else:
                version = version_raw.split("(")[0]
                match version_raw.split("(")[1].rstrip(")"):
                    case "with modifications":
                        section = "modifications"
                    case _:
                        raise ValueError("Incorrect version field formatting.")
            result[section] = version.strip()
        return result

    return parse


def contributors_parse() -> parser[list[dict[str, str | int]]]:
    DISCORD_ID_RE = re.compile(r"<@(\d+)>")
    MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def parse_contributor(text: str) -> dict:
        result = {
            "id": 0,
            "name": "",
            "channel_link": "",
        }

        # Discord ID
        id_match = DISCORD_ID_RE.search(text)
        if id_match:
            result["id"] = int(id_match.group(1))
            text = DISCORD_ID_RE.sub("", text)

            # 🔧 NEW: remove leftover empty parentheses
            text = re.sub(r"\(\s*\)", "", text)

        text = text.strip()

        # Name + channel
        link_match = MD_LINK_RE.search(text)
        if link_match:
            result["name"] = link_match.group(1).strip()
            result["channel_link"] = link_match.group(2).strip("<>")
        else:
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
            result["contribution_link"] = link_match.group(2).strip("<>")
        else:
            result["contribution"] = text.strip()

        return result

    @single_line_parser
    def parse(data: str) -> list[dict[str, str | int]]:
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
        results: list[dict[str, str | int]] = []
        for c in contributors:
            for contrib in contributions:
                results.append({
                    "id": c["id"],
                    "name": c["name"],
                    "channel_link": c["channel_link"],
                    "contribution": contrib["contribution"],
                    "contribution_link": contrib["contribution_link"],
                })

        return results

    return parse


def rates_section_parser() -> parser[dict]:
    def parse(data: section) -> dict:
        result = {
            "drops": [],
            "consumes": [],
            "notes": [],
        }

        sections = prefix_dict_parse("### ")(data)

        drops_data = sections.get("", [])
        if drops_data:
            walk_rates(
                parse_nested_list(drops_data),
                [],
                None,              # no version at top level
                result["drops"],
            )

        if "Consumes" in sections:
            walk_rates(
                parse_nested_list(sections["Consumes"]),
                [],
                None,
                result["consumes"],
            )

        if "Notes" in sections:
            result["notes"] = serialize_nodes(
                parse_nested_list(sections["Notes"])
            )

        return result

    return parse


def parse_rate_line(text: str):
    RATE_LINE_RE = re.compile(
        r"""
        ^                           # start
        (?:(\([^)]*\))\s*)?         # optional (Version)
        (?P<drop>[^:(]+?)           # Drop name
        (?:\s*\((?P<condition>[^)]*)\))?   # optional (Condition)
        \s*:\s*
        (?P<rate>[\d\.]+)(?P<unit>[kKmM]?) # Rate
        /
        (?P<interval>[^\s(]+)       # Interval
        (?:\s*\((?P<note>[^)]*)\))? # optional (Note)
        \s*$
        """,
        re.VERBOSE
    )

    m = RATE_LINE_RE.match(text)
    if not m:
        raise ValueError(f"Invalid rate line: {text!r}")

    rate = float(m.group("rate"))
    unit = {
        "": 1,
        "k": 1e3,
        "m": 1e6,
    }[m.group("unit").lower()]

    version = (m.group(1) or "").strip("()")

    return {
        "version": version,
        "drop": m.group("drop").strip(),
        "conditions": m.group("condition") or "",
        "rates": float(rate * unit),
        "interval": m.group("interval"),
        "note": m.group("note") or "",
    }


def walk_rates(
    nodes: list[ListNode],
    variants: list[str],
    version: str | None,
    out: list[dict],
):
    for node in nodes:
        text = node.text.strip()

        # Version-only node "(1.21.2+)"
        version_match = re.fullmatch(r"\(([^)]+)\)", text)
        if version_match:
            walk_rates(
                node.children,
                variants,
                version_match.group(1),
                out,
            )
            continue

        # Variant node
        if text.endswith(":"):
            walk_rates(
                node.children,
                variants + [text.rstrip(":").strip()],
                version,
                out,
            )
            continue

        # Leaf rate entry
        rate_data = parse_rate_line(text)

        out.append({
            "variants": variants.copy(),
            "version": rate_data["version"] or (version or ""),
            "drop": rate_data["drop"],
            "conditions": rate_data["conditions"],
            "rates": rate_data["rates"],
            "interval": rate_data["interval"],
            "note": rate_data["note"],
        })


def parse_lag_section(data: section) -> dict:
    result = {
        "environment": {"cpu": "", "has_lithium": False, "version": ""},
        "idle": [],
        "active": [],
        "notes": [],
    }

    default_variant = ""

    # Split by ### headers
    sections = prefix_dict_parse("### ")(data)

    # Main lines
    main_lines = sections.get("", [])
    main_nodes = parse_nested_list(main_lines)

    for node in main_nodes:
        text = node.text.strip()

        # Environment
        if text.startswith("Test environment: CPU"):
            m = re.match(
                r"Test environment: CPU (.*?)( with Lithium)?( in (.*?))?( using (.*))?$",
                text
            )
            if m:
                result["environment"]["cpu"] = m.group(1)
                result["environment"]["has_lithium"] = bool(m.group(2))
                result["environment"]["version"] = m.group(4) or ""
                default_variant = (m.group(6) or "").strip()
            continue

        # Flat lag entries
        m = re.match(r"(Idle|Active):\s*([\d\.]+)mspt", text)
        if m:
            section_name = m.group(1).lower()
            lag = float(m.group(2))
            result[section_name].append({
                "conditions": [default_variant] if default_variant else [],
                "lag": lag
            })
            continue

        # Nested entries
        key = node.text.lower().rstrip(":").strip()
        if key in result:
            walk_lag(node.children, [], result[key], default_variant=default_variant)

    # Notes
    if "Notes" in sections:
        notes_lines = sections["Notes"]
        result["notes"] = serialize_nodes(parse_nested_list(notes_lines))

    return result


def walk_lag(nodes, conditions, out, default_variant=""):
    for node in nodes:
        # Match "Label: 6mspt"
        m = re.match(r"(.*?):\s*([\d\.]+)\s*mspt", node.text)
        if m:
            label = m.group(1).strip()
            lag = float(m.group(2))
            # Use label as condition if present, otherwise default_variant
            conds = [label] if label else ([default_variant] if default_variant else [])
            out.append({
                "conditions": conditions + conds,
                "lag": lag,
            })
            continue

        # Match bare "6mspt"
        lag_match = re.search(r"([\d\.]+)\s*mspt", node.text)
        if lag_match:
            out.append({
                "conditions": conditions + ([default_variant] if default_variant else []),
                "lag": float(lag_match.group(1)),
            })
            continue

        # Otherwise, descend and treat this node as variant context
        walk_lag(
            node.children,
            conditions + [node.text.rstrip(":")],
            out,
            default_variant=default_variant
        )


def videos_parse() -> parser[dict[str, str]]:
    def parse(data: list[str]) -> dict[str, str]:
        result = []
        for line in data:
            if not line.startswith("- "):
                raise ValueError("Incorrect video links field formatting.")
            
            text = line[2:].strip()

            m = re.match(r"\[(.*?)\]\(<(.*?)>\)", text)
            if not m:
                raise ValueError(f"Invalid video link format: {data!r}")

            result.append({
                "name": m.group(1),
                "url": m.group(2),
            })
        
        return result

    return parse


def files_from_nodes(nodes: list[ListNode]) -> list[dict]:
    result = []

    for node in nodes:
        urls = re.findall(r"(https?://\S+)", node.text)

        if urls:
            # Note only applies if there's exactly one file
            note = ""
            if len(urls) == 1:
                note = node.text[:node.text.find(urls[0])].strip(": ")

            for url in urls:
                result.append({
                    "type": "file",
                    "name": url.split("/")[-1],
                    "url": url,
                    "note": note if len(urls) == 1 else "",
                })
        else:
            result.append({
                "type": "folder",
                "name": node.text.rstrip(":"),
                "children": files_from_nodes(node.children),
            })

    return result


def figures_parse() -> parser[list[str]]:
    def parse(data: section) -> list[str]:
        urls: list[str] = []

        for line in data:
            stripped = line.lstrip()
            if not stripped.startswith("- "):
                continue

            # Extract URL
            match = re.search(r"(https?://\S+)", stripped)
            if match:
                urls.append(match.group(1))

        return urls

    return parse


message_parse_schema = dict_postprocess_parse(
    prefix_dict_parse("# "),
    schema_dict_parse(
        prefix_dict_parse("## "),
        [
            SchemaItem(
                ["Designer", "Designers", "Designer(s)"],
                "designers",
                list_postprocess_parse(list_parse(), contributors_parse()),
                required=False,),
            SchemaItem(
                ["Credits", "Credit"],
                "credits",
                list_postprocess_parse(list_parse(), contributors_parse()),
                required=False,),
            SchemaItem(["Versions"], "versions", version_parse()),
            SchemaItem(
                ["Rates"],
                "rates",
                rates_section_parser(),
                required=False),
            SchemaItem(
                ["Lag Info"],
                "lag_info",
                parse_lag_section,  # Pass the section directly
                required=False,),
            SchemaItem(["Video Links", "Video Link"], "video_links", videos_parse(), required=False),
            SchemaItem(
                ["Files"],
                "files",
                schema_dict_parse(
                    list_dict_parse(),   # Schematics / World Downloads / Images
                    [
                        SchemaItem(
                            ["Schematic", "Schematics"],
                            "schematics",
                            lambda data: files_from_nodes(parse_nested_list(data)),
                        ),
                        SchemaItem(
                            ["World Download", "World Downloads"],
                            "world_downloads",
                            lambda data: files_from_nodes(parse_nested_list(data)),
                            required=False,
                        ),
                        SchemaItem(
                            ["Image", "Images"],
                            "images",
                            lambda data: files_from_nodes(parse_nested_list(data)),
                        ),
                    ],
                )),
            SchemaItem(["Description"], "description", lambda data: serialize_nodes(parse_nested_list(data))),
            SchemaItem(["Positives"], "positives", lambda data: serialize_nodes(parse_nested_list(data)), required=False),
            SchemaItem(["Negatives"], "negatives", lambda data: serialize_nodes(parse_nested_list(data)), required=False),
            SchemaItem(["Design Specifications"], "design_specifications", lambda data: serialize_nodes(parse_nested_list(data)), required=False),
            SchemaItem(["Instructions"], "instructions", schema_dict_parse(
                prefix_dict_parse("### "),
                [
                    SchemaItem(
                        ["Notes"],
                        "notes",
                        lambda data: serialize_nodes(parse_nested_list(data)),
                        required=False),
                    SchemaItem(
                        ["Build"],
                        "build",
                        lambda data: serialize_nodes(parse_nested_list(data)),
                        required=False),
                    SchemaItem(
                        ["How to Use", "How to use", "Usage"],
                        "usage",
                        lambda data: serialize_nodes(parse_nested_list(data)),
                        required=False),
                ],
            ), required=False),
            SchemaItem(["Figures"], "figures", figures_parse(), required=False),
        ],
    ),
)


def message_parse(data: section) -> list[Message]:
    # Filter crossposts
    if data and any(line.strip().endswith("Original Post") for line in data[:2]):
        return []
    return [rest for _, rest in message_parse_schema(data).items()]


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
        1374185936564256768, #overworld-monsters
        1310484985546805319, #slime
        1374189324626821141, #nether-monsters
        1262787177432092783, #gold-and-barter
        1311841461029044326, #fortress-monsters
        1374193787437322322, #end-monsters
        # Creatures
        1162390388976394240, #villagers
        1162119562922315856, #iron
        1374195641374347344, #animals
        1374197188791631883, #bees
        1374199361751482470, #aquatic-creatures
        # Agriculture
        1366955484401242192, #trees-and-leaves
        1375250019216523264, #mushrooms-and-fungi
        1358146379708370984, #moss-and-aquatic-plants
        1358146101353381978, #tall-plants
        1358145991169147133, #crops
        1358146247680327902, #flowers-and-grasses
        # Blocks & Items
        1376314653788868669, #stone
        1376642039256711329, #gravity-blocks
        1374233269171916841, #block-converters
        1374233112841682974, #obsidian-and-lava
        1374233064384757800, #snow-and-ice
        1374233292332732498, #item-dupers
        1376632527703375973, #dirts
        # Item Processing
        1378800846250184944, #storage-systems
        1379588677948408012, #furnace-arrays
        1379704764471967785, #potion-brewers
        1266037379920167073, #crafting
        # Infrastructure
        1383836451980050442, #chunk-loading
        1431068303228669952, #mob-switches
        1386442783338004501, #infrastructure
        1386748149531541698, #terrain-clearing
        1431451350826487940, #entity-transport
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

            # Crossposts
            if messages[0].startswith("## Original Post"):
                raise ValueError("Crosspost")

            raw_text = "\n".join(messages)
            parsed = message_parse(raw_text.split("\n"))

            if not parsed:
                raise ValueError("No parsable content")

            if len(parsed) > 1:
                raise ValueError("Multiple variants in post")

            # Merge parsed message content
            result.update(parsed[0])
            return result

        except Exception as e:
            print(
                f'{entry["author_id"]}, '
                f'https://discord.com/channels/1161803566265143306/{entry["thread_id"]}, '
                f'"{type(e).__name__}: {e}"'
            )
            authors[f'<@{entry["author_id"]}>'] += 1
            failed[f'https://discord.com/channels/1161803566265143306/{channel_id}'] += 1
            return None

    # Load Archive
    with open("data/archive_backup.json", encoding="utf-8") as file:
        data = json.load(file)

    # Process entries
    for entry in data:
        result = decode_entry(entry)
        if result is None:
            continue

        out_path = f'data/out/{result["id"]}.json'
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
