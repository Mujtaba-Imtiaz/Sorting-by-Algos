import threading

from PyQt6.QtCore import QThread, pyqtSignal

from benchmark import run_benchmark
from github_client import GitHubClient
from scraper import Collector
from sorting_algorithms import SortCancelled


class ScraperThread(QThread):
    """Runs the Collector away from the GUI thread and forwards its messages as Qt signals."""

    status = pyqtSignal(str)
    progress = pyqtSignal(int, int, int, int)
    log = pyqtSignal(str, str)
    done = pyqtSignal(str)

    def __init__(self, source, token, target, restart, database_path, parent=None):
        super().__init__(parent)
        self.source = source
        self.target = target
        self.restart = restart
        self.client = GitHubClient(token)
        self.collector = Collector(
            self.client, database_path,
            on_status=self.status.emit, on_progress=self.progress.emit,
            on_log=lambda level, text: self.log.emit(level, text),
        )

    def run(self):
        try:
            outcome = self.collector.run(self.source, self.target, self.restart)
        except Exception as error:  # last safety net so the GUI always hears that the worker ended
            self.log.emit("ERROR", f"Unexpected problem: {error}")
            outcome = "error"
        self.done.emit(outcome)

    def pause(self):
        self.collector.pause()

    def resume(self):
        self.collector.resume()

    def stop(self):
        self.collector.stop()


class SortThread(QThread):
    step = pyqtSignal(str)
    report_ready = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, records, levels, algorithms, keep_records, parent=None):
        super().__init__(parent)
        self.records = records
        self.levels = levels
        self.algorithms = algorithms
        self.keep_records = keep_records
        self.stop_event = threading.Event()

    def run(self):
        try:
            report = run_benchmark(self.records, self.levels, self.algorithms, self.stop_event,
                                   self.step.emit, self.keep_records)
        except SortCancelled:
            self.cancelled.emit()
            return
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.report_ready.emit(report)

    def cancel(self):
        self.stop_event.set()
