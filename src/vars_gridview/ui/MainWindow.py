import sys
from pathlib import Path
from shutil import rmtree
from typing import Any, List, Optional, Tuple, cast

from PyQt6 import QtCore, QtGui, QtWidgets
from sharktopoda_client.client import SharktopodaClient

from vars_gridview.lib.config.constants import (
    APP_NAME,
    APP_VERSION,
    ICONS_DIR,
    LOG_DIR,
    STYLE_DIR,
    get_settings,
)
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.annotation.box_handler import BoxHandler
from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.m3.query import QueryConstraint
from vars_gridview.lib.common.filesystem import open_file_browser
from vars_gridview.controllers.annotation_controller import AnnotationController
from vars_gridview.controllers.query_controller import QueryController
from vars_gridview.controllers.session_controller import SessionController
from vars_gridview.ui.mosaic.rect_widget import RectWidget
from vars_gridview.ui.dialogs.confirmation_dialog import ConfirmationDialog
from vars_gridview.ui.dialogs.login_dialog import LoginDialog
from vars_gridview.ui.dialogs.query_dialog import QueryDialog
from vars_gridview.ui.coordinators.annotation_action_coordinator import (
    AnnotationActionCoordinator,
)
from vars_gridview.ui.layout.main_window_layout import MainWindowLayout
from vars_gridview.ui.coordinators.main_window_menu_coordinator import (
    MainWindowMenuCoordinator,
)
from vars_gridview.ui.coordinators.annotation_operation_presenter import (
    AnnotationOperationPresenter,
)
from vars_gridview.ui.coordinators.detail_pane_coordinator import (
    DetailPaneCoordinator,
)
from vars_gridview.ui.coordinators.video_navigation_coordinator import (
    VideoNavigationCoordinator,
)
from vars_gridview.ui.coordinators.shutdown_save_coordinator import (
    ShutdownSaveCoordinator,
)
from vars_gridview.ui.coordinators.query_presentation_coordinator import (
    QueryPresentationCoordinator,
)
from vars_gridview.ui.coordinators.login_session_coordinator import (
    LoginSessionCoordinator,
)
from vars_gridview.ui.coordinators.embedding_lifecycle_coordinator import (
    EmbeddingLifecycleCoordinator,
)
from vars_gridview.ui.coordinators.knowledge_base_ui_coordinator import (
    KnowledgeBaseUiCoordinator,
)
from vars_gridview.ui.coordinators.query_results_coordinator import (
    QueryResultsCoordinator,
)
from vars_gridview.ui.coordinators.rect_interaction_coordinator import (
    RectInteractionCoordinator,
)
from vars_gridview.ui.coordinators.dirty_association_save_coordinator import (
    DirtyAssociationSaveCoordinator,
)
from vars_gridview.ui.settings.SettingsDialog import SettingsDialog
from vars_gridview.ui.dialogs.sort_dialog import SortDialog
from vars_gridview.ui.widgets.status_info_widget import StatusInfoWidget
from vars_gridview.ui.settings.tabs.AppearanceTab import AppearanceTab
from vars_gridview.ui.settings.tabs.CacheTab import CacheTab
from vars_gridview.ui.settings.tabs.EmbeddingsTab import EmbeddingsTab
from vars_gridview.ui.settings.tabs.M3Tab import M3Tab
from vars_gridview.ui.settings.tabs.VideoPlayerTab import VideoPlayerTab
from vars_gridview.ui.style import (
    ACTION_BUTTON_PALETTE,
    action_button_style,
    apply_app_theme,
)


