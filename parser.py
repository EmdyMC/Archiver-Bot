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


def identity[T](x: T) -> T:
    return x


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


def safe_predicate(data: section) -> bool:
    parsed_dict = list_dict_parse()(data)
    if not parsed_dict:
        return False
    first_val = next(iter(parsed_dict.values()), [])
    return bool(first_val and ": " in first_val[0])


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
            "modifications": ""
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
            result[section] = version
        return result

    return parse


def contributor_parse() -> parser[dict[str, str | int]]:
    @single_line_parser
    def parse(data: str) -> dict[str, str | int]:
        result: dict[str, str | int] = {
            "id": 0,
            "name": "",
            "channel_link": "",
            "contribution": "",
            "contribution_link": "",
        }
        user_id_match = re.match(r"^<@(\d+?)>", data)
        if user_id_match:
            result["id"] = int(user_id_match.group(1))
            if data[user_id_match.end() :].startswith(": "):
                result["contribution"] = data[user_id_match.end() + 2 :]
        url_match = re.match(r"^\[(.*?)\]\((.*?)\)", data)
        if url_match:
            result["id"] = url_match.group(1)
            result["channel_link"] = url_match.group(2)
            if data[url_match.end() :].startswith(": "):
                result["contribution"] = data[url_match.end() + 2 :]
        return result

    return parse



def rates_value_parse() -> parser[tuple[float, str, str]]:
    @single_line_parser
    def parse(x: str) -> tuple[float, str, str]:
        if not x.startswith("- "):
            raise ValueError(f"Rates section format error, expected '- ', got {x!r}.")
        x = x[2:]

        rates_match = re.match(
            r"^([\d\.]+)([kKmM]?)\/([^\s\(]+)(?: \((.*)\))?\s*$",
            x
        )
        if rates_match is None:
            raise ValueError(f"Rates value regex doesn't match, got {x!r}.")
        rate = float(rates_match.group(1))
        unit = {
            "": 1,
            "k": 1e3,
            "m": 1e6,
        }[rates_match.group(2).lower()]
        interval = rates_match.group(3)
        note = rates_match.group(4) or ""

        return (rate * unit, interval, note)

    return parse


def rates_parse(variant: str) -> parser[list[dict]]:
    def parse(data: section) -> list[dict]:
        result: list[dict] = []
        for drop, (rate, interval, note) in dict_postprocess_parse(
            list_dict_parse(), rates_value_parse()
        )(data).items():
            drop_match = re.match(r"(\((.*)\) )?(.*)( \((.*)\))?", drop)
            assert drop_match is not None  # That regex never fails to match
            result.append(
                {
                    "variant": variant,
                    "version": drop_match.group(2) or "",
                    "drop": drop_match.group(3) or "",
                    "condition": drop_match.group(5) or "",
                    "rates": rate,
                    "interval": interval,
                    "note": note,
                }
            )
        return result

    return parse

def parse_lag_section(lines: list[str], default_variant: str) -> list[dict]:
    result = []

    for line in lines:
        stripped = line.lstrip()
        content = stripped[2:].strip() if stripped.startswith("- ") else stripped

        # Nested variant entry: 'Scaffolding: 6mspt'
        if ": " in content:
            variant, lag_str = content.split(": ", 1)
            lag_match = re.search(r"[\d\.]+", lag_str)
            if lag_match:
                result.append({
                    "variant": variant.strip(),
                    "lag": float(lag_match.group())
                })
        else:
            # Single-line idle/active using default variant from environment
            lag_match = re.search(r"[\d\.]+", content)
            if lag_match:
                result.append({
                    "variant": default_variant,
                    "lag": float(lag_match.group())
                })

    return result


def parse_lag_info(lines: list[str]) -> dict:
    environment = {"cpu": "", "has_lithium": False, "version": ""}
    idle_lines, active_lines, notes_lines = [], [], []
    default_variant = ""

    current_section = None  # None | "idle" | "active" | "notes"

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # --- Environment ---
        if stripped.startswith("- Test environment: CPU"):
            env_match = re.match(
                r"- Test environment: CPU (.*?)( with Lithium)?( in (.*?))?( using (.*))?$",
                stripped
            )
            if env_match:
                environment["cpu"] = env_match.group(1)
                environment["has_lithium"] = env_match.group(2) is not None
                environment["version"] = env_match.group(4) or ""
                default_variant = (env_match.group(6) or "").strip()
            current_section = None
            i += 1
            continue

        # --- Notes header ---
        if stripped.startswith("### Notes"):
            current_section = "notes"
            i += 1
            continue

        # --- Idle / Active headers ---
        m = re.match(r"- (Idle|Active):?", stripped)
        if m:
            current_section = m.group(1).lower()
            i += 1

            # collect indented children
            while i < len(lines):
                next_line = lines[i]
                next_stripped = next_line.lstrip()
                next_indent = len(next_line) - len(next_stripped)

                if next_indent <= indent:
                    break

                if current_section == "idle":
                    idle_lines.append(next_stripped[2:].strip())
                elif current_section == "active":
                    active_lines.append(next_stripped[2:].strip())

                i += 1
            continue

        # --- Notes entries ---
        if current_section == "notes" and stripped.startswith("- "):
            notes_lines.append(stripped)
            i += 1
            continue

        # --- Ignore everything else ---
        i += 1

    return {
        "environment": environment,
        "idle": parse_lag_section(idle_lines, default_variant),
        "active": parse_lag_section(active_lines, default_variant),
        "notes": notes_lines
    }


