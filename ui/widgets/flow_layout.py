from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin: int = 0, hspacing: int | None = None, vspacing: int | None = None):
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._hspace = hspacing
        self._vspace = vspacing

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # type: ignore[override]
        self._items.append(item)

    def addWidget(self, w: QtWidgets.QWidget) -> None:  # convenience
        super().addWidget(w)

    def count(self) -> int:  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> QtCore.Qt.Orientations:  # type: ignore[override]
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QtCore.QSize:  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:  # type: ignore[override]
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        mleft, mtop, mright, mbottom = self.getContentsMargins()
        size += QtCore.QSize(mleft + mright, mtop + mbottom)
        return size

    def _h_spacing(self) -> int:
        if self._hspace is not None:
            return self._hspace
        return self.smartSpacing(QtWidgets.QStyle.PM_LayoutHorizontalSpacing)

    def _v_spacing(self) -> int:
        if self._vspace is not None:
            return self._vspace
        return self.smartSpacing(QtWidgets.QStyle.PM_LayoutVerticalSpacing)

    def smartSpacing(self, pm: QtWidgets.QStyle.PixelMetric) -> int:
        parent = self.parent()
        if isinstance(parent, QtWidgets.QWidget):
            return parent.style().pixelMetric(pm, None, parent)
        return QtWidgets.QApplication.style().pixelMetric(pm)

    def _do_layout(self, rect: QtCore.QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        hspace = self._h_spacing()
        vspace = self._v_spacing()
        mleft, mtop, mright, mbottom = self.getContentsMargins()
        effective_rect = rect.adjusted(mleft, mtop, -mright, -mbottom)
        x = effective_rect.x()
        y = effective_rect.y()
        maxw = effective_rect.width()

        for item in self._items:
            wi = item.sizeHint().width()
            hi = item.sizeHint().height()
            if x > effective_rect.x() and (x + wi) > (effective_rect.x() + maxw):
                x = effective_rect.x()
                y += line_height + vspace
                line_height = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x += wi + hspace
            line_height = max(line_height, hi)
        return y + line_height - rect.y() + mtop + mbottom

