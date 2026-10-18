import tempfile
import unittest
from pathlib import Path

from database import Database
from models import COLUMN_KEYS, comparable_value, normalize_repository

API_ITEM = {
    "id": 42, "name": "demo", "full_name": "someone/demo", "owner": {"login": "someone"},
    "description": "  A   demo\nrepo ", "language": "Python", "stargazers_count": 12, "forks_count": 3,
    "open_issues_count": 1, "created_at": "2020-01-02T03:04:05Z", "updated_at": "2021-01-02T03:04:05Z",
    "license": {"name": "MIT License"}, "default_branch": "main", "html_url": "https://github.com/someone/demo",
    "archived": False, "private": False, "visibility": "public",
}


class NormalizeTests(unittest.TestCase):
    def test_full_item(self):
        record = normalize_repository(API_ITEM)
        self.assertEqual(set(record), set(COLUMN_KEYS))
        self.assertEqual(record["description"], "A demo repo")
        self.assertEqual((record["stars"], record["archived"], record["license_name"]), (12, 0, "MIT License"))

    def test_missing_fields_become_none(self):
        record = normalize_repository({"id": 1, "full_name": "a/b", "description": None, "language": None,
                                       "license": None, "stargazers_count": None})
        for key in ("description", "language", "license_name", "stars"):
            self.assertIsNone(record[key])
        self.assertEqual((record["name"], record["owner"]), ("b", "a"))

    def test_unusable_items_are_rejected(self):
        for bad in [None, "text", {}, {"id": "x", "full_name": "a/b"}, {"id": 1}, {"id": 1, "full_name": " "}]:
            self.assertIsNone(normalize_repository(bad))

    def test_comparable_values(self):
        record = normalize_repository(API_ITEM)
        self.assertEqual(comparable_value(record, "language"), "python")
        self.assertEqual(comparable_value(record, "stars"), 12)
        self.assertIsInstance(comparable_value(record, "created_at"), int)
        self.assertIsNone(comparable_value({"description": "   "}, "description"))


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "test.db"

    def tearDown(self):
        self.folder.cleanup()

    def make(self, repo_id, stars=1):
        record = normalize_repository(API_ITEM)
        record.update(id=repo_id, stars=stars, full_name=f"someone/demo{repo_id}")
        return record

    def test_duplicates_are_not_counted_twice(self):
        database = Database(self.path)
        self.assertEqual(database.save_repositories([self.make(1), self.make(2), self.make(1)]), (2, 1))
        self.assertEqual(database.save_repositories([self.make(2), self.make(3)]), (1, 1))
        self.assertEqual(database.count(), 3)
        database.close()

    def test_duplicate_updates_changed_values(self):
        database = Database(self.path)
        database.save_repositories([self.make(1, stars=5)])
        database.save_repositories([self.make(1, stars=99)])
        self.assertEqual(database.load_all()[0]["stars"], 99)
        database.close()

    def test_records_and_progress_survive_a_restart(self):
        database = Database(self.path)
        database.save_repositories([self.make(1), self.make(2)])
        database.save_progress("bulk", 7, 3, False, 15000)
        database.close()

        reopened = Database(self.path)
        self.assertEqual(reopened.count(), 2)
        progress = reopened.get_progress("bulk")
        self.assertEqual((progress["query_index"], progress["next_page"], progress["finished"]), (7, 3, 0))
        reopened.reset_progress("bulk")
        self.assertIsNone(reopened.get_progress("bulk"))
        self.assertEqual(reopened.count(), 2)
        reopened.close()

    def test_statistics_and_empty_database(self):
        database = Database(self.path)
        self.assertEqual(database.get_statistics()["total"], 0)
        self.assertEqual(database.load_all(), [])
        first, second = self.make(1, 10), self.make(2, 20)
        second["archived"] = 1
        second["language"] = None
        database.save_repositories([first, second])
        stats = database.get_statistics()
        self.assertEqual((stats["total"], stats["languages"], stats["stars"], stats["archived"]), (2, 1, 30, 1))
        database.close()

    def test_no_token_or_secret_columns_exist(self):
        database = Database(self.path)
        columns = [row["name"] for row in database.connection.execute("PRAGMA table_info(repositories)")]
        self.assertFalse([c for c in columns if "token" in c.lower()])
        database.close()


if __name__ == "__main__":
    unittest.main()