def parse_files_nested_list(data: list[str], indent: int = 0) -> list[dict]:
    nodes = []
    i = 0
    while i < len(data):
        line = data[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        if not stripped.startswith("- ") or current_indent < indent:
            i += 1
            continue

        content = stripped[2:].strip()
        i += 1

        # Collect child lines for deeper indentation
        child_lines = []
        while i < len(data):
            next_line = data[i]
            next_indent = len(next_line) - len(next_line.lstrip())
            if next_indent <= current_indent:
                break
            child_lines.append(next_line)
            i += 1

        # Try to detect a URL at the end
        url_match = re.search(r"(https?://\S+)", content)
        if url_match:
            url = url_match.group(1).strip()
            note = content[:url_match.start()].strip(": ") or None
            name = url.split("/")[-1]
            node = {
                "type": "file",
                "name": name,
                "url": url,
                "note": note,
            }
        else:
            # Folder case
            node = {
                "type": "folder",
                "name": content.rstrip(":"),
                "children": parse_files_nested_list(child_lines, indent=current_indent + 2) if child_lines else [],
            }

        nodes.append(node)

    return nodes


def files_nested_list_parser() -> parser[list[dict]]:
    return lambda data: parse_files_nested_list(data)


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
            SchemaItem(["Designer", "Designers", "Designer(s)"], "designers", list_postprocess_parse(list_parse(), contributor_parse()), required=False),
            SchemaItem(["Credits", "Credit"], "credits", list_postprocess_parse(list_parse(), contributor_parse()), required=False),
            SchemaItem(["Versions"], "versions", version_parse()),
            SchemaItem(
                ["Rates"], "rates", schema_dict_parse(
                    prefix_dict_parse("### "),
                    [
                        SchemaItem([""], "drops", variant_parse(rates_parse, safe_predicate), required=False),
                        SchemaItem(["Consumes"], "consumption", variant_parse(rates_parse, safe_predicate), required=False),
                        SchemaItem(["Notes"], "notes", flattened_list_parse(), required=False)
                    ],
                ), required=False),
            SchemaItem(["Lag Info"], "lag_info", parse_lag_info, required=False),
            SchemaItem(["Video Links", "Video Link"], "video_links", flattened_list_parse(), required=False),
            SchemaItem(["Files"], "files", schema_dict_parse(
                list_dict_parse(),
                [
                    SchemaItem(
                        ["Schematic", "Schematics"], "schematics", files_nested_list_parser()
                    ),
                    SchemaItem(
                        ["World Download", "World Downloads"], "world_downloads", files_nested_list_parser(), required=False
                    ),
                    SchemaItem(
                        ["Image", "Images"], "images", files_nested_list_parser()
                    ),
                ],
            )),
            SchemaItem(["Description"], "description", identity),
            SchemaItem(["Positives"], "positives", identity, required=False),
            SchemaItem(["Negatives"], "negatives", identity, required=False),
            SchemaItem(["Design Specifications"], "design_specifications", identity, required=False),
            SchemaItem(["Instructions"], "instructions", schema_dict_parse(
                prefix_dict_parse("### "),
                [
                    SchemaItem(["Notes"], "notes", identity, required=False),
                    SchemaItem(["Build"], "build", identity, required=False),
                    SchemaItem(["How to Use", "How to use"], "usage", identity, required=False),
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
    blacklisted_channels = [
        1364255649453707364,
        1364255868245508096,
        1364256102056857630,
        1385936884781416530,
        1364256219862138930,
        1162319892259811470,
        1173469097649000558,
        1173616633856659486,
    ]


    def decode_entry(
        entry: dict[str, str | int | section],
    ) -> dict:  # Not typed super well but whatever
        result = {k: entry.get(v, None) for k, v in metadata_map.items()}
        if int(result["channel_id"]) in blacklisted_channels:
            return result
        assert isinstance(entry["messages"], list)
        try:
            post_parse = message_parse("\n".join(entry["messages"]).split("\n"))
            result.update(post_parse[""])
            if len(post_parse) > 1:
                raise ValueError("Multiple variants in post.")
            ## variant
        except Exception as e:
            print(
                f"""{result["author"]}, https://discord.com/channels/1161803566265143306/{result["id"]}, \"{type(e).__name__}: {e}\""""
            )
            authors[f"<@{result['author']}>"] += 1
            failed[
                f"https://discord.com/channels/1161803566265143306/{result['channel_id']}"
            ] += 1
            # print(f"""https://discord.com/channels/1161803566265143306/{result["channel_id"]} https://discord.com/channels/1161803566265143306/{result["id"]}, {result["title"]}, {e}""")
            # print(traceback.format_exc())
            return result
        return result


    with open("data/archive_backup.json") as file:
        data = json.load(file)

    failed: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    for entry in data:
        result = decode_entry(entry)
        if result["channel_id"] in blacklisted_channels:
            continue
        if "designer(s)" in result:
            with open(f"data/out/{result['id']}.json", "w") as file:
                json.dump(result, file, indent=4)
    print(failed, failed.total(), len(data))
    print(authors.most_common())
