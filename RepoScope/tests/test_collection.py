import tempfile
import threading
import time
import unittest
from pathlib import Path

import config
from database import Database
from github_client import (ApiError, InvalidSourceError, NotFoundError, RateLimitError, SourceSpec,
                           build_bulk_plan, parse_source_url)
from scraper import Collector


def fake_item(repo_id):
    return {"id": repo_id, "name": f"r{repo_id}", "full_name": f"o/r{repo_id}", "owner": {"login": "o"},
            "stargazers_count": repo_id, "html_url": f"https://github.com/o/r{repo_id}"}


class FakeClient:
    """Pretends to be GitHub. Query 'q-N' owns `total` repositories; `overlap` of them are shared with q-(N-1)."""
    rate_remaining = None

    def __init__(self, total=250, overlap=0, fail_once_with=None, delay=0.0):
        self.total = total
        self.overlap = overlap
        self.fail_once_with = fail_once_with
        self.delay = delay
        self.calls = []

    def seconds_until_reset(self):
        return 0

    def search_repositories(self, query, page):
        time.sleep(self.delay)
        self.calls.append((query, page))
        if self.fail_once_with is not None:
            error, self.fail_once_with = self.fail_once_with, None
            raise error
        query_number = int(query.split("-")[1])
        base = query_number * (self.total - self.overlap) + 1
        start = (page - 1) * config.RESULTS_PER_PAGE
        ids = range(base + start, base + min(self.total, start + config.RESULTS_PER_PAGE))
        return {"total_count": self.total, "items": [fake_item(i) for i in ids]}

    def get_repository(self, full_name):
        if full_name == "missing/repo":
            raise NotFoundError("404")
        return fake_item(1)


def make_spec(query_count=4, key="bulk", kind="bulk"):
    return SourceSpec(kind, key, "test", queries=[f"q-{i}" for i in range(query_count)])


