"""Coordinator for embedding model load/reload lifecycle."""

from __future__ import annotations

from typing import Callable

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker


class EmbeddingLifecycleCoordinator(QtCore.QObject):
    """Own embedding model state and async loading flow."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
        settings: AppSettings,
        apply_model_callback: Callable[[object | None], None],
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._settings = settings
        self._apply_model_callback = apply_model_callback

        self._embedding_model = None
        self._embedding_load_in_progress = False
        self._embedding_load_dialog: QtWidgets.QProgressDialog | None = None
        self._pending_embedding_reload = False
        self._loaded_embedding_config: tuple[str, str] | None = None

        self._embedding_config_reload_timer = QtCore.QTimer(self)
        self._embedding_config_reload_timer.setSingleShot(True)
        self._embedding_config_reload_timer.setInterval(150)
        self._embedding_config_reload_timer.timeout.connect(
            self._apply_embedding_config_reload
        )

    def handle_embeddings_enabled(self, embeddings_enabled: bool) -> None:
        if not embeddings_enabled:
            self._embedding_model = None
            self._loaded_embedding_config = None
            self._pending_embedding_reload = False
            self._apply_model_callback(None)
            return

        current_config = self._current_embedding_config()

        if self._embedding_model is not None:
            if self._loaded_embedding_config == current_config:
                self._apply_model_callback(self._embedding_model)
                return

            # Config changed: force reinitialization of the embedding client.
            self._embedding_model = None
            self._apply_model_callback(None)

        if self._embedding_load_in_progress:
            self._pending_embedding_reload = True
            return

        self._embedding_load_in_progress = True
        self._embedding_load_dialog = QtWidgets.QProgressDialog(
            "Connecting to embedding service...",
            None,
            0,
            0,
            self._dialog_parent,
        )
        self._embedding_load_dialog.setWindowTitle("Embeddings")
        self._embedding_load_dialog.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self._embedding_load_dialog.setMinimumDuration(0)
        self._embedding_load_dialog.show()

        worker = Worker(self._create_embedding_model_worker)
        worker.signals.result.connect(self._on_embedding_model_ready)
        worker.signals.error.connect(self._on_embedding_model_error)
        worker.signals.finished.connect(self._on_embedding_model_finished)
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            self._on_embedding_model_error(
                (RuntimeError, RuntimeError("No thread pool"), "")
            )
            self._on_embedding_model_finished()
            return
        pool.start(worker)

    def on_embedding_config_changed(self, _value: object) -> None:
        """Reload embedding client when service URL/model settings change."""
        if not self._settings.embeddings_enabled.value:
            return
        # Coalesce paired settings updates (URL + model) into one reload.
        self._embedding_config_reload_timer.start()

    def _create_embedding_model_worker(self):
        from vars_gridview.lib.vision.embedding import HttpEmbedding

        model = HttpEmbedding(
            base_url=self._settings.embedding_service_url.value,
            model_name=self._settings.embedding_model_name.value,
        )
        model.health_check()
        return model

    @QtCore.pyqtSlot(object)
    def _on_embedding_model_ready(self, model) -> None:
        self._embedding_model = model
        self._loaded_embedding_config = (
            self._settings.embedding_service_url.value.strip().rstrip("/"),
            self._settings.embedding_model_name.value.strip(),
        )
        self._apply_model_callback(model)

    @QtCore.pyqtSlot(tuple)
    def _on_embedding_model_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Could not initialize embedding service: {message}")
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Error",
            f"Could not initialize embedding service: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_embedding_model_finished(self) -> None:
        self._embedding_load_in_progress = False
        if self._embedding_load_dialog is not None:
            self._embedding_load_dialog.close()
            self._embedding_load_dialog = None
        if self._pending_embedding_reload and self._settings.embeddings_enabled.value:
            self._pending_embedding_reload = False
            self._apply_embedding_config_reload()

    def _current_embedding_config(self) -> tuple[str, str]:
        return (
            self._settings.embedding_service_url.value.strip().rstrip("/"),
            self._settings.embedding_model_name.value.strip(),
        )

    def _apply_embedding_config_reload(self) -> None:
        if not self._settings.embeddings_enabled.value:
            return

        desired_config = self._current_embedding_config()
        if (
            self._embedding_model is not None
            and self._loaded_embedding_config == desired_config
        ):
            return

        if self._embedding_load_in_progress:
            self._pending_embedding_reload = True
            return

        self._embedding_model = None
        self._apply_model_callback(None)
        self.handle_embeddings_enabled(True)


__all__ = ["EmbeddingLifecycleCoordinator"]
