from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QStandardItemModel
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

from benchmark import prepare_input
from config import SORT_WARNING_SIZE
from models import COLUMN_BY_KEY
from sorting_algorithms import ALGORITHMS, BOGO_MAX_RECORDS, unsupported_reason
from ui.repository_table import RepositoryTable
from ui.theme import tokens
from ui.workers import SortThread

SORT_COLUMN_KEYS = ["name", "language", "stars", "forks", "open_issues", "created_at", "updated_at",
                    "license_name", "full_name", "owner", "default_branch", "visibility", "archived", "id"]
MAX_LEVELS = 4

DEFINITIONS = (
    "<b>How the numbers are counted.</b> A <i>comparison</i> is one comparison of two records by the sort "
    "key(s). A <i>swap</i> is two records exchanging places. A <i>movement</i> is a record written into a position "
    "outside a swap (an insertion-sort shift, a merge-sort output write, a counting-sort placement). Time covers "
    "only the sorting algorithm, not the table, database or key preparation. Timings change a little between runs "
    "(other programs, CPU caches, Python's memory manager), and a better big-O does not guarantee a faster run on "
    "every input: for small or nearly sorted data a simple algorithm can win. Missing values are placed last."
)

TABLE_HEADERS = ["Algorithm", "Scope", "Records", "Time (ms)", "Comparisons", "Swaps", "Movements",
                 "Time: best / average / worst", "Extra space", "Stable", "Verified", "Notes"]


class LevelRow(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)

    def __init__(self, caption, parent=None):
        super().__init__(parent)
        self.caption = QLabel(caption)
        self.caption.setMinimumWidth(55)
        self.column_combo = QComboBox()
        for key in SORT_COLUMN_KEYS:
            self.column_combo.addItem(COLUMN_BY_KEY[key].label, key)
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Ascending (A→Z, small→large, old→new)", False)
        self.direction_combo.addItem("Descending (Z→A, large→small, new→old)", True)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setProperty("variant", "flat")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.caption, self.column_combo, self.direction_combo, self.remove_button):
            layout.addWidget(widget)
        layout.addStretch()
        self.column_combo.currentIndexChanged.connect(self.changed)
        self.direction_combo.currentIndexChanged.connect(self.changed)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))

    def level(self):
        return self.column_combo.currentData(), self.direction_combo.currentData()


class LevelsEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("Add sort level")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.rows_layout)
        add_layout = QHBoxLayout()
        add_layout.addWidget(self.add_button)
        add_layout.addStretch()
        layout.addLayout(add_layout)
        self.add_button.clicked.connect(self.add_level)
        self.add_level("stars", True)

    def add_level(self, column=None, descending=False):
        if len(self.rows) >= MAX_LEVELS:
            return
        row = LevelRow("Sort by" if not self.rows else "Then by")
        if isinstance(column, str):
            row.column_combo.setCurrentIndex(row.column_combo.findData(column))
            row.direction_combo.setCurrentIndex(1 if descending else 0)
        row.changed.connect(self.changed)
        row.remove_requested.connect(self.remove_level)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self.refresh()

    def remove_level(self, row):
        if len(self.rows) == 1:
            return
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        for index, remaining in enumerate(self.rows):
            remaining.caption.setText("Sort by" if index == 0 else "Then by")
        self.refresh()

    def refresh(self):
        for row in self.rows:
            row.remove_button.setVisible(len(self.rows) > 1)
        self.add_button.setEnabled(len(self.rows) < MAX_LEVELS)
        self.changed.emit()

    def levels(self):
        return [row.level() for row in self.rows]


