from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.vision.embedding import HttpEmbedding
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class EmbeddingsTab(AbstractSettingsTab):
    """
    Embeddings tab.
    """

    def __init__(self, settings: AppSettings | None = None, parent=None):
        super().__init__("Embeddings", parent=parent)
        self._settings = settings or get_settings()

        self._embeddings_enabled_toggle = QtWidgets.QCheckBox()
        self._embeddings_enabled_toggle.setChecked(
            self._settings.embeddings_enabled.value
        )
        self._embeddings_enabled_toggle.stateChanged.connect(self.settingsChanged.emit)
        self._settings.embeddings_enabled.valueChanged.connect(
            self._embeddings_enabled_toggle.setChecked
        )

        self._service_url_edit = QtWidgets.QLineEdit()
        self._service_url_edit.setText(self._settings.embedding_service_url.value)
        self._service_url_edit.setPlaceholderText(
            "http://donnager.shore.mbari.org:5000/"
        )
        self._service_url_edit.textChanged.connect(self.settingsChanged.emit)
        self._settings.embedding_service_url.valueChanged.connect(
            self._service_url_edit.setText
        )
        self._service_url_edit.editingFinished.connect(self._refresh_image_models_async)

        self._model_name_combo = QtWidgets.QComboBox()
        self._model_name_combo.setEditable(True)
        self._model_name_combo.setInsertPolicy(
            QtWidgets.QComboBox.InsertPolicy.NoInsert
        )
        self._model_name_combo.lineEdit().setPlaceholderText("dinov3_image")
        self._model_name_combo.lineEdit().textChanged.connect(self.settingsChanged.emit)
        self._settings.embedding_model_name.valueChanged.connect(self._set_model_name)
        self._set_model_name(self._settings.embedding_model_name.value)

        self._refresh_models_button = QtWidgets.QPushButton("Refresh")
        self._refresh_models_button.clicked.connect(self._refresh_image_models_async)
        self._models_status_label = QtWidgets.QLabel("")
        self._models_status_label.setWordWrap(True)

        self.arrange()
        QtCore.QTimer.singleShot(0, self._refresh_image_models_async)

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        layout.addRow("Embeddings enabled", self._embeddings_enabled_toggle)
        layout.addRow("Service URL", self._service_url_edit)
        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(self._model_name_combo)
        model_row.addWidget(self._refresh_models_button)
        layout.addRow("Image model", model_row)
        layout.addRow("", self._models_status_label)

        self.setLayout(layout)

    def apply_settings(self):
        changed: set[str] = set()

        if self._settings.embeddings_enabled.set_value(
            self._embeddings_enabled_toggle.isChecked()
        ):
            changed.add(self._settings.embeddings_enabled.key)

        if self._settings.embedding_service_url.set_value(
            self._service_url_edit.text().strip()
        ):
            changed.add(self._settings.embedding_service_url.key)

        if self._settings.embedding_model_name.set_value(
            self._model_name_combo.currentText().strip()
        ):
            changed.add(self._settings.embedding_model_name.key)

        return changed

    def refresh_from_settings(self) -> None:
        prev_enabled = self._embeddings_enabled_toggle.blockSignals(True)
        self._embeddings_enabled_toggle.setChecked(
            self._settings.embeddings_enabled.value
        )
        self._embeddings_enabled_toggle.blockSignals(prev_enabled)

        prev_url = self._service_url_edit.blockSignals(True)
        self._service_url_edit.setText(self._settings.embedding_service_url.value)
        self._service_url_edit.blockSignals(prev_url)

        self._set_model_name(self._settings.embedding_model_name.value)

    def _set_model_name(self, model_name: str) -> None:
        self._model_name_combo.setCurrentText(model_name)

    def _refresh_image_models_async(self) -> None:
        url = self._service_url_edit.text().strip()
        if not url:
            return

        self._refresh_models_button.setEnabled(False)
        self._models_status_label.setText("Loading image models...")

        worker = Worker(HttpEmbedding.list_image_models, url)
        worker.signals.result.connect(self._on_models_loaded)
        worker.signals.error.connect(self._on_models_load_failed)
        worker.signals.finished.connect(self._on_models_load_finished)
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            self._on_models_load_failed(
                (RuntimeError, RuntimeError("No thread pool"), "")
            )
            self._on_models_load_finished()
            return
        pool.start(worker)

    @QtCore.pyqtSlot(object)
    def _on_models_loaded(self, models: list[str]) -> None:
        current_text = self._model_name_combo.currentText()
        self._model_name_combo.blockSignals(True)
        self._model_name_combo.clear()
        self._model_name_combo.addItems(models)
        self._model_name_combo.setCurrentText(current_text)
        self._model_name_combo.blockSignals(False)
        if models:
            self._models_status_label.setText(f"Loaded {len(models)} image models")
        else:
            self._models_status_label.setText("No image models reported by service")

    @QtCore.pyqtSlot(tuple)
    def _on_models_load_failed(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        self._models_status_label.setText(f"Could not load models: {message}")

    @QtCore.pyqtSlot()
    def _on_models_load_finished(self) -> None:
        self._refresh_models_button.setEnabled(True)
