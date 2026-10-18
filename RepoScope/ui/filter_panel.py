from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout)

from filtering import NO_VALUE_OPERATORS, Condition, operator_label, operators_for_kind
from models import COLUMN_BY_KEY, COLUMNS

VALUE_HINTS = {"text": "text to look for", "int": "a whole number, e.g. 1000",
               "date": "YYYY-MM-DD, e.g. 2023-06-30", "bool": "true or false"}


class ConditionRow(QFrame):
    remove_requested = pyqtSignal(object)
    apply_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.join_combo = QComboBox()
        self.join_combo.addItems(["AND", "OR"])
        self.first_label = QLabel("Where")
        self.not_box = QCheckBox("NOT")
        self.column_combo = QComboBox()
        for column in COLUMNS:
            self.column_combo.addItem(column.label, column.key)
        self.operator_combo = QComboBox()
        self.value_edit = QLineEdit()
        remove_button = QPushButton("Remove")
        remove_button.setProperty("variant", "flat")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.join_combo, self.first_label, self.not_box, self.column_combo, self.operator_combo):
            layout.addWidget(widget)
        layout.addWidget(self.value_edit, 1)
        layout.addWidget(remove_button)

        self.column_combo.currentIndexChanged.connect(self.update_operators)
        self.operator_combo.currentIndexChanged.connect(self.update_value_field)
        self.value_edit.returnPressed.connect(self.apply_requested)
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        self.column_combo.setCurrentIndex(self.column_combo.findData("language"))
        self.update_operators()
        self.set_first(False)

    def set_first(self, is_first):
        self.join_combo.setVisible(not is_first)
        self.first_label.setVisible(is_first)

    def column_kind(self):
        return COLUMN_BY_KEY[self.column_combo.currentData()].kind

    def update_operators(self):
        kind = self.column_kind()
        self.operator_combo.clear()
        for operator in operators_for_kind(kind):
            self.operator_combo.addItem(operator_label(operator, kind), operator)
        self.update_value_field()

    def update_value_field(self):
        needs_value = self.operator_combo.currentData() not in NO_VALUE_OPERATORS
        self.value_edit.setEnabled(needs_value)
        self.value_edit.setPlaceholderText(VALUE_HINTS[self.column_kind()] if needs_value else "no value needed")
        if not needs_value:
            self.value_edit.clear()

    def to_condition(self):
        return Condition(self.column_combo.currentData(), self.operator_combo.currentData(),
                         self.value_edit.text(), self.not_box.isChecked(), self.join_combo.currentText())


class FilterPanel(QGroupBox):
    apply_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Filters", parent)
        self.rows = []
        self.rows_layout = QVBoxLayout()
        self.hint_label = QLabel("No filters. All repositories are shown. Click “Add condition” to start. "
                                 "AND is applied before OR.")
        self.hint_label.setObjectName("muted")
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)

        add_button = QPushButton("Add condition")
        apply_button = QPushButton("Apply filters")
        apply_button.setProperty("variant", "primary")
        clear_button = QPushButton("Clear filters")
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(apply_button)
        buttons.addWidget(clear_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.hint_label)
        layout.addLayout(self.rows_layout)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        add_button.clicked.connect(self.add_row)
        apply_button.clicked.connect(self.apply_requested)
        clear_button.clicked.connect(lambda: self.clear(apply=True))

    def add_row(self):
        row = ConditionRow()
        row.remove_requested.connect(self.remove_row)
        row.apply_requested.connect(self.apply_requested)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self.refresh_layout()
        return row

    def remove_row(self, row):
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self.refresh_layout()
        self.apply_requested.emit()

    def refresh_layout(self):
        for index, row in enumerate(self.rows):
            row.set_first(index == 0)
        self.hint_label.setVisible(not self.rows)

    def clear(self, apply=False):
        for row in list(self.rows):
            self.rows.remove(row)
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.refresh_layout()
        self.show_error("")
        if apply:
            self.apply_requested.emit()

    def conditions(self):
        return [row.to_condition() for row in self.rows]

    def show_error(self, text):
        self.error_label.setText(text)
