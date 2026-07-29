"""Status-bar indicator for a background progress stage (ROI loading, embeddings, ...)."""

from __future__ import annotations

import time
from collections import deque

from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.style import UiDimensions, status_info_item_stylesheet


class ProgressStatusWidget(QtWidgets.QWidget):
    """Compact, non-blocking indicator of an in-flight background batch.

    Shows a determinate progress bar plus a numeric count and a smoothed
    estimate of remaining time. Hidden whenever no batch is running.
    """

    _RATE_WINDOW_SECONDS = 3.0
    _RATE_EMA_ALPHA = 0.3
    _MIN_SAMPLES_FOR_ETA = 2

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent=parent)

        self._label_text = label

        self.setObjectName("StatusInfoItem")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(status_info_item_stylesheet())
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self._label = QtWidgets.QLabel()
        self._label.setObjectName("StatusInfoValue")

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setObjectName("ProgressStatusBar")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedWidth(120)
        self._progress_bar.setFixedHeight(12)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(*UiDimensions.STATUS_ITEM_MARGINS)
        layout.setSpacing(UiDimensions.STATUS_ITEM_SPACING)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._label)
        self.setLayout(layout)

        self._samples: deque[tuple[float, int]] = deque()
        self._ema_rate: float | None = None
        self._total = 0

        self.hide()

    def start(self, total: int) -> None:
        """Begin tracking a new batch of `total` items."""
        self._total = total
        self._samples.clear()
        self._ema_rate = None

        if total <= 0:
            self.hide()
            return

        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(0)
        self._label.setText(f"{self._label_text}: 0/{total}")
        self._record_sample(0)
        self.show()

    def update_progress(self, current: int, total: int) -> None:
        """Reflect a new (current, total) sample, smoothing the ETA."""
        if total <= 0:
            self.hide()
            return

        if total != self._total:
            # Batch shape changed mid-flight (e.g. a new query); restart tracking.
            self.start(total)

        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._record_sample(current)

        eta_text = self._estimate_remaining(current, total)
        self._label.setText(f"{self._label_text}: {current}/{total}{eta_text}")

        if current >= total:
            self.hide()

    def hide_immediately(self) -> None:
        """Hide the indicator, e.g. when an unrelated stage starts or finishes."""
        self.hide()

    def _record_sample(self, current: int) -> None:
        now = time.monotonic()
        self._samples.append((now, current))
        cutoff = now - self._RATE_WINDOW_SECONDS
        while len(self._samples) > 1 and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _estimate_remaining(self, current: int, total: int) -> str:
        if len(self._samples) < self._MIN_SAMPLES_FOR_ETA:
            return ""

        oldest_time, oldest_current = self._samples[0]
        newest_time, newest_current = self._samples[-1]
        dt = newest_time - oldest_time
        d_items = newest_current - oldest_current

        if dt > 0 and d_items > 0:
            instant_rate = d_items / dt
            self._ema_rate = (
                instant_rate
                if self._ema_rate is None
                else self._RATE_EMA_ALPHA * instant_rate
                + (1 - self._RATE_EMA_ALPHA) * self._ema_rate
            )

        if not self._ema_rate:
            return ""

        remaining_items = total - current
        remaining_seconds = remaining_items / self._ema_rate
        return f" (~{self._format_duration(remaining_seconds)} remaining)"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0.0, seconds)
        if seconds < 1:
            return "<1s"
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes}m{secs:02d}s"


__all__ = ["ProgressStatusWidget"]
