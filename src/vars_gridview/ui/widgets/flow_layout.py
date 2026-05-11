"""Flow layout — wraps child widgets like text in a paragraph."""

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout


class FlowLayout(QLayout):
    """A layout that arranges widgets in a left-to-right, top-to-bottom flow.

    Widgets are placed in a row until the row width is exhausted, then
    a new row starts.  Unlike ``QHBoxLayout``, no stretching occurs —
    each widget keeps its ``sizeHint``.
    """

    def __init__(self, parent=None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list = []
        self.setSpacing(spacing)

    # ── QLayout protocol ───────────────────────────────────────────────────────

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    # ── Layout engine ──────────────────────────────────────────────────────────

    def _do_layout(self, rect: QRect, *, apply: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = eff.x(), eff.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            hint = item.sizeHint()
            w, h = hint.width(), hint.height()
            next_x = x + w
            if next_x > eff.right() and line_height > 0:
                x = eff.x()
                y += line_height + spacing
                next_x = x + w
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x + spacing
            line_height = max(line_height, h)

        return y + line_height - rect.y() + m.bottom()


__all__ = ["FlowLayout"]