class UrlTests(unittest.TestCase):
    def test_supported_urls(self):
        self.assertEqual(parse_source_url("https://github.com/torvalds/linux").repo_path, "torvalds/linux")
        self.assertEqual(parse_source_url("github.com/python/cpython.git/").repo_path, "python/cpython")
        search = "https://github.com/search?q=language%3APython+stars%3A%3E1000&type=repositories"
        self.assertEqual(parse_source_url(search).queries, ["language:Python stars:>1000"])
        self.assertEqual(parse_source_url("https://github.com/topics/machine-learning").queries,
                         ["topic:machine-learning"])
        self.assertEqual(parse_source_url("https://github.com/microsoft").queries, ["user:microsoft"])
        self.assertEqual(parse_source_url("https://api.github.com/search/repositories?q=rust").queries, ["rust"])

    def test_invalid_urls(self):
        for bad in ["", "   ", "https://gitlab.com/a/b", "https://github.com", "https://github.com/search?type=repositories",
                    "https://github.com/search?q=x&type=users", "https://github.com/settings/profile",
                    "https://github.com/bad name/repo", "ftp://github.com/a/b", "https://api.github.com/user"]:
            with self.assertRaises(InvalidSourceError, msg=bad):
                parse_source_url(bad)

    def test_bulk_plan_can_reach_15000(self):
        plan = build_bulk_plan()
        self.assertGreaterEqual(len(plan.queries) * config.MAX_SEARCH_RESULTS, 15000 * 3)
        self.assertEqual(len(set(plan.queries)), len(plan.queries))


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "test.db"

    def tearDown(self):
        self.folder.cleanup()

    def count(self):
        database = Database(self.path)
        try:
            return database.count()
        finally:
            database.close()

    def test_bulk_collects_until_target_and_stops(self):
        self.assertEqual(Collector(FakeClient(), self.path).run(make_spec(), 600), "finished")
        self.assertGreaterEqual(self.count(), 600)
        self.assertLess(self.count(), 800)

    def test_overlapping_queries_do_not_create_duplicates(self):
        collector = Collector(FakeClient(total=200, overlap=100), self.path)
        collector.run(make_spec(query_count=3), 10_000)
        self.assertEqual(self.count(), 400)
        self.assertEqual(collector.new_records, 400)
        self.assertEqual(collector.duplicate_records, 200)

    def test_resume_continues_from_saved_page_instead_of_starting_over(self):
        first = Collector(FakeClient(), self.path)
        first.on_progress = lambda *args: first.stop()  # stop after the first saved page
        self.assertEqual(first.run(make_spec(), 10_000), "stopped")
        saved = Database(self.path)
        progress = saved.get_progress("bulk")
        saved.close()
        self.assertEqual((progress["query_index"], progress["next_page"]), (0, 2))
        self.assertEqual(self.count(), 100)

        second_client = FakeClient()
        Collector(second_client, self.path).run(make_spec(), 10_000)
        self.assertEqual(second_client.calls[0], ("q-0", 2))
        self.assertEqual(self.count(), 1000)

    def test_restart_flag_ignores_saved_progress_but_keeps_records(self):
        first = Collector(FakeClient(), self.path)
        first.on_progress = lambda *args: first.stop()
        first.run(make_spec(), 10_000)
        client = FakeClient()
        Collector(client, self.path).run(make_spec(), 10_000, restart=True)
        self.assertEqual(client.calls[0], ("q-0", 1))

    def test_pause_really_pauses_and_resume_continues(self):
        client = FakeClient(total=1000, delay=0.05)
        collector = Collector(client, self.path)
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(collector.run(make_spec(query_count=1), 1000)))
        collector.pause()
        worker.start()
        time.sleep(0.5)
        self.assertEqual(client.calls, [])
        self.assertTrue(collector.is_paused)
        collector.resume()
        worker.join(timeout=30)
        self.assertEqual(outcome, ["finished"])
        self.assertEqual(self.count(), 1000)

    def test_stop_while_paused_ends_cleanly_and_keeps_data(self):
        collector = Collector(FakeClient(delay=0.01), self.path)
        collector.on_progress = lambda *args: collector.pause()
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(collector.run(make_spec(), 10_000)))
        worker.start()
        time.sleep(0.5)
        collector.stop()
        worker.join(timeout=10)
        self.assertEqual(outcome, ["stopped"])
        self.assertEqual(self.count(), 100)

    def test_rate_limit_is_waited_out_and_retried(self):
        logs = []
        collector = Collector(FakeClient(fail_once_with=RateLimitError(0)), self.path,
                              on_log=lambda level, text: logs.append((level, text)))
        self.assertEqual(collector.run(make_spec(query_count=1), 100), "finished")
        self.assertEqual(self.count(), 100)
        self.assertTrue(any(level == "WARNING" and "Rate limit" in text for level, text in logs))

    def test_error_ends_the_run_but_keeps_saved_records(self):
        client = FakeClient()
        original = client.search_repositories

        def fails_on_page_three(query, page):
            if page == 3:
                raise ApiError("boom", status=500)
            return original(query, page)

        client.search_repositories = fails_on_page_three
        levels = []
        collector = Collector(client, self.path, on_log=lambda level, text: levels.append(level))
        self.assertEqual(collector.run(make_spec(), 10_000), "error")
        self.assertEqual(self.count(), 200)
        self.assertIn("ERROR", levels)

    def test_query_rejected_with_422_is_skipped(self):
        client = FakeClient()
        original = client.search_repositories

        def reject_first(query, page):
            if query == "q-0":
                raise ApiError("validation failed", status=422)
            return original(query, page)

        client.search_repositories = reject_first
        Collector(client, self.path).run(make_spec(query_count=2), 10_000)
        self.assertEqual(self.count(), 250)

    def test_single_repository_and_not_found(self):
        single = SourceSpec("repo", "repo:o/r1", "x", repo_path="o/r1")
        self.assertEqual(Collector(FakeClient(), self.path).run(single, 1), "finished")
        self.assertEqual(self.count(), 1)
        missing = SourceSpec("repo", "repo:missing/repo", "x", repo_path="missing/repo")
        self.assertEqual(Collector(FakeClient(), self.path).run(missing, 1), "error")

    def test_progress_reports_known_total_for_search_sources(self):
        reports = []
        collector = Collector(FakeClient(total=250), self.path, on_progress=lambda *a: reports.append(a))
        collector.run(make_spec(query_count=1, key="search:x", kind="search"), 1000)
        self.assertEqual(reports[-1][:2], (250, 250))
        self.assertEqual(self.count(), 250)


if __name__ == "__main__":
    unittest.main()
