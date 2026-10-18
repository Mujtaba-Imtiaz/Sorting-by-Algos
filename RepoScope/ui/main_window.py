from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea,
                             QTabWidget, QVBoxLayout, QWidget)

from config import DATABASE_PATH
from database import Database
from ui.collection_tab import CollectionTab
from ui.dashboard_tab import DashboardTab
from ui.data_store import DataStore
from ui.explorer_tab import ExplorerTab
from ui.export_tab import ExportTab
from ui.search_tab import SearchTab
from ui.sorting_tab import SortingTab
from ui import theme


def scrollable(widget):
    """Wraps a tall tab in a scroll area so nothing is cut off on a small screen."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


class MainWindow(QMainWindow):
    theme_changed = pyqtSignal(str)

    def __init__(self, database_path=DATABASE_PATH):
        super().__init__()
        self.setWindowTitle("RepoScope - GitHub Repository Analyzer")
        self.resize(1320, 860)

        self.database = Database(database_path)
        self.store = DataStore(self.database)
        self.dashboard = DashboardTab()
        self.collection = CollectionTab(self.database, database_path)
        self.explorer = ExplorerTab(self.store)
        self.search = SearchTab(self.store, self.explorer)
        self.sorting = SortingTab(self.store, self.explorer)
        self.export = ExportTab(lambda: self.store.records, lambda: self.explorer.displayed_records,
                                self.explorer.selected_records)

        self.tabs = QTabWidget()
        for widget, title in ((scrollable(self.dashboard), "Dashboard"), (scrollable(self.collection), "Data Collection"),
                              (self.explorer, "Repository Explorer"), (self.search, "Search"),
                              (scrollable(self.sorting), "Sorting Laboratory"), (scrollable(self.export), "Export")):
            self.tabs.addTab(widget, title)

        header = QFrame()
        header.setObjectName("header")
        title = QLabel("RepoScope")
        title.setObjectName("appTitle")
        subtitle = QLabel("GitHub Repository Analyzer: collect, search, sort and compare real repository data")
        subtitle.setObjectName("appSubtitle")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.update_theme_button()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 14)
        header_layout.addLayout(titles, 1)
        header_layout.addWidget(self.theme_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.theme_button.clicked.connect(self.toggle_theme)
        self.collection.status_changed.connect(self.dashboard.set_status)
        self.collection.progress_changed.connect(self.dashboard.set_progress)
        self.collection.data_changed.connect(self.store.reload)
        self.sorting.apply_requested.connect(self.show_sorted_result)
        self.store.changed.connect(self.refresh_dashboard)
        self.store.changed.connect(self.update_status_bar)
        self.store.changed.connect(self.export.update_info)

        self.dashboard_timer = QTimer(self)
        self.dashboard_timer.timeout.connect(self.refresh_dashboard_while_collecting)
        self.dashboard_timer.start(2000)
        self.store.reload()

    def update_theme_button(self):
        self.theme_button.setText("Switch to light mode" if theme.current_name == "dark" else "Switch to dark mode")

    def toggle_theme(self):
        name = "light" if theme.current_name == "dark" else "dark"
        theme.apply_theme(QApplication.instance(), name)
        self.update_theme_button()
        self.dashboard.chart.update()
        self.theme_changed.emit(name)

    def refresh_dashboard(self):
        self.dashboard.update_statistics(self.database.get_statistics())

    def refresh_dashboard_while_collecting(self):
        if self.collection.is_busy():
            self.refresh_dashboard()
            stored = self.database.count()
            if stored != len(self.store.records):
                self.statusBar().showMessage(
                    f"The database now has {stored:,} repositories. The Explorer will refresh when collection pauses or ends.")

    def update_status_bar(self):
        self.statusBar().showMessage(f"{len(self.store.records):,} unique repositories loaded from the local database.")

    def show_sorted_result(self, records, levels, scope):
        self.explorer.show_sorted_result(records, levels, scope)
        self.tabs.setCurrentWidget(self.explorer)

    def closeEvent(self, event):
        self.dashboard_timer.stop()
        self.collection.shutdown()
        self.sorting.shutdown()
        self.database.close()
        event.accept()
