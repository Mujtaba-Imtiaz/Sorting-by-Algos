import math

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QStackedWidget, QTableView, QVBoxLayout, QWidget)

from models import COLUMNS
from ui.theme import tokens

PAGE_SIZES = [50, 100, 250, 500]
COLUMN_WIDTHS = {"id": 100, "name": 150, "full_name": 210, "owner": 120, "description": 320, "language": 110,
                 "stars": 80, "forks": 80, "open_issues": 95, "created_at": 95, "updated_at": 100,
                 "license_name": 170, "default_branch": 110, "html_url": 260, "archived": 80,
                 "visibility": 80, "collected_at": 130}


def format_value(column, value):
    if value is None or value == "":
        return "—"
    if column.kind == "int":
        return str(value) if column.key == "id" else f"{value:,}"
    if column.kind == "bool":
        return "Yes" if value else "No"
    if column.key == "collected_at":
        return str(value)[:16].replace("T", " ")
    if column.kind == "date":
        return str(value)[:10]
    return str(value)


def open_repository_page(record, parent=None):
    url = record.get("html_url") or ""
    if not url.startswith("https://github.com/"):
        QMessageBox.warning(parent, "Cannot open page", "This repository has no valid GitHub URL.")
        return
    QDesktopServices.openUrl(QUrl(url))


class RepositoryTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column = COLUMNS[index.column()]
        value = self.rows[index.row()].get(column.key)
        if role == Qt.ItemDataRole.DisplayRole:
            return format_value(column, value)
        if role == Qt.ItemDataRole.TextAlignmentRole and column.kind == "int":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and (value is None or value == ""):
            return QBrush(QColor(tokens["disabled_text"]))
        if role == Qt.ItemDataRole.ToolTipRole and column.key in ("description", "html_url") and value:
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section].label
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class RepositoryTable(QWidget):
    """A paged table. Only one page of rows is ever given to the view, so 15,000 records stay fast."""

    sort_requested = pyqtSignal(str)
    record_activated = pyqtSignal(dict)

    def __init__(self, empty_text="Nothing to show yet.", show_pager=True, parent=None):
        super().__init__(parent)
        self.records = []
        self.page = 0
        self.page_size = 100 if show_pager else 1000
        self.default_empty_text = empty_text

        self.count_label = QLabel()
        self.count_label.setObjectName("muted")
        self.first_button = QPushButton("«")
        self.previous_button = QPushButton("‹")
        self.page_label = QLabel()
        self.next_button = QPushButton("›")
        self.last_button = QPushButton("»")
        self.size_combo = QComboBox()
        for size in PAGE_SIZES:
            self.size_combo.addItem(f"{size} per page", size)
        self.size_combo.setCurrentIndex(PAGE_SIZES.index(100))

        top = QHBoxLayout()
        top.addWidget(self.count_label)
        top.addStretch()
        if show_pager:
            for button in (self.first_button, self.previous_button):
                top.addWidget(button)
            top.addWidget(self.page_label)
            for button in (self.next_button, self.last_button):
                top.addWidget(button)
            top.addWidget(self.size_combo)
        for button in (self.first_button, self.previous_button, self.next_button, self.last_button):
            button.setFixedWidth(34)
            button.setProperty("variant", "pager")

        self.model = RepositoryTableModel(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(28)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsClickable(True)
        header.setStretchLastSection(False)
        for number, column in enumerate(COLUMNS):
            self.view.setColumnWidth(number, COLUMN_WIDTHS.get(column.key, 110))

        self.empty_label = QLabel(empty_text)
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty_label)
        self.stack.addWidget(self.view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.stack)

        header.sectionClicked.connect(lambda number: self.sort_requested.emit(COLUMNS[number].key))
        self.view.doubleClicked.connect(lambda index: self.record_activated.emit(self.model.rows[index.row()]))
        self.first_button.clicked.connect(lambda: self.go_to_page(0))
        self.previous_button.clicked.connect(lambda: self.go_to_page(self.page - 1))
        self.next_button.clicked.connect(lambda: self.go_to_page(self.page + 1))
        self.last_button.clicked.connect(lambda: self.go_to_page(self.page_count() - 1))
        self.size_combo.currentIndexChanged.connect(self.change_page_size)
        self.refresh()

    def page_count(self):
        return max(1, math.ceil(len(self.records) / self.page_size))

    def set_records(self, records, empty_text=None):
        self.records = records
        self.page = 0
        self.empty_label.setText(empty_text or self.default_empty_text)
        self.refresh()

    def go_to_page(self, page):
        self.page = min(max(page, 0), self.page_count() - 1)
        self.refresh()

    def change_page_size(self):
        self.page_size = self.size_combo.currentData()
        self.page = 0
        self.refresh()

    def refresh(self):
        start = self.page * self.page_size
        self.model.set_rows(self.records[start:start + self.page_size])
        total = len(self.records)
        self.count_label.setText(f"{total:,} repositories" if total else "")
        self.page_label.setText(f"Page {self.page + 1} of {self.page_count()}")
        self.first_button.setEnabled(self.page > 0)
        self.previous_button.setEnabled(self.page > 0)
        self.next_button.setEnabled(self.page < self.page_count() - 1)
        self.last_button.setEnabled(self.page < self.page_count() - 1)
        self.stack.setCurrentWidget(self.view if total else self.empty_label)

    def set_sort_indicator(self, column_key, descending):
        header = self.view.horizontalHeader()
        if column_key is None:
            header.setSortIndicatorShown(False)
            return
        number = [column.key for column in COLUMNS].index(column_key)
        order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
        header.setSortIndicatorShown(True)
        header.setSortIndicator(number, order)

    def selected_records(self):
        rows = sorted({index.row() for index in self.view.selectionModel().selectedRows()})
        return [self.model.rows[row] for row in rows]

    def current_record(self):
        index = self.view.currentIndex()
        if index.isValid():
            return self.model.rows[index.row()]
        selected = self.selected_records()
        return selected[0] if selected else None


class RepositoryDetailDialog(QDialog):
    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(record.get("full_name") or "Repository details")
        self.setMinimumWidth(560)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for column in COLUMNS:
            label = QLabel(format_value(column, record.get(column.key)))
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{column.label}:", label)
        open_button = QPushButton("Open on GitHub")
        open_button.setProperty("variant", "primary")
        open_button.clicked.connect(lambda: open_repository_page(record, self))
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(open_button)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
