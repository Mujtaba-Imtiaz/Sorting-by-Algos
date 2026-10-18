from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QStyle, QVBoxLayout, QWidget

from filtering import FilterError, describe_conditions, filter_records
from models import COLUMN_BY_KEY
from sorting_algorithms import sort_records
from ui.filter_panel import FilterPanel
from ui.repository_table import RepositoryDetailDialog, RepositoryTable, open_repository_page

EMPTY_DATASET_TEXT = ("No repositories collected yet.\n\nOpen the “Data Collection” tab and click Start "
                      "to collect repositories from GitHub.")


class ExplorerTab(QWidget):
    """Shows the dataset after filtering and sorting. The stored dataset itself is never reordered."""

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.filtered_records = []  # filtered but not sorted; the Sorting Laboratory can use this
        self.sort_levels = []

        self.summary_label = QLabel()
        self.sort_label = QLabel()
        self.sort_label.setObjectName("muted")
        style = self.style()
        reload_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Reload data")
        details_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Details")
        open_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_DirLinkIcon), "Open on GitHub")
        clear_sort_button = QPushButton("Clear sorting")

        top = QHBoxLayout()
        top.addWidget(self.summary_label, 1)
        for button in (reload_button, details_button, open_button, clear_sort_button):
            top.addWidget(button)

        self.filter_panel = FilterPanel()
        self.table = RepositoryTable(EMPTY_DATASET_TEXT)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.sort_label)
        layout.addWidget(self.filter_panel)
        layout.addWidget(self.table, 1)

        reload_button.clicked.connect(self.store.reload)
        details_button.clicked.connect(self.show_details)
        open_button.clicked.connect(self.open_selected)
        clear_sort_button.clicked.connect(self.clear_sorting)
        self.filter_panel.apply_requested.connect(self.apply_filters)
        self.table.sort_requested.connect(self.on_sort_requested)
        self.table.record_activated.connect(lambda record: RepositoryDetailDialog(record, self).exec())
        self.store.changed.connect(self.apply_filters)

    @property
    def displayed_records(self):
        return self.table.records

    def selected_records(self):
        return self.table.selected_records()

    def apply_filters(self):
        try:
            self.filtered_records = filter_records(self.store.records, self.filter_panel.conditions())
        except FilterError as error:
            self.filter_panel.show_error(str(error))
            return
        self.filter_panel.show_error("")
        self.show_sorted_rows()

    def show_sorted_rows(self):
        rows = self.filtered_records
        if self.sort_levels and rows:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                rows = sort_records(rows, self.sort_levels, "Merge Sort").records
            finally:
                QApplication.restoreOverrideCursor()
        empty_text = EMPTY_DATASET_TEXT if not self.store.records else "No repositories match the current filters."
        self.table.set_records(rows, empty_text)
        self.update_labels()

    def update_labels(self):
        total = len(self.store.records)
        shown = len(self.table.records)
        self.summary_label.setText(
            f"<b>Showing {shown:,} of {total:,} repositories.</b> Filters: {describe_conditions(self.filter_panel.conditions())}")
        if self.sort_levels:
            parts = [f"{COLUMN_BY_KEY[key].label} {'↓' if descending else '↑'}" for key, descending in self.sort_levels]
            self.sort_label.setText("Sorted by: " + ", then ".join(parts) + "  (Explorer sorting uses Merge Sort)")
            self.table.set_sort_indicator(*self.sort_levels[0])
        else:
            self.sort_label.setText("Click a column header to sort. Hold Shift while clicking to add a second or third level.")
            self.table.set_sort_indicator(None, False)

    def on_sort_requested(self, key):
        shift_held = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        position = next((i for i, (column, _) in enumerate(self.sort_levels) if column == key), None)
        if shift_held and self.sort_levels:
            if position is None:
                self.sort_levels.append((key, False))
            else:
                self.sort_levels[position] = (key, not self.sort_levels[position][1])
        elif len(self.sort_levels) == 1 and position == 0:
            self.sort_levels = [(key, not self.sort_levels[0][1])]
        else:
            self.sort_levels = [(key, False)]
        self.show_sorted_rows()

    def clear_sorting(self):
        self.sort_levels = []
        self.show_sorted_rows()

    def show_sorted_result(self, records, levels, scope):
        """Display a result from the Sorting Laboratory without sorting it again."""
        if scope == "full":
            self.filter_panel.clear()
            self.filtered_records = list(self.store.records)
        self.sort_levels = list(levels)
        self.table.set_records(records, "No repositories to show.")
        self.update_labels()

    def current_record(self):
        record = self.table.current_record()
        if record is None:
            QMessageBox.information(self, "Select a repository", "Click a row in the table first.")
        return record

    def show_details(self):
        record = self.current_record()
        if record:
            RepositoryDetailDialog(record, self).exec()

    def open_selected(self):
        record = self.current_record()
        if record:
            open_repository_page(record, self)
