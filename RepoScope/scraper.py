import threading
import time

import config
from database import Database
from github_client import ApiError, GitHubError, RateLimitError
from models import normalize_repository


def _ignore(*arguments):
    pass


class Collector:
    """Collects repositories from the GitHub API into the database.

    It has no GUI code, so a background thread can run it and tests can run it directly.
    It opens its own database connection because SQLite connections belong to one thread.
    """

    def __init__(self, client, database_path, on_status=_ignore, on_progress=_ignore, on_log=_ignore):
        self.client = client
        self.database_path = database_path
        self.on_status = on_status
        self.on_progress = on_progress  # (done, total, new_records, duplicate_records)
        self.on_log = on_log  # (level, text)
        self.new_records = 0
        self.duplicate_records = 0
        self._can_run = threading.Event()
        self._can_run.set()
        self._stop_requested = threading.Event()
        self.database = None

    def pause(self):
        self._can_run.clear()

    def resume(self):
        self._can_run.set()

    def stop(self):
        self._stop_requested.set()
        self._can_run.set()  # wake a paused worker so it can see the stop request

    @property
    def is_paused(self):
        return not self._can_run.is_set()

    def _checkpoint(self):
        """Block while paused. Returns False when the user asked to stop."""
        while not self._can_run.wait(0.2):
            pass
        return not self._stop_requested.is_set()

    def _wait(self, seconds, reason):
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            if not self._checkpoint():
                return False
            self.on_status(f"{reason}. Continuing in {int(remaining) + 1} s")
            self._stop_requested.wait(min(1.0, remaining))

    def _call_api(self, function, *arguments):
        """Run one API call, waiting out rate limits. Returns None if stopped."""
        while True:
            if self.client.rate_remaining == 0 and self.client.seconds_until_reset() > 0:
                if not self._wait(self.client.seconds_until_reset() + 1, "GitHub rate limit used up, waiting for it to reset (normal, nothing is wrong)"):
                    return None
            if not self._checkpoint():
                return None
            try:
                return function(*arguments)
            except RateLimitError as error:
                self.on_log("WARNING", f"Rate limit reached. This is normal: GitHub allows only a few searches per minute. "
                                       f"Waiting {error.wait_seconds} seconds, then continuing automatically.")
                if not self._wait(error.wait_seconds, "Waiting for the GitHub rate limit"):
                    return None

    def run(self, source, target, restart=False):
        """Returns 'finished', 'stopped' or 'error'. Saved records are never deleted."""
        self.database = Database(self.database_path)
        try:
            if restart:
                self.database.reset_progress(source.key)
            if source.kind == "repo":
                return self._collect_one_repository(source)
            return self._collect_search_queries(source, target)
        except GitHubError as error:
            self.on_log("ERROR", str(error))
            self.on_status("Stopped by an error. Saved records are kept; press Start to continue.")
            return "error"
        finally:
            self.database.close()

    def _collect_one_repository(self, source):
        self.on_status(f"Fetching {source.repo_path}")
        data = self._call_api(self.client.get_repository, source.repo_path)
        if data is None:
            return "stopped"
        record = normalize_repository(data)
        if record is None:
            raise ApiError("GitHub returned a repository without an ID or name.")
        new, duplicate = self.database.save_repositories([record])
        self.new_records += new
        self.duplicate_records += duplicate
        self.database.save_progress(source.key, 0, 1, True, 1)
        self.on_progress(1, 1, self.new_records, self.duplicate_records)
        self.on_status("Finished. 1 repository saved.")
        return "finished"

    def _collect_search_queries(self, source, target):
        is_bulk = source.kind == "bulk"
        saved = self.database.get_progress(source.key)
        query_index, page = 0, 1
        if saved and not saved["finished"] and saved["query_index"] < len(source.queries):
            query_index, page = saved["query_index"], saved["next_page"]
            self.on_log("INFO", f"Resuming from saved progress: query {query_index + 1}, page {page}.")
        elif is_bulk and self.database.count() >= target:
            self.on_log("INFO", f"The database already has {self.database.count()} repositories (target {target}).")
            self.on_status("Finished. The target was already reached.")
            self.on_progress(target, target, 0, 0)
            return "finished"

        fetched = (page - 1) * config.RESULTS_PER_PAGE
        total_known = target if is_bulk else 0

        while query_index < len(source.queries):
            query = source.queries[query_index]
            while page <= config.MAX_SEARCH_PAGES:
                done = self.database.count() if is_bulk else fetched
                if done >= target:
                    return self._finish(source, query_index, total_known)
                self.on_status(f"Collecting: search {query_index + 1} of {len(source.queries)}  [{query}], page {page}")
                try:
                    data = self._call_api(self.client.search_repositories, query, page)
                except ApiError as error:
                    if error.status != 422:
                        raise
                    self.on_log("WARNING", f"GitHub could not run '{query}': {error}. Skipping it.")
                    break
                if data is None:
                    return "stopped"

                items = data["items"]
                records = [record for record in map(normalize_repository, items) if record]
                if len(records) < len(items):
                    self.on_log("WARNING", f"Skipped {len(items) - len(records)} unusable items on page {page}.")
                new, duplicate = self.database.save_repositories(records)
                self.new_records += new
                self.duplicate_records += duplicate
                fetched += len(items)

                available = min(int(data.get("total_count") or 0), config.MAX_SEARCH_RESULTS)
                if not is_bulk:
                    total_known = min(available, target)
                done = self.database.count() if is_bulk else min(fetched, total_known)
                self.database.save_progress(source.key, query_index, page + 1, False, total_known)
                self.on_progress(done, total_known, self.new_records, self.duplicate_records)
                if len(items) < config.RESULTS_PER_PAGE or page * config.RESULTS_PER_PAGE >= available:
                    break
                page += 1
            query_index += 1
            page = 1
            self.database.save_progress(source.key, query_index, 1, False, total_known)
        return self._finish(source, query_index, total_known)

    def _finish(self, source, query_index, total_known):
        self.database.save_progress(source.key, query_index, 1, True, total_known)
        count = self.database.count()
        self.on_status(f"Finished. {count:,} unique repositories in the database.")
        return "finished"
