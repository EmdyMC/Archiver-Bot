import json
import re

# import traceback
from collections import Counter, defaultdict
from functools import wraps
from typing import Callable
from dataclasses import dataclass

from .MessageDict import Message

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
                current_key = line[len(prefix) :]
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


def optionally_single_entry_flattened_list_parse() -> parser[section]:
    def parse(data: section) -> section:
        if data[0].startswith("- "):
            return flattened_list_parse()(data)
        return data

    return parse


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
        parsed_data_iter = iter(parsed_data.items())
        k, v = next(parsed_data_iter)
        for field in config:
            if k in field.display_names:
                result[field.name] = field.parser(v)
                k, v = next(parsed_data_iter, (None, None)) # After iteration is done, just don't match anything and exhaust defaults, or error.
            elif not field.required:
                result[field.name] = field.default
            else:
                raise ValueError(f"Required field {field.name} not found, {f"found {k}" if k is not None else "reached end of post"}.\nConfig: {[f"{"?" if not field.required else ""}{field.name}" for field in config]}.")
        if k is not None:
            raise ValueError(f"Extra field {k} at the end, after {field.name}.\nConfig: {[f"{"?" if not field.required else ""}{field.name}" for field in config]}.")
        return result

    return parse


def variant_parse[T](
    parser_: Callable[[str], parser[list[T]]], predicate: Callable[[section], bool]
) -> parser[list[T]]:
    def parse(data: section) -> list[T]:
        # Test
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
            "thread": "",
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
                    case "see thread":
                        section = "thread"
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
            result["name"] = int(user_id_match.group(1))
            if data[user_id_match.end() :].startswith(": "):
                result["contribution"] = data[user_id_match.end() + 2 :]
        url_match = re.match(r"^\[(.*?)\]\((.*?)\)", data)
        if url_match:
            result["name"] = url_match.group(1)
            result["channel_link"] = url_match.group(2)
            if data[url_match.end() :].startswith(": "):
                result["contribution"] = data[url_match.end() + 2 :]
        return result

    return parse


def environment_parse() -> parser[dict[str, str | bool]]:
    @single_line_parser
    def parse(data: str) -> dict[str, str | bool]:
        environment_match = re.match(r"^- CPU (.*?)( with Lithium)?(in (.*))?$", data)
        if environment_match is None:
            # print(data)
            raise ValueError("Incorrectly formatted lag info environment field")
        return {
            "CPU": environment_match.group(1),
            "Lithium": environment_match.group(2) is not None,
            "version": environment_match.group(4) or "",
        }

    return parse


def rates_value_parse() -> parser[tuple[float, str, str]]:
    # Tuple return is a little weird but simple enough
    @single_line_parser
    def parse(x: str) -> tuple[float, str, str]:
        if not x.startswith("- "):
            raise ValueError(f"Rates section format error, expected '- ', got {x!r}.")
        x = x[2:]
        rates_match = re.match(r"^([\d\.]+)([kKmM]?)\/(.*)( \((.*)\))?$", x)
        if rates_match is None:
            raise ValueError(f"Rates value regex doesn't match, got {x!r}.")
        rate = float(rates_match.group(1))
        unit = {
            "": 1,
            "k": 1e3,
            "m": 1e6,
        }[rates_match.group(2).lower()]
        interval = rates_match.group(3)
        note = rates_match.group(5)

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


def lag_parse(variant: str) -> parser[list[dict]]:
    return single_line_parser(lambda data: [{"variant": variant, "lag": data}])



message_parse_schema = dict_postprocess_parse(
    prefix_dict_parse("# "),
    schema_dict_parse(
        prefix_dict_parse("## "),
        [
            SchemaItem(["Designer", "Designers", "Designer(s)"], "designers", list_postprocess_parse(list_parse(), contributor_parse())),
            SchemaItem(["Credits"], "credits", list_postprocess_parse(list_parse(), contributor_parse()), required=False),
            SchemaItem(["Versions"], "versions", version_parse()),
            SchemaItem(["Rates"], "rates", schema_dict_parse(
                prefix_dict_parse("### "),
                [
                    SchemaItem([""], "drops", variant_parse(rates_parse, lambda data: ": " in next(iter(list_dict_parse()(data).values()))[0])),
                    SchemaItem(["Consumes"], "consumption", variant_parse(rates_parse, lambda data: ": " in next(iter(list_dict_parse()(data).values()))[0]), required=False),
                ],
            ), required=False),
            SchemaItem(["Lag Info"], "lag_info", schema_dict_parse(
                list_dict_parse(),
                [
                    SchemaItem(["Test environment"], "environment", environment_parse()),
                    SchemaItem(["Idle"], "idle", variant_parse(lag_parse, lambda data: ": " in data[0])),
                    SchemaItem(["Active"], "active", variant_parse(lag_parse, lambda data: ": " in data[0])),
                ],
            ), required=False),
            SchemaItem(["Video Links"], "video_links", flattened_list_parse(), required=False),
            SchemaItem(["Files"], "files", schema_dict_parse(
                list_dict_parse(),
                [
                    SchemaItem(["Schematic", "Schematics"], "schematics", optionally_single_entry_flattened_list_parse()),
                    SchemaItem(["World Download", "World Downloads"], "world_downloads", optionally_single_entry_flattened_list_parse(), required=False),
                    SchemaItem(["Image", "Images"], "images", optionally_single_entry_flattened_list_parse()),
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
            SchemaItem(["Figures"], "figures", list_dict_parse(), required=False),
        ],
    ),
)


def message_parse(data: section) -> list[Message]:
    return [{"variant_name": name, **rest} for name, rest in message_parse_schema(data).items()]


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
