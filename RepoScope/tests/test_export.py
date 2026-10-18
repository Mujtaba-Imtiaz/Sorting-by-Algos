import csv
import json
import tempfile
import unittest
from pathlib import Path

from exporter import export_csv, export_json
from models import COLUMN_KEYS

RECORDS = [
    {"id": 1, "name": "a", "full_name": "x/a", "description": "Héllo, \"world\"\nline two", "stars": 5, "language": None},
    {"id": 2, "name": "b", "full_name": "x/b", "description": None, "stars": None, "language": "Go"},
]


class ExportTests(unittest.TestCase):
    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.csv"
            export_csv(path, RECORDS)
            with open(path, newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
        self.assertEqual(list(rows[0].keys()), COLUMN_KEYS)
        self.assertEqual(rows[0]["description"], "Héllo, \"world\"\nline two")
        self.assertEqual(rows[1]["stars"], "")
        self.assertEqual(len(rows), 2)

    def test_json_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.json"
            export_json(path, RECORDS)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["stars"], 5)
        self.assertIsNone(data[1]["description"])
        self.assertEqual(list(data[0].keys()), COLUMN_KEYS)

    def test_export_has_no_secret_fields(self):
        self.assertFalse([key for key in COLUMN_KEYS if "token" in key or "secret" in key])


if __name__ == "__main__":
    unittest.main()
