"""Coordinator for KB-backed UI setup and background warmup tasks."""

from __future__ import annotations

from typing import Callable

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker


class KnowledgeBaseUiCoordinator(QtCore.QObject):
    """Own KB label-combobox setup and one-time cache warmup workflows."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
        kb_service_getter: Callable[[], object | None],
        label_combo_box: QtWidgets.QComboBox,
        part_combo_box: QtWidgets.QComboBox,
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._kb_service_getter = kb_service_getter
        self._label_combo_box = label_combo_box
        self._part_combo_box = part_combo_box
        self._label_box_load_dialog: QtWidgets.QProgressDialog | None = None
        self._kb_warmup_started = False

    def setup_label_boxes_async(self) -> None:
        """Fetch label-box options in the background with a loading indicator."""
        self._label_box_load_dialog = QtWidgets.QProgressDialog(
            "Loading concepts and parts...",
            None,
            0,
            0,
            self._dialog_parent,
        )
        self._label_box_load_dialog.setWindowTitle("Loading")
        self._label_box_load_dialog.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self._label_box_load_dialog.setMinimumDuration(0)
        self._label_box_load_dialog.show()

        worker = Worker(self._fetch_label_box_items)
        worker.signals.result.connect(self._on_label_box_items_ready)
        worker.signals.error.connect(self._on_label_box_items_failed)
        worker.signals.finished.connect(self._on_label_box_items_finished)

        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            self._on_label_box_items_failed(
                (RuntimeError, RuntimeError("No thread pool"), "")
            )
            self._on_label_box_items_finished()
            return
        pool.start(worker)

    def warm_kb_cache_async(self) -> None:
        """Warm KB caches once per session so later dialogs remain responsive."""
        if self._kb_warmup_started:
            return
        self._kb_warmup_started = True

        worker = Worker(self._warm_kb_cache_worker)
        worker.signals.error.connect(
            lambda err: LOGGER.warning(f"KB warmup failed: {err[1]}")
        )
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.warning(
                "Skipping KB warmup because no global thread pool is available"
            )
            return
        pool.start(worker)

    def _kb_service(self):
        return self._kb_service_getter()

    def _setup_label_boxes(self, kb_concepts: list[str], kb_parts: list[str]) -> None:
        self._label_combo_box.clear()
        concepts = sorted([c for c in kb_concepts if c != ""])
        self._label_combo_box.addItems(concepts)
        self._label_combo_box.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self._label_combo_box.setCurrentIndex(-1)
        self._label_combo_box.lineEdit().setPlaceholderText("Concept")

        self._part_combo_box.clear()
        parts = sorted([p for p in kb_parts if p != ""])
        self._part_combo_box.addItems(parts)
        self._part_combo_box.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self._part_combo_box.setCurrentIndex(-1)
        self._part_combo_box.lineEdit().setPlaceholderText("Part")

    def _fetch_label_box_items(self) -> tuple[list[str], list[str]]:
        kb_service = self._kb_service()
        if kb_service is None:
            raise RuntimeError("Knowledge base service is unavailable")
        kb_concepts = list(kb_service.get_concepts().keys())
        kb_parts = list(kb_service.get_parts())
        return kb_concepts, kb_parts

    @QtCore.pyqtSlot(object)
    def _on_label_box_items_ready(self, payload: tuple[list[str], list[str]]) -> None:
        concepts, parts = payload
        self._setup_label_boxes(concepts, parts)

    @QtCore.pyqtSlot(tuple)
    def _on_label_box_items_failed(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Could not get KB concepts or parts: {message}")
        QtWidgets.QMessageBox.warning(
            self._dialog_parent,
            "Knowledge Base",
            f"Failed to load concepts/parts: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_label_box_items_finished(self) -> None:
        if self._label_box_load_dialog is not None:
            self._label_box_load_dialog.close()
            self._label_box_load_dialog = None

    def _warm_kb_cache_worker(self) -> None:
        kb_service = self._kb_service()
        if kb_service is not None:
            kb_service.get_concepts()
            kb_service.get_parts()


__all__ = ["KnowledgeBaseUiCoordinator"]
