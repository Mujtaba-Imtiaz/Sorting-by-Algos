from PyQt6.QtWidgets import (QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QVBoxLayout, QWidget)

from exporter import export_csv, export_json
from models import COLUMNS


class ExportTab(QWidget):
    def __init__(self, get_all, get_displayed, get_selected):
        super().__init__()
        self.sources = {"all": get_all, "displayed": get_displayed, "selected": get_selected}

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Entire dataset", "all")
        self.scope_combo.addItem("Explorer results (current filters and sorting)", "displayed")
        self.scope_combo.addItem("Rows selected in the Explorer", "selected")
        self.format_combo = QComboBox()
        self.format_combo.addItem("CSV (opens in Excel)", "csv")
        self.format_combo.addItem("JSON", "json")
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        export_button = QPushButton("Export…")
        export_button.setProperty("variant", "primary")

        box = QGroupBox("Export repositories")
        layout = QVBoxLayout(box)
        for caption, widget in (("What to export", self.scope_combo), ("File format", self.format_combo)):
            row = QHBoxLayout()
            label = QLabel(caption)
            label.setMinimumWidth(110)
            row.addWidget(label)
            row.addWidget(widget, 1)
            layout.addLayout(row)
        layout.addWidget(self.info_label)
        buttons = QHBoxLayout()
        buttons.addWidget(export_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.addWidget(box)
        outer.addStretch()

        self.scope_combo.currentIndexChanged.connect(self.update_info)
        self.format_combo.currentIndexChanged.connect(self.update_info)
        export_button.clicked.connect(self.export)
        self.update_info()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_info()

    def records(self):
        return self.sources[self.scope_combo.currentData()]()

    def update_info(self):
        count = len(self.records())
        columns = ", ".join(column.label for column in COLUMNS)
        missing = "empty cells" if self.format_combo.currentData() == "csv" else "null"
        self.info_label.setText(
            f"<b>{count:,} repositories</b> will be exported, in the order shown in the Explorer for the "
            f"second and third options. Each record has all {len(COLUMNS)} attributes: {columns}.<br>"
            f"Missing values are written as {missing}. A GitHub token is never part of the export.")

    def export(self):
        records = self.records()
        if not records:
            QMessageBox.information(self, "Nothing to export", "There are no repositories in this selection.")
            return
        kind = self.format_combo.currentData()
        path, _ = QFileDialog.getSaveFileName(self, "Export repositories", f"reposcope_export.{kind}",
                                              "CSV files (*.csv)" if kind == "csv" else "JSON files (*.json)")
        if not path:
            return
        try:
            (export_csv if kind == "csv" else export_json)(path, records)
        except OSError as error:
            QMessageBox.warning(self, "Export failed", f"The file could not be written:\n{error}")
            return
        QMessageBox.information(self, "Export finished", f"{len(records):,} repositories were saved to:\n{path}")
