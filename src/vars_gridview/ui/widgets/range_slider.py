"""A horizontal slider with two handles, for picking a range (e.g. 0.20-0.30).

Qt has no range slider, and the one common add-on (superqt) would be a new
dependency for one control, so this is a small painted widget instead:

- drag either handle; a handle can't pass the other one
- click the track to bring the nearer handle there
- arrow keys move the handle last touched by 1, Page Up/Down by 10

Values are integers in ``[minimum, maximum]``; ``valuesChanged(low, high)``
fires on every change. Colours come from the widget's palette, so it fits
both the light and the dark themes.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPalette, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

_HANDLE_RADIUS = 7.0
_TRACK_HEIGHT = 4.0


class RangeSlider(QWidget):
    valuesChanged = pyqtSignal(int, int)  # low, high

    def __init__(self, minimum: int = 0, maximum: int = 100, parent=None) -> None:
        super().__init__(parent)
        self._min, self._max = minimum, maximum
        self._low, self._high = minimum, maximum
        self._active = 0  # 0 = low handle, 1 = high handle: what the keys move
        self._dragging: int | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(80)

    # -- values ---------------------------------------------------------------

    def values(self) -> tuple[int, int]:
        return self._low, self._high

    def setValues(self, low: int, high: int) -> None:
        low = max(self._min, min(int(low), self._max))
        high = max(low, min(int(high), self._max))
        if (low, high) != (self._low, self._high):
            self._low, self._high = low, high
            self.update()
            self.valuesChanged.emit(low, high)

    def _set_handle(self, which: int, value: int) -> None:
        if which == 0:
            self.setValues(min(value, self._high), self._high)
        else:
            self.setValues(self._low, max(value, self._low))

    # -- geometry -------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(200, int(2 * _HANDLE_RADIUS + 8))

    def _span(self) -> tuple[float, float]:
        return _HANDLE_RADIUS + 1, self.width() - _HANDLE_RADIUS - 1

    def _x_of(self, value: int) -> float:
        left, right = self._span()
        return left + (right - left) * (value - self._min) / max(
            1, self._max - self._min
        )

    def _value_at(self, x: float) -> int:
        left, right = self._span()
        frac = (x - left) / max(1.0, right - left)
        return round(self._min + max(0.0, min(1.0, frac)) * (self._max - self._min))

    def _nearer_handle(self, x: float) -> int:
        d_low, d_high = abs(x - self._x_of(self._low)), abs(x - self._x_of(self._high))
        if d_low == d_high:  # handles together: go by which side was clicked
            return 1 if x > self._x_of(self._high) else 0
        return 0 if d_low < d_high else 1

    # -- painting -------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        palette = self.palette()
        track = palette.color(QPalette.ColorRole.Mid)
        selected_range = palette.color(QPalette.ColorRole.Highlight)
        handle = palette.color(QPalette.ColorRole.Button)
        handle_active = palette.color(QPalette.ColorRole.Light)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.height() / 2
        left, right = self._span()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(
            QRectF(left, cy - _TRACK_HEIGHT / 2, right - left, _TRACK_HEIGHT), 2, 2
        )
        x_low, x_high = self._x_of(self._low), self._x_of(self._high)
        p.setBrush(selected_range)
        p.drawRoundedRect(
            QRectF(x_low, cy - _TRACK_HEIGHT / 2, x_high - x_low, _TRACK_HEIGHT), 2, 2
        )
        for which, x in ((0, x_low), (1, x_high)):
            active = self.hasFocus() and which == self._active
            p.setPen(QPen(selected_range if active else track, 2))
            p.setBrush(handle_active if active else handle)
            p.drawEllipse(QPointF(x, cy), _HANDLE_RADIUS, _HANDLE_RADIUS)
        p.end()

    # -- input ----------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        x = event.position().x()
        self._active = self._dragging = self._nearer_handle(x)
        self._set_handle(self._dragging, self._value_at(x))
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging is not None:
            self._set_handle(self._dragging, self._value_at(event.position().x()))

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = None

    def keyPressEvent(self, event) -> None:
        steps = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Down: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: 1,
            Qt.Key.Key_PageDown: -10,
            Qt.Key.Key_PageUp: 10,
        }
        step = steps.get(event.key())
        if step is None:
            return super().keyPressEvent(event)
        current = self._low if self._active == 0 else self._high
        self._set_handle(self._active, current + step)

    def focusInEvent(self, event) -> None:
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.update()
        super().focusOutEvent(event)


__all__ = ["RangeSlider"]
