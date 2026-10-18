import sys

try:
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
except ImportError:
    sys.exit("PyQt6 is not installed. Run:  pip install -r requirements.txt")

from ui.main_window import MainWindow
from ui.theme import THEMES, apply_theme, system_theme_name


def main():
    app = QApplication(sys.argv)
    settings = QSettings("RepoScope", "RepoScope")
    saved = settings.value("theme", "")
    apply_theme(app, saved if saved in THEMES else system_theme_name(app))
    window = MainWindow()
    window.theme_changed.connect(lambda name: settings.setValue("theme", name))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
