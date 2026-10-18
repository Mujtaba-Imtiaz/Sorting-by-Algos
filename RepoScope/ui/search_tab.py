from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QVBoxLayout, QWidget)

from filtering import NO_VALUE_OPERATORS, operator_label, operators_for_kind
from models import COLUMN_BY_KEY, COLUMNS
from searching_algorithms import (BINARY_OPERATORS, NotSortedError, SearchError, binary_search, hash_search,
                                  linear_search)
from sorting_algorithms import sort_records
from ui.repository_table import RepositoryTable, open_repository_page

METHOD_HELP = {
    "linear": "Linear search checks every record one by one. It works on any data and any operator.",
    "binary": "Binary search halves the search range each step (about log₂ n steps). It only works on data "
              "sorted ascending by the searched column, and only for equals, starts with, greater/less than "
              "and before/after. It cannot find text inside a description (contains).",
    "hash": "A hash index finds exact matches almost instantly after a one-time pass to build the index.",
}


class SearchTab(QWidget):
    def __init__(self, store, explorer):
        super().__init__()
        self.store = store
        self.explorer = explorer

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Full dataset", "full")
        self.scope_combo.addItem("Explorer’s filtered results", "filtered")
        self.column_combo = QComboBox()
        for column in COLUMNS:
            self.column_combo.addItem(column.label, column.key)
        self.operator_combo = QComboBox()
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("value to search for")
        self.method_combo = QComboBox()
        self.method_combo.addItem("Linear search", "linear")
        self.method_combo.addItem("Binary search", "binary")
        self.method_combo.addItem("Hash index (exact match)", "hash")
        search_button = QPushButton("Search")
        search_button.setProperty("variant", "primary")
        open_button = QPushButton("Open selected on GitHub")

        row = QHBoxLayout()
        for caption, widget in (("Search in", self.scope_combo), ("Column", self.column_combo),
                                ("Operator", self.operator_combo)):
            row.addWidget(QLabel(caption))
            row.addWidget(widget)
        row.addWidget(self.value_edit, 1)
        row.addWidget(QLabel("Method"))
        row.addWidget(self.method_combo)
        row.addWidget(search_button)

        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setObjectName("muted")
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.stats_label = QLabel("Run a search to see how many comparisons each method needs.")
        self.stats_label.setWordWrap(True)

        box = QGroupBox("Search")
        box_layout = QVBoxLayout(box)
        box_layout.addLayout(row)
        box_layout.addWidget(self.help_label)
        box_layout.addWidget(self.error_label)
        self.table = RepositoryTable("Search results appear here.")
        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(open_button)
        layout.addLayout(bottom)

        self.column_combo.currentIndexChanged.connect(self.update_operators)
        self.operator_combo.currentIndexChanged.connect(self.update_methods)
        self.method_combo.currentIndexChanged.connect(self.update_help)
        self.value_edit.returnPressed.connect(self.run_search)
        search_button.clicked.connect(self.run_search)
        open_button.clicked.connect(self.open_selected)
        self.table.record_activated.connect(lambda record: open_repository_page(record, self))
        self.column_combo.setCurrentIndex(self.column_combo.findData("name"))
        self.update_operators()

    def update_operators(self):
        kind = COLUMN_BY_KEY[self.column_combo.currentData()].kind
        self.operator_combo.clear()
        for operator in operators_for_kind(kind):
            self.operator_combo.addItem(operator_label(operator, kind), operator)

    def update_methods(self):
        operator = self.operator_combo.currentData()
        allowed = {"linear": True, "binary": operator in BINARY_OPERATORS, "hash": operator == "equals"}
        model = self.method_combo.model()
        if isinstance(model, QStandardItemModel):
            for number in range(self.method_combo.count()):
                model.item(number).setEnabled(allowed[self.method_combo.itemData(number)])
        if not allowed[self.method_combo.currentData()]:
            self.method_combo.setCurrentIndex(0)
        self.value_edit.setEnabled(operator not in NO_VALUE_OPERATORS)
        self.update_help()

    def update_help(self):
        self.help_label.setText(METHOD_HELP[self.method_combo.currentData()])

    def open_selected(self):
        record = self.table.current_record()
        if record:
            open_repository_page(record, self)

    def run_search(self):
        self.error_label.setText("")
        records = self.store.records if self.scope_combo.currentData() == "full" else self.explorer.filtered_records
        column = self.column_combo.currentData()
        operator = self.operator_combo.currentData()
        text = self.value_edit.text()
        method = self.method_combo.currentData()
        note = ""
        try:
            if method == "linear":
                result = linear_search(records, column, operator, text)
            elif method == "hash":
                result = hash_search(records, column, operator, text)
            else:
                try:
                    result = binary_search(records, column, operator, text)
                except NotSortedError:
                    label = COLUMN_BY_KEY[column].label
                    answer = QMessageBox.question(
                        self, "Data is not sorted",
                        f"Binary search only works on data sorted ascending by “{label}”, and this data is not.\n\n"
                        f"Sort a copy with Merge Sort first? (Your stored dataset is not changed.)")
                    if answer != QMessageBox.StandardButton.Yes:
                        self.error_label.setText(f"Binary search cancelled: the data is not sorted by {label}.")
                        return
                    ordered = sort_records(records, [(column, False)], "Merge Sort").records
                    result = binary_search(ordered, column, operator, text)
                    note = f" A copy was sorted by {label} with Merge Sort first (not included in the numbers below)."
        except SearchError as error:
            self.error_label.setText(str(error))
            return
        self.table.set_records(result.matches, "No repository matches that search.")
        setup = f", index build {result.setup_ms:.3f} ms" if result.method == "Hash index lookup" else ""
        self.stats_label.setText(
            f"<b>{result.method}</b>: {len(result.matches):,} matches, {result.comparisons:,} comparisons, "
            f"{result.time_ms:.3f} ms{setup}, searched {len(records):,} records.{note}")
