from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.theme import tokens


class LanguageChart(QWidget):
    """Horizontal bars: how many collected repositories use each of the top languages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setMinimumHeight(250)

    def set_items(self, items):
        self.items = items
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.items:
            painter.setPen(QColor(tokens["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet. Collect repositories to see the chart.")
            return
        label_width, value_width = 130, 70
        row_height = min(30, self.height() / len(self.items))
        biggest = max(count for _, count in self.items)
        bar_space = max(10, self.width() - label_width - value_width)
        for number, (language, count) in enumerate(self.items):
            top = number * row_height
            painter.setPen(QColor(tokens["text"]))
            painter.drawText(QRectF(0, top, label_width - 8, row_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, language)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["accent"]))
            width = bar_space * count / biggest
            painter.drawRoundedRect(QRectF(label_width, top + 5, width, row_height - 10), 4, 4)
            painter.setPen(QColor(tokens["text"]))
            painter.drawText(QRectF(label_width + width + 6, top, value_width, row_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{count:,}")


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self.card_values = {}
        cards = QHBoxLayout()
        for key, caption in (("total", "Unique repositories"), ("languages", "Programming languages"),
                             ("stars", "Total stars"), ("archived", "Archived repositories")):
            cards.addWidget(self.make_card(key, caption))

        self.status_label = QLabel("Idle. Open the Data Collection tab to begin.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_box = QGroupBox("Collection status")
        status_layout = QVBoxLayout(status_box)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        self.chart = LanguageChart()
        chart_box = QGroupBox("Top languages by number of repositories")
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.addWidget(self.chart)

        layout = QVBoxLayout(self)
        layout.addLayout(cards)
        layout.addWidget(status_box)
        layout.addWidget(chart_box, 1)

    def make_card(self, key, caption):
        card = QFrame()
        card.setObjectName("card")
        value = QLabel("0")
        value.setObjectName("cardValue")
        caption_label = QLabel(caption)
        caption_label.setObjectName("cardCaption")
        layout = QVBoxLayout(card)
        layout.addWidget(value)
        layout.addWidget(caption_label)
        self.card_values[key] = value
        return card

    def update_statistics(self, stats):
        for key in ("total", "languages", "stars", "archived"):
            self.card_values[key].setText(f"{stats[key]:,}")
        self.chart.set_items(stats["top_languages"])

    def set_status(self, text):
        self.status_label.setText(text)

    def set_progress(self, done, total):
        if total > 0:
            percent = min(100, int(done * 100 / total))
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent}%  ({done:,} of {total:,})")
