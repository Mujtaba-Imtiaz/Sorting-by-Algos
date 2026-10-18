from datetime import datetime

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                             QProgressBar, QPushButton, QRadioButton, QSpinBox, QStyle, QVBoxLayout, QWidget)

from config import DEFAULT_TARGET_RECORDS, MAX_SEARCH_RESULTS, TOKEN_ENVIRONMENT_VARIABLE
from github_client import SUPPORTED_FORMATS_HELP, InvalidSourceError, build_bulk_plan, default_token, parse_source_url
from ui.workers import ScraperThread

STATE_IDLE, STATE_RUNNING, STATE_PAUSED, STATE_STOPPING = "idle", "running", "paused", "stopping"


class CollectionTab(QWidget):
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int, int)
    data_changed = pyqtSignal()

    def __init__(self, database, database_path):
        super().__init__()
        self.database = database
        self.database_path = database_path
        self.thread = None
        self.state = STATE_IDLE
        self.session_new = 0
        self.session_duplicates = 0

        self.bulk_radio = QRadioButton("Build a large dataset automatically (recommended, reaches 15,000)")
        self.bulk_radio.setChecked(True)
        self.url_radio = QRadioButton("Collect from a GitHub URL")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/owner/repo   or   https://github.com/search?q=language%3APython+stars%3A%3E1000")
        help_label = QLabel(SUPPORTED_FORMATS_HELP)
        help_label.setObjectName("muted")
        self.progress_info = QLabel()
        self.progress_info.setObjectName("muted")

        source_box = QGroupBox("1. Choose what to collect")
        source_layout = QVBoxLayout(source_box)
        source_layout.addWidget(self.bulk_radio)
        source_layout.addWidget(self.url_radio)
        source_layout.addWidget(self.url_edit)
        source_layout.addWidget(help_label)
        source_layout.addWidget(self.progress_info)

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 200_000)
        self.target_spin.setValue(DEFAULT_TARGET_RECORDS)
        self.target_spin.setSingleStep(1000)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText(f"Optional GitHub token (or set the {TOKEN_ENVIRONMENT_VARIABLE} environment variable)")
        self.restart_box = QCheckBox("Start from the beginning (ignore saved progress; stored records are kept)")
        token_note = QLabel("A token raises the search limit from 10 to 30 requests per minute, so collection is about "
                            "three times faster. It is only kept in memory, never saved, logged or exported.")
        token_note.setObjectName("muted")
        token_note.setWordWrap(True)

        options_box = QGroupBox("2. Options")
        options_layout = QVBoxLayout(options_box)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target number of repositories"))
        target_row.addWidget(self.target_spin)
        target_row.addWidget(QLabel(f"(a single search or user URL can give at most {MAX_SEARCH_RESULTS:,})"))
        target_row.addStretch()
        options_layout.addLayout(target_row)
        options_layout.addWidget(self.token_edit)
        options_layout.addWidget(token_note)
        options_layout.addWidget(self.restart_box)

        style = self.style()
        self.start_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Start")
        self.start_button.setProperty("variant", "primary")
        self.pause_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause), "Pause")
        self.resume_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward), "Resume")
        self.stop_button = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Stop")
        self.stop_button.setProperty("variant", "danger")
        buttons = QHBoxLayout()
        for button in (self.start_button, self.pause_button, self.resume_button, self.stop_button):
            buttons.addWidget(button)
        buttons.addStretch()

        explain = QLabel("“Search 1 of 140” means one of the 140 prepared GitHub searches (language × star range, up to "
                         "1,000 repositories each). “Rate limit” messages are normal: GitHub only allows a few searches "
                         "per minute, so the app waits and then continues by itself. A token makes it about 3 times faster.")
        explain.setObjectName("muted")
        explain.setWordWrap(True)
        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.count_label = QLabel()
        self.session_label = QLabel()
        self.rate_label = QLabel()
        self.rate_label.setObjectName("muted")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setMinimumHeight(140)

        status_box = QGroupBox("3. Progress")
        status_layout = QVBoxLayout(status_box)
        status_layout.addLayout(buttons)
        status_layout.addWidget(explain)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.count_label)
        status_layout.addWidget(self.session_label)
        status_layout.addWidget(self.rate_label)
        status_layout.addWidget(self.log, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(source_box)
        layout.addWidget(options_box)
        layout.addWidget(status_box, 1)

        self.start_button.clicked.connect(self.start)
        self.pause_button.clicked.connect(self.pause)
        self.resume_button.clicked.connect(self.resume)
        self.stop_button.clicked.connect(self.stop)
        self.bulk_radio.toggled.connect(self.update_inputs)
        self.url_edit.textChanged.connect(self.update_saved_progress)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_live_labels)
        self.timer.start(1000)
        self.setMinimumHeight(820)
        self.set_state(STATE_IDLE)
        self.update_live_labels()

    def is_busy(self):
        return self.thread is not None

    def current_source(self):
        if self.bulk_radio.isChecked():
            return build_bulk_plan()
        return parse_source_url(self.url_edit.text())

    def update_inputs(self):
        self.url_edit.setEnabled(self.url_radio.isChecked() and self.state == STATE_IDLE)
        self.update_saved_progress()

    def update_saved_progress(self):
        try:
            source = self.current_source()
        except InvalidSourceError:
            self.progress_info.setText("")
            return
        saved = self.database.get_progress(source.key)
        if not saved:
            self.progress_info.setText("No saved progress for this source yet.")
        elif saved["finished"]:
            self.progress_info.setText("This source was finished before. Start will fetch it again to refresh the data.")
        elif source.kind == "bulk":
            self.progress_info.setText(f"Saved progress: query {saved['query_index'] + 1} of {len(source.queries)}, "
                                       f"page {saved['next_page']}. Start continues from there.")
        else:
            self.progress_info.setText(f"Saved progress: next page is {saved['next_page']}. Start continues from there.")

    def set_state(self, state):
        self.state = state
        idle = state == STATE_IDLE
        self.start_button.setEnabled(idle)
        self.pause_button.setEnabled(state == STATE_RUNNING)
        self.resume_button.setEnabled(state == STATE_PAUSED)
        self.stop_button.setEnabled(state in (STATE_RUNNING, STATE_PAUSED))
        for widget in (self.bulk_radio, self.url_radio, self.target_spin, self.token_edit, self.restart_box):
            widget.setEnabled(idle)
        self.url_edit.setEnabled(idle and self.url_radio.isChecked())

    def add_log(self, level, text):
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {level:<7} {text}")

    def start(self):
        if self.thread is not None:
            return
        try:
            source = self.current_source()
        except InvalidSourceError as error:
            self.add_log("ERROR", str(error))
            QMessageBox.warning(self, "That URL cannot be used", f"{error}\n\n{SUPPORTED_FORMATS_HELP}")
            return
        target = self.target_spin.value()
        if source.kind != "bulk":
            target = min(target, MAX_SEARCH_RESULTS)
        token = self.token_edit.text().strip() or default_token()
        self.session_new = self.session_duplicates = 0
        self.thread = ScraperThread(source, token, target, self.restart_box.isChecked(), self.database_path)
        self.thread.status.connect(self.set_status)
        self.thread.progress.connect(self.on_progress)
        self.thread.log.connect(self.add_log)
        self.thread.done.connect(self.on_done)
        self.thread.finished.connect(self.on_thread_finished)
        self.add_log("INFO", f"Started: {source.title}. Target {target:,}. "
                             f"{'Token in use.' if token else 'No token (lower rate limit).'}")
        self.set_state(STATE_RUNNING)
        self.set_status("Starting…")
        self.thread.start()

    def pause(self):
        if self.thread is not None:
            self.thread.pause()
            self.set_state(STATE_PAUSED)
            self.set_status("Paused. The current request finishes first; everything collected is already saved.")
            self.add_log("INFO", "Paused.")

    def resume(self):
        if self.thread is not None:
            self.thread.resume()
            self.set_state(STATE_RUNNING)
            self.set_status("Resuming…")
            self.add_log("INFO", "Resumed.")

    def stop(self):
        if self.thread is not None:
            self.set_state(STATE_STOPPING)
            self.set_status("Stopping…")
            self.thread.stop()

    def set_status(self, text):
        self.status_label.setText(text)
        self.status_changed.emit(text)

    def on_progress(self, done, total, new_records, duplicate_records):
        self.session_new, self.session_duplicates = new_records, duplicate_records
        if total > 0:
            self.progress_bar.setRange(0, 100)
            percent = min(100, int(done * 100 / total))
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent}%  ({done:,} of {total:,})")
        self.progress_changed.emit(done, total)
        self.update_live_labels()

    def on_done(self, outcome):
        if outcome == "stopped":
            self.set_status("Stopped. Saved records were kept; press Start to continue later.")
            self.add_log("INFO", "Stopped by the user.")
        elif outcome == "finished":
            self.add_log("INFO", "Finished.")

    def on_thread_finished(self):
        self.thread.deleteLater()
        self.thread = None
        self.set_state(STATE_IDLE)
        self.update_saved_progress()
        self.update_live_labels()
        self.data_changed.emit()

    def update_live_labels(self):
        self.count_label.setText(f"<b>Unique repositories in the database: {self.database.count():,}</b>")
        self.session_label.setText(f"This session: {self.session_new:,} new, {self.session_duplicates:,} duplicates "
                                   f"skipped (same repository ID).")
        client = self.thread.client if self.thread is not None else None
        if client is not None and client.rate_limit is not None:
            kind = "with token" if client.has_token else "no token"
            self.rate_label.setText(f"GitHub rate limit ({kind}): {client.rate_remaining} of {client.rate_limit} "
                                    f"requests left, resets in {client.seconds_until_reset()} s.")
        else:
            self.rate_label.setText("GitHub rate limit: not checked yet.")

    def shutdown(self):
        self.timer.stop()
        if self.thread is not None:
            self.thread.stop()
            if not self.thread.wait(30000):
                self.thread.terminate()  # each page is saved in its own transaction, so no data is lost
                self.thread.wait(2000)
