from PyQt6.QtCore import QObject, pyqtSignal


class DataStore(QObject):
    """The in-memory copy of the database that every tab reads. Tabs never change it; they copy from it."""

    changed = pyqtSignal()

    def __init__(self, database):
        super().__init__()
        self.database = database
        self.records = []

    def reload(self):
        self.records = self.database.load_all()
        self.changed.emit()
