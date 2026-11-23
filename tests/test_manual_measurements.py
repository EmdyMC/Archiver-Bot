from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from manual_measurements import (
    ManualMeasurementsError,
    load_manual_measurements,
    merge_manual_measurements,
)
from parser import parse_lag_section, rates_section_parser


THREAD_ID = "123456789"
FIGURE = {
    "figure_number": 1,
    "url": "https://cdn.discordapp.com/attachments/1/2/rates.png?ex=old",
}


class ManualMeasurementsTests(unittest.TestCase):
    def setUp(self):
        self.post = {
            "figures": [{**FIGURE, "url": "https://cdn.tmcc.dev/attachments/1/2/rates.png?ex=new"}],
            "rates": rates_section_parser()([
                "- Iron Ingot: 1.2k/h", "### Notes", "- See Figure 1.",
            ]),
            "lag_info": parse_lag_section(["- Test environment: CPU Example with Lithium", "- Idle: 0.2mspt"]),
        }
        self.entry = {"figures": [FIGURE], "rates": {"drops": self.post["rates"]["drops"].copy()}}

    def load(self, value):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manual_measurements.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_manual_measurements(path)

    def test_merges_into_parser_output_without_duplicates(self):
        additions = rates_section_parser()([
            "### Consumes", "- Bone Meal: 100/h", "### Notes", "- Measured by the figure author.",
        ])
        self.entry["rates"].update(consumption=additions["consumption"], notes=additions["notes"])
        self.entry["lag_info"] = {"active": [{"conditions": ["Fast"], "lag": 0.5}]}
        entries = self.load({THREAD_ID: self.entry})

        for _ in range(2):
            merge_manual_measurements(THREAD_ID, self.post, entries)

        self.assertEqual(len(self.post["rates"]["drops"]), 1)
        self.assertEqual(self.post["rates"]["consumption"], additions["consumption"])
        self.assertEqual(
            [note["text"] for note in self.post["rates"]["notes"]],
            ["See Figure 1.", "Measured by the figure author."],
        )
        self.assertEqual(self.post["lag_info"]["active"], self.entry["lag_info"]["active"])
        self.assertEqual(self.post["lag_info"]["idle"], [{"conditions": [], "lag": 0.2}])
        self.assertTrue(self.post["lag_info"]["environment"]["has_lithium"])

    def test_supports_creating_lag_section(self):
        self.post["lag_info"] = None
        self.entry["lag_info"] = {"active": [{"conditions": [], "lag": 0.0}]}

        merge_manual_measurements(THREAD_ID, self.post, self.load({THREAD_ID: self.entry}))

        self.assertEqual(self.post["lag_info"], {
            "environment": {"cpu": "", "has_lithium": False, "version": ""},
            "idle": [],
            "active": [{"conditions": [], "lag": 0.0}],
            "notes": [],
        })

    def test_combines_notes_for_the_same_rate_without_adding_a_second_row(self):
        original = self.post["rates"]["drops"][0]
        self.entry["rates"]["drops"] = [{**original, "note": "From Figure 1"}]
        original["note"] = "From the post"
        entries = self.load({THREAD_ID: self.entry})

        for _ in range(2):
            merge_manual_measurements(THREAD_ID, self.post, entries)

        self.assertEqual(self.post["rates"]["drops"], [{**original, "note": "From the post · From Figure 1"}])

    def test_rejects_a_conflict_before_changing_either_section(self):
        self.entry["rates"]["consumption"] = rates_section_parser()([
            "### Consumes", "- Bone Meal: 100/h",
        ])["consumption"]
        self.entry["lag_info"] = {"idle": [{"conditions": [], "lag": 0.3}]}
        unchanged = deepcopy(self.post)

        with self.assertRaisesRegex(ManualMeasurementsError, r"123456789.*lag_info.idle"):
            merge_manual_measurements(THREAD_ID, self.post, self.load({THREAD_ID: self.entry}))

        self.assertEqual(self.post, unchanged)

    def test_rejects_stale_figure(self):
        self.post["figures"][0]["url"] = self.post["figures"][0]["url"].replace("/1/2/", "/1/3/")
        with self.assertRaisesRegex(ManualMeasurementsError, "Source Figure 1"):
            merge_manual_measurements(THREAD_ID, self.post, self.load({THREAD_ID: self.entry}))

    def test_validates_parser_native_rows_and_notes(self):
        self.entry["rates"]["notes"] = [{"text": "A note missing its list metadata"}]
        with self.assertRaisesRegex(ManualMeasurementsError, r"123456789.*rates.notes"):
            self.load({THREAD_ID: self.entry})

        del self.entry["rates"]["notes"]
        self.entry["rates"]["drops"] = [{"items": "Iron Ingot", "amount": 10}]
        with self.assertRaisesRegex(ManualMeasurementsError, r"123456789.*rates.drops"):
            self.load({THREAD_ID: self.entry})

    def test_no_entry_leaves_post_unchanged(self):
        unchanged = deepcopy(self.post)
        merge_manual_measurements(THREAD_ID, self.post, self.load({}))
        self.assertEqual(self.post, unchanged)

    def test_missing_file_can_be_allowed_for_targeted_parses_only(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manual_measurements.json"
            self.assertEqual(load_manual_measurements(path, missing_ok=True), {})
            with self.assertRaisesRegex(ManualMeasurementsError, "manual_measurements.json is missing"):
                load_manual_measurements(path)
