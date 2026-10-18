import csv
import json

from models import COLUMN_KEYS


def export_csv(path, records):
    # utf-8-sig lets Excel on Windows show non-English descriptions correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMN_KEYS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def export_json(path, records):
    rows = [{key: record.get(key) for key in COLUMN_KEYS} for record in records]
    with open(path, "w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
