import sys
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast

from PyQt6 import QtCore, QtGui, QtWidgets
from sharktopoda_client.client import SharktopodaClient

from vars_gridview.lib.config.constants import (
    SETTINGS,
    APP_NAME,
    APP_VERSION,
    ICONS_DIR,
    LOG_DIR,
    STYLE_DIR,
)
from vars_gridview.lib.annotation.box_handler import BoxHandler
from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.m3.query import QueryConstraint
from vars_gridview.lib.sorting.sort_methods import RecordedTimestampSort
from vars_gridview.lib.common.filesystem import open_file_browser
from vars_gridview.controllers.annotation_controller import AnnotationController
from vars_gridview.controllers.query_controller import QueryController
from vars_gridview.controllers.session_controller import SessionController
from vars_gridview.lib.runtime.runnables import Worker
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

if TYPE_CHECKING:
    from vars_gridview.lib.vision.embedding import Embedding


class MainWindow(QtWidgets.QMainWindow):
    """
    Main application window.
    """

    sharktopodaConnected = QtCore.pyqtSignal()

    def __init__(self, app):
        super().__init__()
        self._app = app

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
        SETTINGS.gui_style.valueChanged.connect(self._on_gui_style_changed)

        self.last_selected_rect = None  # Last selected ROI

        # Embedding model
        self._embedding_model: Optional[Embedding] = None
        self._embedding_load_in_progress = False
        self._embedding_load_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._pending_embedding_reload = False
        self._loaded_embedding_config: Optional[tuple[str, str]] = None
        self._embedding_config_reload_timer = QtCore.QTimer(self)
        self._embedding_config_reload_timer.setSingleShot(True)
        self._embedding_config_reload_timer.setInterval(150)
        self._embedding_config_reload_timer.timeout.connect(
            self._apply_embedding_config_reload
        )

        # Last query request and total row count
        self._query_running = False
        self._kb_warmup_started = False
        self._label_box_load_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._shutdown_save_in_progress = False
        self._shutdown_after_save = False
        self._shutdown_save_dialog: Optional[QtWidgets.QProgressDialog] = None

        # Services/controllers (initialized after login)
        self._annotation_service = None
        self._kb_service = None
        self._annotation_controller: Optional[AnnotationController] = None
        self._session_controller = SessionController(parent=self)
        self._session_controller.logged_in.connect(self._on_session_logged_in)
        self._session_controller.login_failed.connect(self._on_session_login_failed)
        self._login_event_loop: Optional[QtCore.QEventLoop] = None
        self._login_success = False
        self._login_error: Optional[str] = None

        self._query_controller = QueryController(parent=self)
        self._query_controller.query_started.connect(self._on_query_started)
        self._query_controller.query_progress.connect(self._on_query_progress)
        self._query_controller.query_failed.connect(self._on_query_failed)
        self._query_controller.results_ready.connect(self._on_query_results)
        self._query_progress_dialog: Optional[QtWidgets.QProgressDialog] = None

        # Image mosaic (holds the thumbnails as a grid of RectWidgets)
        self.image_mosaic = ImageMosaic(
            self.ui.roiGraphicsView,
            self.rect_clicked,
            dialog_parent=self,
            embedding_model=self._embedding_model,
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
        self._video_navigation = VideoNavigationCoordinator()
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

        self._sort_method = RecordedTimestampSort

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

        SETTINGS.label_font_size.valueChanged.connect(self.update_layout)
        SETTINGS.embeddings_enabled.valueChanged.connect(self.update_embeddings_enabled)
        SETTINGS.embedding_service_url.valueChanged.connect(
            self._on_embedding_config_changed
        )
        SETTINGS.embedding_model_name.valueChanged.connect(
            self._on_embedding_config_changed
        )

        # Create the settings dialog and register tabs
        self.settings_dialog = SettingsDialog(parent=self)
        self.settings_dialog.register(
            M3Tab(),
            AppearanceTab(),
            VideoPlayerTab(self._setup_sharktopoda_client, self.sharktopodaConnected),
            CacheTab(self._clear_cache),
            EmbeddingsTab(),
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
        self._setup_label_boxes_async()

        # Set up the menu bar
        self._setup_menu_bar()

        # Set up embeddings
        self.update_embeddings_enabled(SETTINGS.embeddings_enabled.value)

        # Set up Sharktopoda client
        if SETTINGS.sharktopoda_autoconnect.value:
            try:
                self._setup_sharktopoda_client()
            except Exception as e:
                LOGGER.warning(f"Could not set up Sharktopoda client: {e}")

        LOGGER.info("Launch successful")

    def _get_login(self) -> Optional[Tuple[str, str, str]]:
        """
        Prompt a login dialog and return the username, password, and Raziel URL. If failed, returns None.
        """
        login_dialog = LoginDialog(parent=self)
        login_dialog.focus_username()
        ok = login_dialog.exec()

        if not ok:
            return None

        return (*login_dialog.credentials, login_dialog.raziel_url)

    def _login_procedure(self) -> bool:
        """
        Perform the full login + authentication procedure. Return True on success, False on fail.
        """
        login = self._get_login()
        if login is None:  # Login failed
            return False

        username, password, raziel_url = login  # unpack the credentials

        # Update the Raziel URL setting
        if SETTINGS.raz_url.value != raziel_url:
            LOGGER.debug(f"Updating Raziel URL setting to {raziel_url}")
            SETTINGS.raz_url.value = raziel_url

        # Authenticate and build session services through the session controller
        ok = self._authenticate_session(raziel_url, username, password)
        if not ok:
            return False

        # Set the username setting
        SETTINGS.username.value = username
        if self._annotation_service is not None:
            self._annotation_service.observer = username

        return True

    def _authenticate_session(
        self, raziel_url: str, username: str, password: str
    ) -> bool:
        """
        Authenticate using SessionController and block until completion.
        """
        self._login_success = False
        self._login_error = None
        self._login_event_loop = QtCore.QEventLoop(self)

        self._session_controller.login(raziel_url, username, password)
        self._login_event_loop.exec()
        self._login_event_loop = None

        if self._login_success:
            LOGGER.info(f"Authenticated user {username} at {raziel_url}")
            return True

        error = self._login_error or "Unknown authentication error"
        LOGGER.error(f"Login failed: {error}")
        QtWidgets.QMessageBox.critical(
            self,
            "Authentication failed",
            f"Failed to authenticate with the configuration server. Check your username and password.\n\n{error}",
        )
        return False

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
            self._login_success = False
            self._login_error = "Session initialized without required services"
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
            self._login_success = True
            self._login_error = None
            self._warm_kb_cache_async()

        if self._login_event_loop is not None and self._login_event_loop.isRunning():
            self._login_event_loop.quit()

    @QtCore.pyqtSlot(str)
    def _on_session_login_failed(self, message: str) -> None:
        self._login_success = False
        self._login_error = message
        if self._login_event_loop is not None and self._login_event_loop.isRunning():
            self._login_event_loop.quit()

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
                SETTINGS.sharktopoda_host.value,
                SETTINGS.sharktopoda_outgoing_port.value,
                SETTINGS.sharktopoda_incoming_port.value,
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
        cache_dir = Path(SETTINGS.cache_dir.value)
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

        self._sort_method = method
        self.image_mosaic.sort_rect_widgets(self._sort_method)

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
        """Clear both detail metadata panels."""
        self.ui.boundingBoxInfoTree.clear()
        self.ui.imageInfoTree.clear()

    def _sync_display_flags(self) -> None:
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.hide_unlabeled = self.ui.hideUnlabeled.isChecked()
        self.image_mosaic.hide_training = self.ui.hideTraining.isChecked()
        self.image_mosaic.hide_nontraining = self.ui.hideNontraining.isChecked()

    @QtCore.pyqtSlot()
    def _on_query_started(self) -> None:
        self._query_running = True
        if self._query_progress_dialog is None:
            self._query_progress_dialog = QtWidgets.QProgressDialog(
                "Starting query...",
                None,
                0,
                6,
                self,
            )
            self._query_progress_dialog.setWindowTitle("Loading Query")
            self._query_progress_dialog.setWindowModality(
                QtCore.Qt.WindowModality.WindowModal
            )
            self._query_progress_dialog.setMinimumDuration(0)
            self._query_progress_dialog.setValue(0)
            self._query_progress_dialog.show()

    @QtCore.pyqtSlot(str, int, int)
    def _on_query_progress(self, message: str, step: int, total_steps: int) -> None:
        if self._query_progress_dialog is None:
            return
        if self._query_progress_dialog.maximum() != total_steps:
            self._query_progress_dialog.setMaximum(total_steps)
        self._query_progress_dialog.setLabelText(message)
        self._query_progress_dialog.setValue(max(0, min(step, total_steps)))

    @QtCore.pyqtSlot(str)
    def _on_query_failed(self, message: str) -> None:
        self._query_running = False
        if self._query_progress_dialog is not None:
            self._query_progress_dialog.close()
            self._query_progress_dialog = None
        self._update_status_info({"Status": "Query failed"})
        QtWidgets.QMessageBox.critical(self, "Query Failed", message)

    @QtCore.pyqtSlot(list, list, int, int, int)
    def _on_query_results(
        self,
        query_headers: list[str],
        query_rows: list[list[str]],
        page_number: int,
        total_pages: int,
        total_rows: int,
    ) -> None:
        self._query_running = False
        if self._query_progress_dialog is not None:
            self._query_progress_dialog.setLabelText("Rendering mosaic...")
            self._query_progress_dialog.setValue(5)
        self._update_status_info(
            {
                "Page": f"{page_number} of {total_pages}",
                "Rows": str(total_rows),
                "Status": "Ready",
            }
        )

        self._sync_display_flags()
        self.image_mosaic.populate(query_headers, query_rows)

        self.sort_dialog.clear()
        self._sort_method = RecordedTimestampSort
        self.image_mosaic.sort_rect_widgets(self._sort_method)
        self.image_mosaic.render_mosaic()

        try:
            if self._kb_service is None:
                raise RuntimeError("Knowledge base service is unavailable")
            kb_concepts = list(self._kb_service.get_concepts().keys())
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts: {e}")
            return

        self.box_handler = BoxHandler(
            self.ui.roiDetailGraphicsView,
            self.image_mosaic,
            all_labels=kb_concepts,
            push_changes_callback=(
                self._annotation_service.push_changes
                if self._annotation_service is not None
                else None
            ),
            change_concept_callback=self._change_concept_from_box,
            change_part_callback=self._change_part_from_box,
            delete_callback=self._delete_from_box,
        )
        if self._query_progress_dialog is not None:
            self._query_progress_dialog.setLabelText("Done")
            self._query_progress_dialog.setValue(6)
            self._query_progress_dialog.close()
            self._query_progress_dialog = None

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

    def _setup_label_boxes(self, kb_concepts: list[str], kb_parts: list[str]) -> None:
        """Populate label combo boxes from already-fetched KB values."""
        self.ui.labelComboBox.clear()
        concepts = sorted([c for c in kb_concepts if c != ""])
        self.ui.labelComboBox.addItems(concepts)
        self.ui.labelComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self.ui.labelComboBox.setCurrentIndex(-1)
        self.ui.labelComboBox.lineEdit().setPlaceholderText("Concept")

        self.ui.partComboBox.clear()
        parts = sorted([p for p in kb_parts if p != ""])
        self.ui.partComboBox.addItems(parts)
        self.ui.partComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self.ui.partComboBox.setCurrentIndex(-1)
        self.ui.partComboBox.lineEdit().setPlaceholderText("Part")

    def _setup_label_boxes_async(self) -> None:
        """Fetch label-box options in the background with a loading indicator."""
        self._label_box_load_dialog = QtWidgets.QProgressDialog(
            "Loading concepts and parts...",
            None,
            0,
            0,
            self,
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

    def _fetch_label_box_items(self) -> tuple[list[str], list[str]]:
        if self._kb_service is None:
            raise RuntimeError("Knowledge base service is unavailable")
        kb_concepts = list(self._kb_service.get_concepts().keys())
        kb_parts = list(self._kb_service.get_parts())
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
            self,
            "Knowledge Base",
            f"Failed to load concepts/parts: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_label_box_items_finished(self) -> None:
        if self._label_box_load_dialog is not None:
            self._label_box_load_dialog.close()
            self._label_box_load_dialog = None

    def _warm_kb_cache_async(self) -> None:
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

    def _warm_kb_cache_worker(self) -> None:
        if self._kb_service is not None:
            self._kb_service.get_concepts()
            self._kb_service.get_parts()

    def _restore_gui(self):
        """
        Restore window size and splitter states
        """
        if SETTINGS.gui_geometry.value is not None:
            self.restoreGeometry(SETTINGS.gui_geometry.value)
        if SETTINGS.gui_window_state.value is not None:
            self.restoreState(SETTINGS.gui_window_state.value)
        if SETTINGS.gui_splitter1_state.value is not None:
            self.ui.splitter1.restoreState(SETTINGS.gui_splitter1_state.value)
        if SETTINGS.gui_splitter2_state.value is not None:
            self.ui.splitter2.restoreState(SETTINGS.gui_splitter2_state.value)
        self.ui.zoomSpinBox.setValue(int(SETTINGS.gui_zoom.value * 100))

    def _save_gui(self):
        SETTINGS.gui_geometry.value = self.saveGeometry()
        SETTINGS.gui_window_state.value = self.saveState()
        SETTINGS.gui_splitter1_state.value = self.ui.splitter1.saveState()
        SETTINGS.gui_splitter2_state.value = self.ui.splitter2.saveState()

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
        SETTINGS.gui_zoom.value = zoom / 100

    @QtCore.pyqtSlot(object)
    def update_embeddings_enabled(self, embeddings_enabled: bool):
        if not embeddings_enabled:
            self._embedding_model = None
            self._loaded_embedding_config = None
            self._pending_embedding_reload = False
            if self.image_mosaic is not None:
                self.image_mosaic.update_embedding_model(None)
            return

        current_config = self._current_embedding_config()

        if self._embedding_model is not None:
            if self._loaded_embedding_config == current_config:
                if self.image_mosaic is not None:
                    self.image_mosaic.update_embedding_model(self._embedding_model)
                return

            # Config changed: force reinitialization of the embedding client.
            self._embedding_model = None
            if self.image_mosaic is not None:
                self.image_mosaic.update_embedding_model(None)

        if self._embedding_load_in_progress:
            self._pending_embedding_reload = True
            return

        self._embedding_load_in_progress = True
        self._embedding_load_dialog = QtWidgets.QProgressDialog(
            "Connecting to embedding service...",
            None,
            0,
            0,
            self,
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

    def _create_embedding_model_worker(self):
        from vars_gridview.lib.vision.embedding import HttpEmbedding

        model = HttpEmbedding(
            base_url=SETTINGS.embedding_service_url.value,
            model_name=SETTINGS.embedding_model_name.value,
        )
        model.health_check()
        return model

    @QtCore.pyqtSlot(object)
    def _on_embedding_model_ready(self, model) -> None:
        self._embedding_model = model
        self._loaded_embedding_config = (
            SETTINGS.embedding_service_url.value.strip().rstrip("/"),
            SETTINGS.embedding_model_name.value.strip(),
        )
        if self.image_mosaic is not None:
            self.image_mosaic.update_embedding_model(model)
            self.image_mosaic.precompute_embeddings_async()

    @QtCore.pyqtSlot(tuple)
    def _on_embedding_model_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Could not initialize embedding service: {message}")
        QtWidgets.QMessageBox.critical(
            self,
            "Error",
            f"Could not initialize embedding service: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_embedding_model_finished(self) -> None:
        self._embedding_load_in_progress = False
        if self._embedding_load_dialog is not None:
            self._embedding_load_dialog.close()
            self._embedding_load_dialog = None
        if self._pending_embedding_reload and SETTINGS.embeddings_enabled.value:
            self._pending_embedding_reload = False
            self._apply_embedding_config_reload()

    def _current_embedding_config(self) -> tuple[str, str]:
        """Return normalized embedding service/model settings tuple."""
        return (
            SETTINGS.embedding_service_url.value.strip().rstrip("/"),
            SETTINGS.embedding_model_name.value.strip(),
        )

    def _apply_embedding_config_reload(self) -> None:
        """Apply a settings-driven embedding reload only when config actually changed."""
        if not SETTINGS.embeddings_enabled.value:
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
        if self.image_mosaic is not None:
            self.image_mosaic.update_embedding_model(None)
        self.update_embeddings_enabled(True)

    @QtCore.pyqtSlot(object)
    def _on_embedding_config_changed(self, _value: object) -> None:
        """Reload embedding client when service URL/model settings change."""
        if not SETTINGS.embeddings_enabled.value:
            return
        # Coalesce paired settings updates (URL + model) into one reload.
        self._embedding_config_reload_timer.start()

    @staticmethod
    def _selection_modifiers(
        event: Optional[QtGui.QMouseEvent],
    ) -> tuple[bool, bool]:
        """Return ``(ctrl, shift)`` modifier state for a click event."""
        if event is None:
            return False, False
        ctrl = bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        return ctrl, shift

    def _save_dirty_boxes_then_handle_click(
        self,
        rect: RectWidget,
        event: Optional[QtGui.QMouseEvent],
    ) -> None:
        """Save dirty detail boxes synchronously, then handle the click."""
        if self.box_handler is not None:
            try:
                self.box_handler.save_all()
            except Exception as exc:
                self._on_pre_click_save_error((type(exc), exc, ""))
                return
        self._apply_rect_click(rect, event)

    @QtCore.pyqtSlot(tuple)
    def _on_pre_click_save_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Could not save localizations: {message}")
        QtWidgets.QMessageBox.critical(
            self,
            "Error",
            f"An error occurred while saving localizations: {message}",
        )

    def _update_mosaic_selection(
        self, rect: RectWidget, ctrl: bool, shift: bool
    ) -> None:
        """Apply ctrl/shift selection behavior in the mosaic view."""
        if shift and self.last_selected_rect is not None:
            self.image_mosaic.select_range(self.last_selected_rect, rect)
        elif ctrl and rect.is_selected:
            self.image_mosaic.deselect(rect)
        else:
            self.image_mosaic.select(rect, clear=not ctrl)

    def _clear_last_detail_selection(
        self, *, clear_detail_overlays: bool = True
    ) -> None:
        """Remove highlight and detail overlays from the prior selected tile."""
        if self.last_selected_rect is None:
            return
        if clear_detail_overlays and self.box_handler is not None:
            self.box_handler.clear()
        self.last_selected_rect.is_last_selected = False
        self.last_selected_rect.update()

    def _detail_view_minimized(self) -> bool:
        """Return True when the detail view cannot render content visibly."""
        return (
            self.ui.roiDetailGraphicsView.width() == 0
            or self.ui.roiDetailGraphicsView.height() == 0
        )

    def _populate_detail_metadata(self, rect: RectWidget) -> None:
        """Refresh detail info panels for the selected localization."""
        self.ui.boundingBoxInfoTree.set_data(rect.association.data)

        ancillary_data = rect.ancillary_data.copy()
        annotation_datetime = rect.annotation_datetime()
        if annotation_datetime is not None:
            ancillary_data["derived_timestamp"] = annotation_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ancillary_data["observation_observer"] = rect.association.observation.observer
        ancillary_data["observation_group"] = rect.association.observation.group
        ancillary_data["imaged_moment_uuid"] = rect.imaged_moment_uuid
        ancillary_data["observation_uuid"] = rect.observation_uuid
        ancillary_data["association_uuid"] = rect.association_uuid

        if rect.association.image_reference_uuid:
            ancillary_data["image_reference_uuid"] = (
                rect.association.image_reference_uuid
            )

        self.ui.imageInfoTree.set_data(ancillary_data)

    def _apply_rect_click(
        self, rect: RectWidget, event: Optional[QtGui.QMouseEvent]
    ) -> None:
        if not self.loaded:
            return

        ctrl, shift = self._selection_modifiers(event)

        previous_rect = self.last_selected_rect
        same_image = False
        if previous_rect is not None:
            same_image = self._detail_pane.rect_source_key(
                rect
            ) == self._detail_pane.rect_source_key(previous_rect)

        self._update_mosaic_selection(rect, ctrl, shift)
        self._clear_last_detail_selection(clear_detail_overlays=not same_image)

        image_view_minimized = self._detail_view_minimized()

        needs_autorange = not (same_image or image_view_minimized)

        # Update the last selection
        rect.is_last_selected = True
        rect.update()
        self.last_selected_rect = rect

        # Update the image and add the boxes asynchronously (only if the detail view isn't minimized)
        if not image_view_minimized:
            reused_overlays = False
            if same_image:
                reused_overlays = self._detail_pane.update_overlays_for_same_source(
                    rect
                )

            if not reused_overlays:
                if same_image and self.box_handler is not None:
                    # Reuse failed (e.g. box count changed); force a clean redraw.
                    self.box_handler.clear()
                self._detail_pane.show_rect_in_detail_async(rect, needs_autorange)

        self._populate_detail_metadata(rect)

    @QtCore.pyqtSlot(object, object)
    def rect_clicked(self, rect: RectWidget, event: Optional[QtGui.QMouseEvent]):
        if not self.loaded:
            return
        self._save_dirty_boxes_then_handle_click(rect, event)

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
        apply_app_theme(self._app, SETTINGS.gui_style.value, STYLE_DIR)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_gui()
        if self._shutdown_after_save:
            QtWidgets.QMainWindow.closeEvent(self, event)
            return

        if self.loaded and self.box_handler is not None:
            event.ignore()
            if self._shutdown_save_in_progress:
                return
            self._shutdown_save_in_progress = True

            self._shutdown_save_dialog = QtWidgets.QProgressDialog(
                "Saving localizations before exit...",
                None,
                0,
                0,
                self,
            )
            self._shutdown_save_dialog.setWindowTitle("Saving")
            self._shutdown_save_dialog.setWindowModality(
                QtCore.Qt.WindowModality.WindowModal
            )
            self._shutdown_save_dialog.setMinimumDuration(0)
            self._shutdown_save_dialog.show()

            worker = Worker(self.box_handler.save_all)
            worker.signals.result.connect(self._on_close_save_ready_from_worker)
            worker.signals.error.connect(self._on_close_save_failed)
            worker.signals.finished.connect(self._on_close_save_finished)
            pool = QtCore.QThreadPool.globalInstance()
            if pool is None:
                self._on_close_save_failed(
                    (RuntimeError, RuntimeError("No thread pool"), "")
                )
                self._on_close_save_finished()
                return
            pool.start(worker)
            return

        QtWidgets.QMainWindow.closeEvent(self, event)

    @QtCore.pyqtSlot()
    def _on_close_save_ready(self) -> None:
        self._shutdown_after_save = True
        self.close()

    @QtCore.pyqtSlot(object)
    def _on_close_save_ready_from_worker(self, _unused) -> None:
        self._on_close_save_ready()

    @QtCore.pyqtSlot(tuple)
    def _on_close_save_failed(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Could not save localizations during shutdown: {message}")
        QtWidgets.QMessageBox.critical(
            self,
            "Error",
            f"An error occurred while saving localizations: {message}",
        )

    @QtCore.pyqtSlot()
    def _on_close_save_finished(self) -> None:
        self._shutdown_save_in_progress = False
        if self._shutdown_save_dialog is not None:
            self._shutdown_save_dialog.close()
            self._shutdown_save_dialog = None

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