class SortingTab(QWidget):
    apply_requested = pyqtSignal(list, list, str)  # records, levels, scope

    def __init__(self, store, explorer):
        super().__init__()
        self.store = store
        self.explorer = explorer
        self.thread = None
        self.last_result_records = None
        self.last_levels = None
        self.last_scope = "full"
        self.pending_is_complete = False
        self.pending_scope = "full"
        self.pending_levels = []
        self.pending_scope_total = 0

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Full dataset", "full")
        self.scope_combo.addItem("Currently filtered results (from the Explorer)", "filtered")
        self.scope_label = QLabel()
        self.scope_label.setObjectName("muted")
        self.scope_label.setWordWrap(True)
        self.levels_editor = LevelsEditor()
        self.algorithm_combo = QComboBox()
        for name in ALGORITHMS:
            self.algorithm_combo.addItem(name, name)
        self.shuffle_box = QCheckBox("Shuffle the input first (fixed seed 42)")
        self.sample_box = QCheckBox("Use only a random sample of")
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(1, 1_000_000)
        self.sample_spin.setValue(5000)
        self.sample_spin.setSuffix(" records")
        self.algorithm_info = QLabel()
        self.algorithm_info.setWordWrap(True)
        self.algorithm_info.setTextFormat(Qt.TextFormat.RichText)

        settings = QGroupBox("Sort settings")
        grid = QGridLayout(settings)
        grid.addWidget(QLabel("Scope"), 0, 0)
        grid.addWidget(self.scope_combo, 0, 1)
        grid.addWidget(self.scope_label, 0, 2)
        grid.addWidget(QLabel("Columns"), 1, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.levels_editor, 1, 1, 1, 2)
        grid.addWidget(QLabel("Algorithm"), 2, 0)
        grid.addWidget(self.algorithm_combo, 2, 1)
        grid.addWidget(self.algorithm_info, 2, 2)
        options = QHBoxLayout()
        options.addWidget(self.shuffle_box)
        options.addWidget(self.sample_box)
        options.addWidget(self.sample_spin)
        options.addStretch()
        grid.addWidget(QLabel("Input"), 3, 0)
        grid.addLayout(options, 3, 1, 1, 2)
        grid.setColumnStretch(2, 1)

        self.run_button = QPushButton("Run sort")
        self.run_button.setProperty("variant", "primary")
        self.benchmark_button = QPushButton("Benchmark all algorithms")
        self.benchmark_button.setProperty("variant", "primary")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("variant", "danger")
        self.apply_button = QPushButton("Show sorted result in Explorer")
        self.apply_button.setToolTip("Available after a single “Run sort” on every record in the scope "
                                     "(untick “Use only a random sample”).")
        self.status_label = QLabel("Choose columns and an algorithm, then click Run sort or Benchmark.")
        buttons = QHBoxLayout()
        for button in (self.run_button, self.benchmark_button, self.cancel_button, self.apply_button):
            buttons.addWidget(button)
        buttons.addWidget(self.status_label, 1)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.results_table = QTableWidget(0, len(TABLE_HEADERS))
        self.results_table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setMinimumHeight(300)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.preview = RepositoryTable("Run a single sort to preview the first sorted repositories here.", show_pager=False)
        self.preview.setMaximumHeight(210)
        definitions = QLabel(DEFINITIONS)
        definitions.setWordWrap(True)
        definitions.setObjectName("muted")

        layout = QVBoxLayout(self)
        layout.addWidget(settings)
        layout.addLayout(buttons)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.results_table)
        layout.addWidget(QLabel("<b>Preview of the sorted result</b> (first 20 records)"))
        layout.addWidget(self.preview)
        layout.addWidget(definitions)

        self.levels_editor.changed.connect(self.update_algorithm_choices)
        self.algorithm_combo.currentIndexChanged.connect(self.update_algorithm_info)
        self.scope_combo.currentIndexChanged.connect(self.update_scope_label)
        self.store.changed.connect(self.update_scope_label)
        self.run_button.clicked.connect(self.run_single)
        self.benchmark_button.clicked.connect(self.run_benchmark)
        self.cancel_button.clicked.connect(self.cancel)
        self.apply_button.clicked.connect(self.apply_result)
        self.setMinimumHeight(980)
        self.set_running(False)
        self.update_algorithm_choices()
        self.update_scope_label()

    def scope_records(self):
        if self.scope_combo.currentData() == "full":
            return self.store.records
        return self.explorer.filtered_records

    def update_scope_label(self):
        count = len(self.scope_records())
        if self.scope_combo.currentData() == "full":
            text = (f"{count:,} records. The Explorer will show the whole dataset sorted (its filters are cleared). "
                    "The stored dataset order never changes.")
        else:
            text = (f"{count:,} records that match the Explorer’s filters. Only these are sorted and shown; "
                    "all other records stay stored and untouched.")
        self.scope_label.setText(text)

    def update_algorithm_choices(self):
        levels = self.levels_editor.levels()
        model = self.algorithm_combo.model()
        for number in range(self.algorithm_combo.count()):
            reason = unsupported_reason(self.algorithm_combo.itemData(number), levels)
            if isinstance(model, QStandardItemModel):
                model.item(number).setEnabled(reason is None)
            self.algorithm_combo.setItemData(number, reason or "", Qt.ItemDataRole.ToolTipRole)
        if not model.item(self.algorithm_combo.currentIndex()).isEnabled():
            self.algorithm_combo.setCurrentIndex(next(n for n in range(self.algorithm_combo.count())
                                                      if model.item(n).isEnabled()))
        self.update_algorithm_info()

    def update_algorithm_info(self):
        name = self.algorithm_combo.currentData()
        info = ALGORITHMS[name]
        stable_text = ("Stable: repositories with equal keys keep their original order."
                       if info.stable else
                       "Not stable: repositories with equal keys may change their relative order.")
        extra = "" if info.taught_in_class else " (extra algorithm)"
        disabled = [n for n in ALGORITHMS if unsupported_reason(n, self.levels_editor.levels())]
        disabled_text = ""
        if disabled:
            reason = unsupported_reason(disabled[0], self.levels_editor.levels())
            disabled_text = f"<br><span style='color:{tokens['warn']}'>{disabled[0]} is disabled: {reason}</span>"
        self.algorithm_info.setText(
            f"<b>{name}</b>{extra}: {info.description}<br>Time: best {info.best}, average {info.average}, "
            f"worst {info.worst}. Extra memory: {info.space}. {stable_text}{disabled_text}")

    def set_running(self, running):
        for widget in (self.run_button, self.benchmark_button, self.scope_combo, self.algorithm_combo):
            widget.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.apply_button.setEnabled(not running and self.last_result_records is not None)

    def build_input(self):
        scope_records = self.scope_records()
        if not scope_records:
            QMessageBox.information(self, "Nothing to sort",
                                    "There are no records in this scope. Collect data first, or loosen the Explorer filters.")
            return None
        sample = self.sample_spin.value() if self.sample_box.isChecked() else None
        records = prepare_input(scope_records, sample, self.shuffle_box.isChecked())
        return records, len(records) == len(scope_records) and sample is None

    def confirm_slow(self, names, count):
        slow = [name for name in names if ALGORITHMS[name].quadratic]
        if count <= SORT_WARNING_SIZE or not slow:
            return names
        box = QMessageBox(self)
        box.setWindowTitle("Slow algorithms ahead")
        box.setText(f"{', '.join(slow)} compare records in pairs and take O(n²) time. With {count:,} records "
                    f"that can take minutes in Python.\n\nTip: tick “Use only a random sample” to benchmark fewer records.")
        run_all = box.addButton("Run anyway", QMessageBox.ButtonRole.AcceptRole)
        skip = None
        if len(slow) < len(names):
            skip = box.addButton("Skip the slow ones", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is run_all:
            return names
        if skip is not None and box.clickedButton() is skip:
            return [name for name in names if name not in slow]
        return None

    def run_single(self):
        self.start([self.algorithm_combo.currentData()], keep_records=True)

    def run_benchmark(self):
        self.start(list(ALGORITHMS), keep_records=False)

    def start(self, names, keep_records):
        if self.thread is not None:
            return
        prepared = self.build_input()
        if prepared is None:
            return
        records, is_complete = prepared
        if names == ["Bogo Sort"] and len(records) > BOGO_MAX_RECORDS:
            QMessageBox.information(
                self, "Bogo Sort needs a tiny input",
                f"Bogo Sort shuffles the records randomly until they happen to be sorted. That takes about n! tries "
                f"(for {len(records):,} records the number has thousands of digits), so it would never finish.\n\n"
                f"Tick “Use only a random sample of” and set it to {BOGO_MAX_RECORDS} or less, then run again.")
            return
        names = self.confirm_slow(names, len(records))
        if not names:
            return
        self.pending_is_complete = is_complete and keep_records
        self.pending_scope = self.scope_combo.currentData()
        self.pending_levels = self.levels_editor.levels()
        self.pending_scope_total = len(self.scope_records())
        self.last_result_records = None
        self.summary_label.setText("")
        self.thread = SortThread(records, self.pending_levels, names, keep_records)
        self.thread.step.connect(self.status_label.setText)
        self.thread.report_ready.connect(self.show_report)
        self.thread.failed.connect(self.show_failure)
        self.thread.cancelled.connect(lambda: self.finish("Cancelled. Nothing was changed."))
        self.thread.finished.connect(self.thread_finished)
        self.set_running(True)
        self.status_label.setText(f"Sorting {len(records):,} records…")
        self.thread.start()

    def cancel(self):
        if self.thread is not None:
            self.thread.cancel()
            self.status_label.setText("Cancelling…")

    def thread_finished(self):
        self.thread.deleteLater()
        self.thread = None
        self.set_running(False)

    def finish(self, message):
        self.status_label.setText(message)

    def show_failure(self, message):
        self.finish("The sort failed.")
        QMessageBox.warning(self, "Sorting problem", message)

    def show_report(self, report):
        scope_name = "Full dataset" if self.pending_scope == "full" else "Filtered results"
        self.results_table.setRowCount(0)
        for result in report.results:
            self.add_row([result.algorithm, scope_name, f"{result.record_count:,}", f"{result.time_ms:.3f}",
                          f"{result.comparisons:,}", f"{result.swaps:,}", f"{result.movements:,}",
                          result.time_complexity, result.space_complexity, "Yes" if result.stable else "No",
                          "Yes" if result.verified else "NO", result.note],
                         highlight=result.algorithm == report.fastest)
        for name, reason in report.skipped.items():
            self.add_row([name, scope_name, "-", "-", "-", "-", "-", "-", "-", "-", "-", f"Not available: {reason}"],
                         muted=True)
        if report.problems:
            self.summary_label.setText(f"<span style='color:{tokens['danger']}'><b>Comparison is not valid.</b> "
                                       + "; ".join(report.problems) + "</span>")
        elif report.fastest:
            fastest = min(report.results, key=lambda r: r.time_ms)
            count = fastest.record_count
            if len(report.results) == 1:
                self.summary_label.setText(
                    f"<b>{fastest.algorithm}</b> sorted {count:,} records ({scope_name.lower()}) in "
                    f"{fastest.time_ms:.3f} ms. The result was verified (sorted, nothing lost or duplicated).")
            else:
                self.summary_label.setText(
                    f"<b>Fastest on this input: {report.fastest}</b> ({fastest.time_ms:.3f} ms for {count:,} records, "
                    f"{scope_name.lower()}). Every algorithm sorted its own copy of the same input, "
                    f"and all results were verified.")
        else:
            self.summary_label.setText("No algorithm could run on these columns.")

        single = len(report.results) == 1 and report.results[0].records is not None
        if single and report.valid:
            records = report.results[0].records
            self.preview.set_records(records[:20])
            if self.pending_is_complete:
                self.last_result_records = records
                self.last_levels = self.pending_levels
                self.last_scope = self.pending_scope
        else:
            self.preview.set_records([], "Run a single sort (not a sample) to preview the first sorted repositories here.")
        if single and report.valid and not self.pending_is_complete:
            self.finish(f"Done. This run sorted {report.results[0].record_count:,} of {self.pending_scope_total:,} "
                        f"records, so it cannot replace the Explorer table. Untick “Use only a random sample” "
                        f"and run again to enable “Show sorted result in Explorer”.")
        else:
            self.finish("Done.")

    def add_row(self, values, highlight=False, muted=False):
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if 2 <= column <= 6:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if highlight:
                item.setBackground(QBrush(QColor(tokens["ok_row"])))
                item.setForeground(QBrush(QColor(tokens["ok_text"])))
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            if muted:
                item.setForeground(QBrush(QColor(tokens["disabled_text"])))
            self.results_table.setItem(row, column, item)

    def apply_result(self):
        if self.last_result_records is not None:
            self.apply_requested.emit(self.last_result_records, self.last_levels, self.last_scope)

    def shutdown(self):
        if self.thread is not None:
            self.thread.cancel()
            self.thread.wait(10000)
