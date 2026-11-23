"""Read and merge measurements transcribed from archive figures."""

import json
import re
from collections.abc import Callable
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from links import embedded_discord_links
from parser import AbbreviatedRate, VERSIONS, normalize_cdn_url, normalize_inline_urls

MANUAL_MEASUREMENTS_PATH = Path(__file__).with_name("manual_measurements.json")
RATE_FIELDS = {"variants", "version", "items", "conditions", "amount", "interval", "note"}
LAG_FIELDS = {"conditions", "lag"}
LAG_ENVIRONMENT_DEFAULTS = {"cpu": "", "has_lithium": False, "version": ""}


class ManualMeasurementsError(ValueError):
    """An archive measurement could not be loaded or merged."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManualMeasurementsError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def _figure_url(url: str) -> str:
    if not isinstance(url, str) or any(character.isspace() for character in url):
        raise ManualMeasurementsError("Expected an HTTP(S) figure URL")
    parts = urlsplit(normalize_cdn_url(url))
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ManualMeasurementsError("Expected an HTTP(S) figure URL")
    if parts.netloc == "cdn.tmcc.dev":
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return urlunsplit(parts._replace(fragment=""))


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _is_measurement(value: object) -> bool:
    return type(value) in (int, float) and 0 <= value < float("inf")


def _valid_version(value: object) -> bool:
    return isinstance(value, str) and (value == "" or re.fullmatch(VERSIONS, value) is not None)


def _valid_rate(row: object) -> bool:
    if not isinstance(row, dict) or row.keys() != RATE_FIELDS:
        return False
    items = row["items"]
    return (
        _is_string_list(row["variants"])
        and _valid_version(row["version"])
        and all(isinstance(row[key], str) for key in ("conditions", "note", "interval"))
        and re.fullmatch(r"[\w.+-]+(?:/[\w.+-]+)*", row["interval"]) is not None
        and _is_measurement(row["amount"])
        and isinstance(items, dict)
        and items.keys() == {"type", "names"}
        and items["type"] in ("concurrent", "exclusive")
        and _is_string_list(items["names"])
        and bool(items["names"])
    )


def _valid_lag(row: object) -> bool:
    return (
        isinstance(row, dict)
        and row.keys() == LAG_FIELDS
        and _is_string_list(row["conditions"])
        and _is_measurement(row["lag"])
    )


def _valid_note(node: object) -> bool:
    return (
        isinstance(node, dict)
        and node.keys() == {"list_type", "text", "children"}
        and node["list_type"] in ("dashed", "numbered")
        and isinstance(node["text"], str)
        and bool(node["text"].strip())
        and isinstance(node["children"], list)
        and all(_valid_note(child) for child in node["children"])
    )


def _validate_entry(entry: object) -> None:
    if not isinstance(entry, dict) or entry.keys() - {"figures", "rates", "lag_info"}:
        raise ManualMeasurementsError("Expected an object with figures, rates, and/or lag_info")

    figures = entry.get("figures")
    if not isinstance(figures, list) or not figures:
        raise ManualMeasurementsError("Expected a nonempty figures list")
    figure_numbers = set()
    for figure in figures:
        if not isinstance(figure, dict) or figure.keys() != {"figure_number", "url"}:
            raise ManualMeasurementsError("Expected figure_number and url for each source figure")
        number = figure["figure_number"]
        if type(number) is not int or number < 1 or number in figure_numbers:
            raise ManualMeasurementsError(f"Expected a unique positive figure number, got {number!r}")
        _figure_url(figure["url"])
        figure_numbers.add(number)

    row_count = 0
    for section_name, row_keys, validator in (
        ("rates", ("drops", "consumption"), _valid_rate),
        ("lag_info", ("idle", "active"), _valid_lag),
    ):
        if section_name not in entry:
            continue
        section = entry[section_name]
        allowed_keys = {*row_keys, "notes"}
        if section_name == "lag_info":
            allowed_keys.add("environment")
        if not isinstance(section, dict) or section.keys() - allowed_keys:
            raise ManualMeasurementsError(f"Unexpected fields in {section_name}")
        for row_key in row_keys:
            rows = section.get(row_key, [])
            if not isinstance(rows, list):
                raise ManualMeasurementsError(f"Expected a list in {section_name}.{row_key}")
            for index, row in enumerate(rows, 1):
                if not validator(row):
                    raise ManualMeasurementsError(f"Invalid parser row {index} in {section_name}.{row_key}")
            row_count += len(rows)
        notes = section.get("notes", [])
        if not isinstance(notes, list) or not all(_valid_note(note) for note in notes):
            raise ManualMeasurementsError(f"Invalid parser notes in {section_name}.notes")
        if "environment" in section:
            environment = section["environment"]
            if not isinstance(environment, dict) or any(
                key not in LAG_ENVIRONMENT_DEFAULTS or type(value) is not type(LAG_ENVIRONMENT_DEFAULTS[key])
                for key, value in environment.items()
            ):
                raise ManualMeasurementsError("Invalid lag_info.environment")
            if not _valid_version(environment.get("version", "")):
                raise ManualMeasurementsError("Invalid lag_info.environment.version")
    if not row_count:
        raise ManualMeasurementsError("Expected at least one rate or lag reading")


def load_manual_measurements(
    path: Path = MANUAL_MEASUREMENTS_PATH,
    *,
    missing_ok: bool = False,
) -> dict[str, dict]:
    """Load one validated snapshot for a parse command."""
    try:
        with path.open(encoding="utf-8") as file:
            entries = json.load(file, object_pairs_hook=_unique_object)
        if not isinstance(entries, dict):
            raise ManualMeasurementsError("Expected an object keyed by Discord thread ID")
        for thread_id, entry in entries.items():
            if not re.fullmatch(r"[1-9][0-9]*", thread_id):
                raise ManualMeasurementsError(f"Invalid Discord thread ID {thread_id!r}")
            try:
                _validate_entry(entry)
            except ValueError as error:
                raise ManualMeasurementsError(f"Thread {thread_id}: {error}") from error
    except FileNotFoundError as error:
        if missing_ok:
            return {}
        raise ManualMeasurementsError(f"{path.name} is missing") from error
    except (OSError, ValueError) as error:
        raise ManualMeasurementsError(f"{path.name}: {error}") from error
    return entries


def _rate_key(row: dict) -> tuple:
    items = row["items"]
    return (
        tuple(row["variants"]), row["version"], items["type"],
        tuple(items["names"]), row["conditions"], row["interval"],
    )


def _lag_key(row: dict) -> tuple:
    return tuple(row["conditions"])


def _matches_rounded_rate(archived: AbbreviatedRate, manual: int | float) -> bool:
    exact = Decimal(str(manual))
    scale = archived.scale
    if exact < scale or (scale == 1_000 and exact >= 1_000_000):
        return False
    with localcontext() as context:
        context.prec = max(context.prec, exact.adjusted() + 3)
        displayed = (exact / scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return displayed == archived.written


def _merge_rows(
    existing: list[dict],
    incoming: list[dict],
    key: Callable[[dict], tuple],
    value_field: str,
    field: str,
) -> list[dict]:
    rows = existing.copy()
    indices = {}
    for index, row in enumerate(rows):
        indices.setdefault(key(row), []).append(index)
    for row in incoming:
        identity = key(row)
        if identity in indices:
            manual_value = row[value_field]
            for index in indices[identity]:
                current = rows[index]
                archived_value = current[value_field]
                abbreviated = value_field == "amount" and isinstance(archived_value, AbbreviatedRate)
                if archived_value != manual_value and not (
                    abbreviated and _matches_rounded_rate(archived_value, manual_value)
                ):
                    raise ManualMeasurementsError(
                        f"Conflicting measurement in {field} for {identity!r} "
                        f"({archived_value} vs {manual_value})"
                    )
                if abbreviated:
                    rows[index] = {**current, value_field: manual_value}
            if note := row.get("note"):
                index = indices[identity][0]
                current = rows[index]
                notes = dict.fromkeys((current["note"] + " · " + note).split(" · "))
                notes.pop("", None)
                rows[index] = {**current, "note": " · ".join(notes)}
            continue
        indices[identity] = [len(rows)]
        rows.append(row)
    return rows


def _merge_environment(existing: dict, incoming: dict) -> dict:
    environment = existing.copy()
    for key, value in incoming.items():
        current = existing[key]
        known = bool(existing["cpu"]) if key == "has_lithium" else bool(current)
        if known and current != value:
            raise ManualMeasurementsError(f"Conflicting lag_info.environment.{key}")
        environment[key] = value
    return environment


def _normalize_note(note: dict) -> dict:
    text = normalize_inline_urls(note["text"])
    return {
        "list_type": note["list_type"],
        "text": text,
        "children": [_normalize_note(child) for child in note["children"]],
        "discord_links": embedded_discord_links([text]),
    }


def _note_key(note: dict) -> tuple:
    return note["list_type"], note["text"], tuple(_note_key(child) for child in note["children"])


def _merge_notes(existing: list[dict], incoming: list[dict]) -> list[dict]:
    notes = existing.copy()
    seen = {_note_key(note) for note in existing}
    for raw_note in incoming:
        note = _normalize_note(raw_note)
        key = _note_key(note)
        if key in seen:
            continue
        seen.add(key)
        notes.append(note)
    return notes


def merge_manual_measurements(thread_id: str, post_data: dict, entries: dict[str, dict]) -> None:
    """Apply a thread's measurements after verifying their source figures."""
    if (entry := entries.get(thread_id)) is None:
        return

    figures = {figure["figure_number"]: figure["url"] for figure in post_data["figures"]}
    patched = {}
    try:
        for source in entry["figures"]:
            number = source["figure_number"]
            if number not in figures or _figure_url(figures[number]) != _figure_url(source["url"]):
                raise ManualMeasurementsError(f"Source Figure {number} is missing or has changed")

        if "rates" in entry:
            rates = post_data["rates"].copy()
            measurement = entry["rates"]
            for key in ("drops", "consumption"):
                rates[key] = _merge_rows(
                    rates[key], measurement.get(key, []), _rate_key, "amount", f"rates.{key}"
                )
            rates["notes"] = _merge_notes(rates["notes"], measurement.get("notes", []))
            patched["rates"] = rates

        if "lag_info" in entry:
            lag = (post_data["lag_info"] or {
                "environment": LAG_ENVIRONMENT_DEFAULTS,
                "idle": [],
                "active": [],
                "notes": [],
            }).copy()
            measurement = entry["lag_info"]
            for key in ("idle", "active"):
                lag[key] = _merge_rows(
                    lag[key], measurement.get(key, []), _lag_key, "lag", f"lag_info.{key}"
                )
            lag["environment"] = _merge_environment(lag["environment"], measurement.get("environment", {}))
            lag["notes"] = _merge_notes(lag["notes"], measurement.get("notes", []))
            patched["lag_info"] = lag
    except ValueError as error:
        raise ManualMeasurementsError(f"Thread {thread_id}: {error}") from error

    post_data.update(patched)
