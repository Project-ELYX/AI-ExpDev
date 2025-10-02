from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class AutoGrowTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, min_height: int = 40, max_height: int = 200, parent=None):
        super().__init__(parent)
        self._min_h = int(min_height)
        self._max_h = int(max_height)
        self.setMinimumHeight(self._min_h)
        self.setMaximumHeight(self._max_h)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.document().contentsChanged.connect(self._update_height)
        QtCore.QTimer.singleShot(0, self._update_height)

    def _update_height(self):
        doc = self.document()
        lay = doc.documentLayout()
        h = lay.documentSize().height() if lay else doc.size().height()
        h = int(h) + 10  # small padding
        h = max(self._min_h, min(self._max_h, h))
        self.setFixedHeight(h)

