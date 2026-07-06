"""Coordinator owning the single persistent query-loading progress dialog."""

from __future__ import annotations

from typing import Callable

from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.dialogs.staged_progress_dialog import StagedProgressDialog

# Single source of truth for the whole query->mosaic->ROI pipeline's stages.
STAGES: list[tuple[str, str]] = [
    ("count", "Counting matching rows..."),
    ("download", "Downloading result rows..."),
    ("parse", "Parsing result rows..."),
    ("localization", "Preparing localization data..."),
    ("video_sequence", "Fetching video sequence data..."),
    ("proxy_mapping", "Preparing proxy mappings..."),
    ("roi_widgets", "Preparing ROI widgets..."),
    ("roi_images", "Loading ROI images..."),
]


class QueryProgressCoordinator(QtCore.QObject):
    """Own the single progress dialog spanning query fetch + mosaic build + ROI load."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
        status_update_callback: Callable[[dict[str, str]], None],
        cancel_callback: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._status_update_callback = status_update_callback
        self._cancel_callback = cancel_callback
        self._dialog: StagedProgressDialog | None = None

    def on_query_started(self) -> None:
        if self._dialog is not None:
            self._dialog.close_dialog()
        self._dialog = StagedProgressDialog(
            self._dialog_parent, "Loading Query", STAGES
        )
        self._dialog.cancel_requested.connect(self._cancel_callback)
        self._dialog.show()
        self.begin_stage("count")

    def begin_stage(self, key: str, maximum: int = 0) -> None:
        if self._dialog is None:
            return
        self._dialog.start_stage(key, determinate=maximum > 0, maximum=maximum)

    def on_stage_progress(self, key: str, current: int, total: int) -> None:
        if self._dialog is None:
            return
        self._dialog.update_progress(current, total)

    def on_query_cancelled(self) -> None:
        self.close_progress_dialog()
        self._status_update_callback({"Status": "Query cancelled"})

    def on_query_failed(self, message: str) -> None:
        if self._dialog is not None:
            self._dialog.fail_stage(message)
        self._status_update_callback({"Status": "Query failed"})
        QtWidgets.QMessageBox.critical(self._dialog_parent, "Query Failed", message)
        self.close_progress_dialog()

    def mark_done(self) -> None:
        if self._dialog is None:
            return
        self._dialog.finish()
        self._dialog = None

    def close_progress_dialog(self) -> None:
        if self._dialog is not None:
            self._dialog.close_dialog()
            self._dialog = None


__all__ = ["QueryProgressCoordinator", "STAGES"]
