"""Single persistent, multi-stage, cancellable progress dialog."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.style import UiDimensions

_PENDING_GLYPH = "○"  # ○
_ACTIVE_GLYPH = "●"  # ●
_DONE_GLYPH = "✓"  # ✓
_FAILED_GLYPH = "✗"  # ✗


class StagedProgressDialog(QtWidgets.QDialog):
    """Persistent dialog showing a checklist of named stages and one Cancel button.

    Unlike :class:`QtWidgets.QProgressDialog`, this dialog is meant to be created
    once for an entire multi-stage operation and updated in place as each stage
    starts/progresses/completes, so the user always has something readable to
    look at instead of a sequence of dialogs flashing open and closed.
    """

    cancel_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        stages: list[tuple[str, str]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setMinimumWidth(UiDimensions.DIALOG_MIN_WIDTH)

        self._stage_order = [key for key, _ in stages]
        self._rows: dict[str, tuple[QtWidgets.QLabel, str]] = {}
        self._active_key: str | None = None
        self._cancel_requested = False
        self._closing = False

        layout = QtWidgets.QVBoxLayout(self)

        for key, label in stages:
            row = QtWidgets.QHBoxLayout()
            glyph = QtWidgets.QLabel(_PENDING_GLYPH)
            glyph.setFixedWidth(20)
            text = QtWidgets.QLabel(label)
            row.addWidget(glyph)
            row.addWidget(text)
            row.addStretch(1)
            layout.addLayout(row)
            self._rows[key] = (glyph, label)

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setRange(0, 0)
        layout.addWidget(self._progress_bar)

        self._status_label = QtWidgets.QLabel("")
        layout.addWidget(self._status_label)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        self._cancel_button = QtWidgets.QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self._cancel_button)
        layout.addLayout(button_row)

    # ── Cancel / close handling ──────────────────────────────────────────────

    def _on_cancel_clicked(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self._cancel_button.setEnabled(False)
        self._status_label.setText("Cancelling...")
        self.cancel_requested.emit()

    def closeEvent(self, event: QtCore.QEvent) -> None:
        if self._closing:
            event.accept()
            return
        event.ignore()
        self._on_cancel_clicked()

    def _force_close(self) -> None:
        self._closing = True
        self.close()

    # ── Stage updates ────────────────────────────────────────────────────────

    def start_stage(
        self, key: str, *, determinate: bool = False, maximum: int = 0
    ) -> None:
        """Mark *key* as the active stage, completing any previously-active one."""
        if self._active_key is not None and self._active_key != key:
            self.complete_stage(self._active_key)

        self._active_key = key
        glyph, label = self._rows[key]
        glyph.setText(_ACTIVE_GLYPH)
        self._progress_bar.setRange(0, maximum if determinate else 0)
        self._progress_bar.setValue(0)
        self._status_label.setText(label)

    def update_progress(self, current: int, maximum: int) -> None:
        """Update the progress bar for the currently active stage."""
        if maximum <= 0:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, maximum)
            self._progress_bar.setValue(max(0, min(current, maximum)))

    def complete_stage(self, key: str | None = None) -> None:
        """Mark *key* (default: the active stage) as done."""
        key = key or self._active_key
        if key is None or key not in self._rows:
            return
        glyph, _ = self._rows[key]
        glyph.setText(_DONE_GLYPH)
        if key == self._active_key:
            self._active_key = None

    def fail_stage(self, message: str, key: str | None = None) -> None:
        """Mark *key* (default: the active stage) as failed and disable Cancel."""
        key = key or self._active_key
        if key is not None and key in self._rows:
            glyph, _ = self._rows[key]
            glyph.setText(_FAILED_GLYPH)
        self._status_label.setText(message)
        self._cancel_button.setEnabled(False)

    def finish(self) -> None:
        """Mark every stage done and close the dialog."""
        for key in self._stage_order:
            glyph, _ = self._rows[key]
            if glyph.text() != _DONE_GLYPH:
                glyph.setText(_DONE_GLYPH)
        self._active_key = None
        self._force_close()

    def close_dialog(self) -> None:
        """Close the dialog without forcing every stage to completed."""
        self._force_close()

    @property
    def is_cancel_requested(self) -> bool:
        return self._cancel_requested


__all__ = ["StagedProgressDialog"]