class MainWindow(QtWidgets.QMainWindow):
    """
    Main application window.
    """

    sharktopodaConnected = QtCore.pyqtSignal()

    def __init__(self, app, settings: AppSettings | None = None):
        super().__init__()
        self._app = app
        self._settings = settings or get_settings()

        # Create the main window
        self.ui: Any = cast(Any, MainWindowLayout())
        self.ui.setupUi(self)

        # Set the window title
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setWindowIcon(
            QtGui.QIcon(str(ICONS_DIR / "VARSGridView.iconset" / "icon_256.png"))
        )

        # Style buttons
        self._style_buttons()

        # Restore and style GUI
        self._restore_gui()
        self._style_gui()
        self._settings.gui_style.valueChanged.connect(self._on_gui_style_changed)

        self.last_selected_rect = None  # Last selected ROI

        # Last query request and total row count
        self._shutdown_save = ShutdownSaveCoordinator(parent=self, dialog_parent=self)

        # Services/controllers (initialized after login)
        self._annotation_service = None
        self._kb_service = None
        self._annotation_controller: Optional[AnnotationController] = None
        self._session_controller = SessionController(parent=self)
        self._session_controller.logged_in.connect(self._on_session_logged_in)
        self._login_flow = LoginSessionCoordinator(
            parent=self,
            session_controller=self._session_controller,
        )

        self._query_controller = QueryController(parent=self)
        self._query_controller.query_started.connect(self._on_query_started)
        self._query_controller.query_progress.connect(self._on_query_progress)
        self._query_controller.query_failed.connect(self._on_query_failed)
        self._query_controller.results_ready.connect(self._on_query_results)
        self._query_presentation = QueryPresentationCoordinator(
            parent=self,
            dialog_parent=self,
            status_update_callback=self._update_status_info,
        )
        self._dirty_association_save = DirtyAssociationSaveCoordinator(
            parent=self,
            annotation_service_getter=lambda: self._annotation_service,
        )

        # Image mosaic (holds the thumbnails as a grid of RectWidgets)
        self.image_mosaic = ImageMosaic(
            self.ui.roiGraphicsView,
            self.rect_clicked,
            settings=self._settings,
            dialog_parent=self,
            embedding_model=None,
            concept_provider=lambda: list(self._kb_service.get_concepts().keys())
            if self._kb_service is not None
            else [],
            part_provider=lambda: list(self._kb_service.get_parts())
            if self._kb_service is not None
            else [],
            label_action_callback=self._label_single_from_tile,
            verify_action_callback=self._verify_single_from_tile,
            mark_training_action_callback=self._mark_training_single_from_tile,
        )
        self._annotation_actions = AnnotationActionCoordinator(
            parent=self,
            image_mosaic=self.image_mosaic,
            annotation_controller_getter=lambda: self._annotation_controller,
            kb_service_getter=lambda: self._kb_service,
            settings=self._settings,
        )
        self._annotation_presenter = AnnotationOperationPresenter(
            parent=self,
            image_mosaic=self.image_mosaic,
            roi_graphics_view=self.ui.roiGraphicsView,
            clear_detail_panels_callback=self._clear_detail_panels,
            status_update_callback=self._update_status_info,
            box_handler_getter=lambda: self.box_handler,
            action_state=self._annotation_actions,
        )
        self._detail_pane = DetailPaneCoordinator(
            box_handler_getter=lambda: self.box_handler,
            selected_rect_getter=lambda: self.last_selected_rect,
        )
        self._rect_interaction = RectInteractionCoordinator(
            parent=self,
            dialog_parent=self,
            image_mosaic=self.image_mosaic,
            detail_pane=self._detail_pane,
            roi_detail_graphics_view=self.ui.roiDetailGraphicsView,
            bounding_box_info_tree=self.ui.boundingBoxInfoTree,
            image_info_tree=self.ui.imageInfoTree,
            loaded_getter=lambda: self.loaded,
            box_handler_getter=lambda: self.box_handler,
            last_selected_getter=lambda: self.last_selected_rect,
            last_selected_setter=lambda value: setattr(
                self, "last_selected_rect", value
            ),
            save_dirty_associations_worker=self._dirty_association_save.save_dirty_associations_worker,
        )
        self._video_navigation = VideoNavigationCoordinator()
        self._embedding_lifecycle = EmbeddingLifecycleCoordinator(
            parent=self,
            dialog_parent=self,
            settings=self._settings,
            apply_model_callback=self._apply_embedding_model,
        )
        self._kb_ui = KnowledgeBaseUiCoordinator(
            parent=self,
            dialog_parent=self,
            kb_service_getter=lambda: self._kb_service,
            label_combo_box=self.ui.labelComboBox,
            part_combo_box=self.ui.partComboBox,
        )
        self._query_results = QueryResultsCoordinator(
            parent=self,
            image_mosaic=self.image_mosaic,
            sort_dialog_getter=lambda: self.sort_dialog,
            roi_detail_graphics_view=self.ui.roiDetailGraphicsView,
            settings=self._settings,
            kb_service_getter=lambda: self._kb_service,
            annotation_service_getter=lambda: self._annotation_service,
            change_concept_callback=self._change_concept_from_box,
            change_part_callback=self._change_part_from_box,
            delete_callback=self._delete_from_box,
        )
        self.image_mosaic.stats_changed.connect(self._on_mosaic_stats_changed)

        self.status_info_widget = StatusInfoWidget(
            {"Status": "Ready"}, parent=self.ui.statusInfoContainer
        )
        self.ui.statusInfoLayout.addWidget(self.status_info_widget)

        # Box handler (handles the ROIs and annotations)
        self.box_handler: Optional[BoxHandler] = None

        self.sharktopoda_client = None  # Sharktopoda client
        self.sharktopoda_connected = (
            False  # Whether the Sharktopoda client is connected
        )

        # Connect signals to slots
        self.ui.discardButton.clicked.connect(self.delete)
        self.ui.clearSelections.clicked.connect(self.clear_selected)
        self.ui.labelSelectedButton.clicked.connect(self.label_selected)
        self.ui.verifySelectedButton.clicked.connect(self.verify_selected)
        self.ui.unverifySelectedButton.clicked.connect(self.unverify_selected)
        self.ui.markTrainingSelectedButton.clicked.connect(self.mark_training_selected)
        self.ui.unmarkTrainingSelectedButton.clicked.connect(
            self.unmark_training_selected
        )
        self.ui.zoomSpinBox.valueChanged.connect(self.update_zoom)
        self.ui.hideLabeled.stateChanged.connect(self.update_layout)
        self.ui.hideUnlabeled.stateChanged.connect(self.update_layout)
        self.ui.hideTraining.stateChanged.connect(self.update_layout)
        self.ui.hideNontraining.stateChanged.connect(self.update_layout)
        self.ui.openVideo.clicked.connect(self.open_video)
        self.ui.sortButton.clicked.connect(self._sort_widgets)

        self._settings.label_font_size.valueChanged.connect(self.update_layout)
        self._settings.embeddings_enabled.valueChanged.connect(
            self._embedding_lifecycle.handle_embeddings_enabled
        )
        self._settings.embedding_service_url.valueChanged.connect(
            self._embedding_lifecycle.on_embedding_config_changed
        )
        self._settings.embedding_model_name.valueChanged.connect(
            self._embedding_lifecycle.on_embedding_config_changed
        )

        # Create the settings dialog and register tabs
        self.settings_dialog = SettingsDialog(parent=self)
        self.settings_dialog.register(
            M3Tab(settings=self._settings),
            AppearanceTab(settings=self._settings),
            VideoPlayerTab(
                self._setup_sharktopoda_client,
                self.sharktopodaConnected,
                settings=self._settings,
            ),
            CacheTab(self._clear_cache, settings=self._settings),
            EmbeddingsTab(settings=self._settings),
        )

        # Create the sort dialog
        self.sort_dialog = SortDialog(parent=self)

        self.ui.roiGraphicsView.viewport().setAttribute(
            QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents, False
        )
        self.ui.roiDetailGraphicsView.viewport().setAttribute(
            QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents, False
        )

        self._launch()

    @property
    def loaded(self):
        return self.image_mosaic is not None and self.box_handler is not None

    def _launch(self):
        """
        Perform additional on-launch setup after the window is shown.
        """
        LOGGER.info("Launching application")

        # Run the login procedure
        login_ok = self._login_procedure()
        if not login_ok:
            LOGGER.error("Login failed")
            sys.exit(1)

        # Set up the label combo boxes asynchronously.
        self._kb_ui.setup_label_boxes_async()

        # Set up the menu bar
        self._setup_menu_bar()

        # Set up embeddings
        self._embedding_lifecycle.handle_embeddings_enabled(
            self._settings.embeddings_enabled.value
        )

        # Set up Sharktopoda client
        if self._settings.sharktopoda_autoconnect.value:
            try:
                self._setup_sharktopoda_client()
            except Exception as e:
                LOGGER.warning(f"Could not set up Sharktopoda client: {e}")

        LOGGER.info("Launch successful")

    def _login_procedure(self) -> bool:
        """
        Perform the full login + authentication procedure. Return True on success, False on fail.
        """
        username = self._login_flow.run_login(
            parent_widget=self,
            current_raziel_url=self._settings.raz_url.value,
            set_raziel_url=lambda value: setattr(
                self._settings.raz_url, "value", value
            ),
            login_dialog_factory=lambda parent: LoginDialog(
                parent=parent,
                settings=self._settings,
            ),
        )
        if username is None:
            return False

        # Set the username setting
        self._settings.username.value = username
        if self._annotation_service is not None:
            self._annotation_service.observer = username

        return True

    @QtCore.pyqtSlot(object)
    def _on_session_logged_in(self, _context: object) -> None:
        self._kb_service = self._session_controller.knowledge_base
        self._annotation_service = self._session_controller.annotations
        context = self._session_controller.context

        if (
            self._kb_service is None
            or self._annotation_service is None
            or context is None
        ):
            LOGGER.error("Session initialized without required services")
        else:
            self._query_controller.set_annosaurus_client(context.annosaurus)
            if self._session_controller.roi is None:
                raise RuntimeError("Session initialized without ROI service")
            self.image_mosaic.configure_services(
                annosaurus_client=context.annosaurus,
                vampire_squid_client=context.vampire_squid,
                roi_service=self._session_controller.roi,
            )
            self._annotation_controller = AnnotationController(
                annotation_service=self._annotation_service,
                knowledge_base_service=self._kb_service,
                parent=self,
            )
            self._annotation_controller.operation_started.connect(
                self._on_annotation_operation_started
            )
            self._annotation_controller.operation_finished.connect(
                self._on_annotation_operation_finished
            )
            self._annotation_controller.operation_failed.connect(
                self._on_annotation_operation_failed
            )
            self._annotation_controller.concept_remapped.connect(
                self._on_concept_remapped
            )
            self._kb_ui.warm_kb_cache_async()

    def _setup_menu_bar(self):
        """Populate the menu bar and left toolbar."""
        MainWindowMenuCoordinator(self, self.ui.menuBar).build(
            icons_dir=ICONS_DIR,
            on_open_settings=self._open_settings,
            on_open_log_dir=self._open_log_dir,
            on_query=self._do_query,
            on_next_page=self.next_page,
            on_previous_page=self.previous_page,
        )

    def _setup_sharktopoda_client(self):
        """
        Create the Sharktopoda video player client.
        """
        if (
            self.sharktopoda_client is not None
        ):  # stop the sharktopoda client UDP server
            self.sharktopoda_client.stop_server()

        try:
            self.sharktopoda_client = SharktopodaClient(
                self._settings.sharktopoda_host.value,
                self._settings.sharktopoda_outgoing_port.value,
                self._settings.sharktopoda_incoming_port.value,
            )
        except Exception as e:
            LOGGER.error(f"Could not create Sharktopoda client: {e}")
            return

        for handler in LOGGER.handlers:
            self.sharktopoda_client.logger.addHandler(handler)

        ok = self.sharktopoda_client.connect()
        self.sharktopoda_connected = ok

        if not ok:
            LOGGER.warning("Could not connect to Sharktopoda")
            return

        self.sharktopodaConnected.emit()

    @QtCore.pyqtSlot()
    def _clear_cache(self):
        """
        Clear the cache.
        """
        # Confirm
        cache_dir = Path(self._settings.cache_dir.value)
        confirm = ConfirmationDialog.confirm(
            self,
            "Clear Cache",
            f"Are you sure you want to clear the cache? This will delete the directory:\n{cache_dir.resolve().absolute()}",
        )

        if confirm:
            try:
                rmtree(cache_dir)
                LOGGER.info("Cache cleared")
                QtWidgets.QMessageBox.information(
                    self,
                    "Cache Cleared",
                    "Cache cleared successfully.",
                )
            except Exception as e:
                LOGGER.error(f"Could not clear cache: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "Cache Clear Failed",
                    f"Could not clear cache: {e}",
                )

    def _open_settings(self):
        """
        Open the settings dialog.
        """
        self.settings_dialog.show()

    def _open_log_dir(self):
        """
        Open the log directory.
        """
        open_file_browser(LOG_DIR)

    def _require_loaded(self, operation: str) -> bool:
        """Return True when results are loaded, otherwise show a standard warning."""
        if self.loaded:
            return True
        QtWidgets.QMessageBox.warning(
            self,
            "Not Loaded",
            f"No results are loaded, so {operation} cannot be performed.",
        )
        return False

    def _sort_widgets(self):
        """
        Open the sort dialog and apply a sort method to the rect widgets.
        """
        if not self._require_loaded("sorting"):
            return

        # Show the sort dialog
        ok = self.sort_dialog.exec()
        if not ok:
            return
        method = self.sort_dialog.method
        if method is None:
            return

        self.image_mosaic.sort_rect_widgets(method)

        self.image_mosaic.render_mosaic()

    def _do_query(self):
        """
        Perform a query based on the filter string.
        """
        # Show a query dialog
        query_spec = self.get_query_params()

        if query_spec is None:  # User cancelled, do nothing
            return
        constraints, limit, offset = query_spec
        self._prepare_for_new_results()
        self._query_controller.execute(constraints, limit, offset)

    def next_page(self) -> None:
        if not self._require_loaded("paging"):
            return
        self._prepare_for_new_results()
        self._query_controller.next_page()

    def previous_page(self) -> None:
        if not self._require_loaded("paging"):
            return
        self._prepare_for_new_results()
        self._query_controller.previous_page()

    def _prepare_for_new_results(self) -> None:
        """Reset active selection/detail panes before a new query page loads."""
        if self.last_selected_rect is not None:
            self.image_mosaic.deselect(self.last_selected_rect)
        self.last_selected_rect = None

        self.image_mosaic.clear_view()
        self.box_handler = None
        self.clear_selected()
        self._clear_detail_panels()

    def _clear_detail_panels(self) -> None:
        self._rect_interaction.clear_detail_panels()

    def _sync_display_flags(self) -> None:
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.hide_unlabeled = self.ui.hideUnlabeled.isChecked()
        self.image_mosaic.hide_training = self.ui.hideTraining.isChecked()
        self.image_mosaic.hide_nontraining = self.ui.hideNontraining.isChecked()

    @QtCore.pyqtSlot()
    def _on_query_started(self) -> None:
        self._query_presentation.on_query_started()

    @QtCore.pyqtSlot(str, int, int)
    def _on_query_progress(self, message: str, step: int, total_steps: int) -> None:
        self._query_presentation.on_query_progress(message, step, total_steps)

    @QtCore.pyqtSlot(str)
    def _on_query_failed(self, message: str) -> None:
        self._query_presentation.on_query_failed(message)

    @QtCore.pyqtSlot(list, list, int, int, int)
    def _on_query_results(
        self,
        query_headers: list[str],
        query_rows: list[list[str]],
        page_number: int,
        total_pages: int,
        total_rows: int,
    ) -> None:
        self._query_presentation.mark_rendering()
        self._update_status_info(
            {
                "Page": f"{page_number} of {total_pages}",
                "Rows": str(total_rows),
                "Status": "Ready",
            }
        )

        self.box_handler = self._query_results.apply_query_results(
            query_headers=query_headers,
            query_rows=query_rows,
            hide_labeled=self.ui.hideLabeled.isChecked(),
            hide_unlabeled=self.ui.hideUnlabeled.isChecked(),
            hide_training=self.ui.hideTraining.isChecked(),
            hide_nontraining=self.ui.hideNontraining.isChecked(),
        )
        self._query_presentation.mark_done()

    def _change_concept_from_box(
        self,
        rect_widget: RectWidget,
        current_concept: str,
    ) -> Optional[str]:
        return self._annotation_actions.change_concept_from_box(
            rect_widget,
            current_concept,
        )

    def _change_part_from_box(
        self,
        rect_widget: RectWidget,
        current_part: str,
    ) -> Optional[str]:
        return self._annotation_actions.change_part_from_box(
            rect_widget,
            current_part,
        )

    def _delete_from_box(self, rect_widget: RectWidget) -> None:
        self._annotation_actions.delete_from_box(rect_widget)

    def _label_single_from_tile(
        self,
        rect_widget: RectWidget,
        concept: str,
        part: str,
    ) -> None:
        self._annotation_actions.label_single_from_tile(rect_widget, concept, part)

    def _verify_single_from_tile(self, rect_widget: RectWidget) -> None:
        self._annotation_actions.verify_single_from_tile(rect_widget)

    def _mark_training_single_from_tile(self, rect_widget: RectWidget) -> None:
        self._annotation_actions.mark_training_single_from_tile(rect_widget)

    @QtCore.pyqtSlot(str)
    def _on_annotation_operation_started(self, description: str) -> None:
        self._annotation_presenter.on_started(description)

    @QtCore.pyqtSlot(str)
    def _on_annotation_operation_finished(self, _description: str) -> None:
        self._annotation_presenter.on_finished()

    @QtCore.pyqtSlot(str)
    def _on_annotation_operation_failed(self, message: str) -> None:
        self._annotation_presenter.on_failed(message)

    @QtCore.pyqtSlot(dict)
    def _on_mosaic_stats_changed(self, stats: dict[str, str]) -> None:
        self._update_status_info(stats)

    def _update_status_info(self, state: dict[str, str]) -> None:
        self.status_info_widget.update(state)

    @QtCore.pyqtSlot(str, str)
    def _on_concept_remapped(self, original: str, canonical: str) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Remapped Name",
            f"Remapped concept from '{original}' to '{canonical}'.",
        )

    def _restore_gui(self):
        """
        Restore window size and splitter states
        """
        if self._settings.gui_geometry.value is not None:
            self.restoreGeometry(self._settings.gui_geometry.value)
        if self._settings.gui_window_state.value is not None:
            self.restoreState(self._settings.gui_window_state.value)
        if self._settings.gui_splitter1_state.value is not None:
            self.ui.splitter1.restoreState(self._settings.gui_splitter1_state.value)
        if self._settings.gui_splitter2_state.value is not None:
            self.ui.splitter2.restoreState(self._settings.gui_splitter2_state.value)
        self.ui.zoomSpinBox.setValue(int(self._settings.gui_zoom.value * 100))

    def _save_gui(self):
        self._settings.gui_geometry.value = self.saveGeometry()
        self._settings.gui_window_state.value = self.saveState()
        self._settings.gui_splitter1_state.value = self.ui.splitter1.saveState()
        self._settings.gui_splitter2_state.value = self.ui.splitter2.saveState()

    @QtCore.pyqtSlot(object)
    def _on_gui_style_changed(self, _value: object) -> None:
        self._style_gui()

    def _style_buttons(self):
        """
        Style the main window buttons.
        """
        style = self.style()
        if style is None:
            return

        self.ui.verifySelectedButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton)
        )
        self.ui.unverifySelectedButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self.ui.markTrainingSelectedButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton)
        )
        self.ui.unmarkTrainingSelectedButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self.ui.discardButton.setIcon(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TrashIcon)
        )

        self.ui.labelSelectedButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.label)
        )
        self.ui.verifySelectedButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.verify)
        )
        self.ui.unverifySelectedButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.unverify)
        )
        self.ui.markTrainingSelectedButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.mark_training)
        )
        self.ui.unmarkTrainingSelectedButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.unmark_training)
        )
        self.ui.discardButton.setStyleSheet(
            action_button_style(ACTION_BUTTON_PALETTE.delete)
        )

    def label_selected(self):
        """
        Label selected localizations. Uses the concept & part from the respective combo boxes. If the part is empty, "self" is used.
        """
        if not self._require_loaded("labeling"):
            return

        # Get the concept and part from the combo boxes
        concept = self.ui.labelComboBox.currentText()
        part = self.ui.partComboBox.currentText()

        if part.strip() == "":  # remap empty part to "self"
            part = "self"

        if concept.strip() == "":
            QtWidgets.QMessageBox.critical(
                self, "Empty Concept", "Concept cannot be empty."
            )
            return

        self._annotation_actions.label_selected(concept, part)

    def verify_selected(self):
        """
        Verify the selected localizations.
        """
        self._annotation_actions.verify_selected(True)

    def unverify_selected(self):
        """
        Unverify the selected localizations.
        """
        self._annotation_actions.verify_selected(False)

    @QtCore.pyqtSlot()
    def mark_training_selected(self) -> None:
        """
        Mark the selected localizations for training.
        """
        self._annotation_actions.mark_training_selected(True)

    @QtCore.pyqtSlot()
    def unmark_training_selected(self) -> None:
        """
        Unmark the selected localizations for training.
        """
        self._annotation_actions.mark_training_selected(False)

    @QtCore.pyqtSlot()
    def delete(self):
        if not self._require_loaded("deletions"):
            return

        self._annotation_actions.delete_selected()

    @QtCore.pyqtSlot()
    def clear_selected(self):
        if not self.loaded:
            return

        self.image_mosaic.clear_selected()

    @QtCore.pyqtSlot()
    def update_layout(self):
        if not self.loaded:
            return

        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.hide_unlabeled = self.ui.hideUnlabeled.isChecked()
        self.image_mosaic.hide_training = self.ui.hideTraining.isChecked()
        self.image_mosaic.hide_nontraining = self.ui.hideNontraining.isChecked()

        self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot(int)
    def update_zoom(self, zoom: int):
        self._settings.gui_zoom.value = zoom / 100

    def _apply_embedding_model(self, model: object | None) -> None:
        if self.image_mosaic is not None:
            self.image_mosaic.update_embedding_model(model)
            if model is not None:
                self.image_mosaic.precompute_embeddings_async()

    @QtCore.pyqtSlot(object, object)
    def rect_clicked(self, rect: RectWidget, event: Optional[QtGui.QMouseEvent]):
        self._rect_interaction.handle_rect_clicked(rect, event)

    @QtCore.pyqtSlot()
    def open_video(self):
        """
        Open the video of the last selected ROI, if available
        """
        self._video_navigation.open_video(
            parent=self,
            selected_rect=self.last_selected_rect,
            all_rect_widgets=self.image_mosaic.get_all_rect_widgets(),
            sharktopoda_connected=self.sharktopoda_connected,
            sharktopoda_client=self.sharktopoda_client,
        )

    @QtCore.pyqtSlot()
    def _style_gui(self):
        """
        Set the GUI stylesheet from persisted settings.
        """
        apply_app_theme(self._app, self._settings.gui_style.value, STYLE_DIR)

    def _request_close_after_save(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_gui()
        if self._shutdown_save.consume_allow_close_once():
            QtWidgets.QMainWindow.closeEvent(self, event)
            return

        if self._shutdown_save.handle_close_event(
            event=event,
            loaded=self.loaded,
            box_handler=self.box_handler,
            save_callable=self._dirty_association_save.save_dirty_associations_worker,
            request_close=self._request_close_after_save,
        ):
            return

        QtWidgets.QMainWindow.closeEvent(self, event)

    def get_query_params(self) -> Optional[Tuple[List[QueryConstraint], int, int]]:
        """
        Show the query dialog and return the constraints dictionary, limit, and offset.

        Returns:
            Optional[Tuple[List[QueryConstraint], int, int]]: A tuple containing the constraints list, limit, and offset. None if the dialog was cancelled.
        """
        if self._kb_service is None or self._session_controller.context is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Ready",
                "Knowledge base and user services are not initialized.",
            )
            return None

        dialog = QueryDialog(
            parent=self,
            kb_concepts_getter=lambda: list(self._kb_service.get_concepts().keys()),
            kb_descendants_getter=self._kb_service.get_descendants,
            users_getter=lambda: self._session_controller.context.vars_user_server.get_all_users().json(),
            video_sequence_names_getter=self._kb_service.get_video_sequence_names,
        )
        ok = dialog.exec()
        return (dialog.constraints, dialog.limit, dialog.offset) if ok else None
