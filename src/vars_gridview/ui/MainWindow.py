import os
from pathlib import Path
from shutil import rmtree
import sys
import traceback
import webbrowser
from time import sleep
from typing import TYPE_CHECKING, Optional, Tuple
from uuid import UUID, uuid4

import cv2
import pyqtgraph as pg
import qdarkstyle
from iso8601 import parse_date
from PyQt6 import QtCore, QtGui, QtWidgets
from sharktopoda_client.client import SharktopodaClient
from sharktopoda_client.dto import Localization

from vars_gridview.lib import m3, raziel
from vars_gridview.lib.constants import (
    SETTINGS,
    UI_FILE,
    APP_NAME,
    APP_VERSION,
    ICONS_DIR,
    LOG_DIR,
    SHARKTOPODA_APP_NAME,
    STYLE_DIR,
)
from vars_gridview.lib.box_handler import BoxHandler
from vars_gridview.ui.ImageMosaic import ImageMosaic
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.operations import (
    get_kb_concepts,
    get_kb_name,
    get_kb_parts,
    query_download,
)
from vars_gridview.lib.m3.query import QueryConstraint, QueryRequest, ConstraintSpec
from vars_gridview.lib.sort_methods import RecordedTimestampSort
from vars_gridview.lib.utils import color_for_concept, open_file_browser, parse_tsv
from vars_gridview.ui.RectWidget import RectWidget
from vars_gridview.ui.ConfirmationDialog import ConfirmationDialog
from vars_gridview.ui.JSONTree import JSONTree
from vars_gridview.ui.LoginDialog import LoginDialog
from vars_gridview.ui.QueryDialog import QueryDialog
from vars_gridview.ui.settings.SettingsDialog import SettingsDialog
from vars_gridview.ui.SortDialog import SortDialog
from vars_gridview.ui.settings.tabs.AppearanceTab import AppearanceTab
from vars_gridview.ui.settings.tabs.CacheTab import CacheTab
from vars_gridview.ui.settings.tabs.EmbeddingsTab import EmbeddingsTab
from vars_gridview.ui.settings.tabs.M3Tab import M3Tab
from vars_gridview.ui.settings.tabs.VideoPlayerTab import VideoPlayerTab

if TYPE_CHECKING:
    from vars_gridview.lib.embedding import Embedding


# Define main window class from template
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(UI_FILE)


class MainWindow(TemplateBaseClass):
    """
    Main application window.
    """

    sharktopodaConnected = QtCore.pyqtSignal()

    def __init__(self, app):
        super(QtWidgets.QMainWindow, self).__init__()
        super(TemplateBaseClass, self).__init__()
        self._app = app

        # Create the main window
        self.ui = WindowTemplate()
        self.ui.setupUi(self)

        # Patch UI
        bb_info_tree: QtWidgets.QWidget = self.ui.boundingBoxInfoTree
        bb_info_tree.setLayout(QtWidgets.QVBoxLayout())
        bb_json_tree = JSONTree()
        bb_info_tree.layout().addWidget(bb_json_tree)
        self.ui.boundingBoxInfoTree = bb_json_tree
        ancillary_info_tree: QtWidgets.QWidget = self.ui.imageInfoTree
        ancillary_info_tree.setLayout(QtWidgets.QVBoxLayout())
        ancillary_json_tree = JSONTree()
        ancillary_info_tree.layout().addWidget(ancillary_json_tree)
        self.ui.imageInfoTree = ancillary_json_tree

        # Set the window title
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setWindowIcon(
            QtGui.QIcon(str(ICONS_DIR / "VARSGridView.iconset" / "icon_256x256.png"))
        )

        # Style buttons
        self._style_buttons()

        # Restore and style GUI
        self._restore_gui()
        self._style_gui()

        self.endpoints = None  # The list of endpoint data from Raziel

        self.last_selected_rect = None  # Last selected ROI

        # Embedding model
        self._embedding_model: Optional[Embedding] = None

        # Last query request
        self._last_query_request: Optional[QueryRequest] = None

        # Image mosaic (holds the thumbnails as a grid of RectWidgets)
        self.image_mosaic = ImageMosaic(
            self.ui.roiGraphicsView,
            self.rect_clicked,
            embedding_model=self._embedding_model,
        )

        # Box handler (handles the ROIs and annotations)
        self.box_handler: Optional[BoxHandler] = None

        self.cached_moment_concepts = {}  # Cache for imaged moment -> set of observed concepts

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
        self.ui.markTrainingSelectedButton.clicked.connect(
            self.mark_training_selected
        )  # TODO: implement
        self.ui.unmarkTrainingSelectedButton.clicked.connect(
            self.unmark_training_selected
        )  # TODO: implement
        self.ui.zoomSpinBox.valueChanged.connect(self.update_zoom)
        self.ui.hideLabeled.stateChanged.connect(self.update_layout)
        self.ui.hideUnlabeled.stateChanged.connect(self.update_layout)
        self.ui.hideTraining.stateChanged.connect(self.update_layout)
        self.ui.hideNontraining.stateChanged.connect(self.update_layout)
        self.ui.styleComboBox.currentTextChanged.connect(self._style_gui)
        self.ui.openVideo.clicked.connect(self.open_video)
        self.ui.sortButton.clicked.connect(self._sort_widgets)

        SETTINGS.label_font_size.valueChanged.connect(self.update_layout)
        SETTINGS.embeddings_enabled.valueChanged.connect(self.update_embeddings_enabled)

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

        # Set up the label combo boxes
        self._setup_label_boxes()

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
        login_dialog._login_form._username_line_edit.setFocus()
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

        # Authenticate Raziel + get endpoint data
        endpoints = self._auth_raziel(raziel_url, username, password)
        if endpoints is None:  # Authentication failed
            return False

        # Authenticate M3 modules
        ok = self._setup_m3(endpoints)
        if not ok:
            return False

        # Set the username setting and endpoint data
        SETTINGS.username.value = username
        self.endpoints = endpoints

        return True

    def _auth_raziel(self, raziel_url, username, password) -> Optional[list]:
        """
        Authenticate with Raziel. Return endpoints list on success, None on fail.
        """
        try:
            endpoints = raziel.authenticate(raziel_url, username, password)
            LOGGER.info(f"Authenticated user {username} at {raziel_url}")
            return endpoints
        except Exception as e:
            LOGGER.error(f"Raziel authentication failed: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Authentication failed",
                f"Failed to authenticate with the configuration server. Check your username and password.\n\n{e}",
            )

    def _setup_m3(self, endpoints: list) -> bool:
        """
        Setup the M3 modules from a list of authenticated Raziel endpoint dicts. Return True on success, False on fail.
        """
        try:
            m3.setup_from_endpoint_data(endpoints)
            LOGGER.info("M3 setup successful")
            return True
        except ValueError as e:
            LOGGER.error(f"M3 setup failed: {e}")
            QtWidgets.QMessageBox.critical(
                self, "M3 setup failed", f"M3 setup failed: {e}"
            )
            return False

    def _setup_menu_bar(self):
        """
        Populate the menu bar with menus and actions.
        """
        menu_bar = self.ui.menuBar

        file_menu = menu_bar.addMenu("&File")

        settings_action = QtGui.QAction("&Settings", self)
        settings_icon = QtGui.QIcon(str(ICONS_DIR / "gear-solid.svg"))
        settings_action.setIcon(settings_icon)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        open_log_dir_action = QtGui.QAction("&Open Log Directory", self)
        open_log_dir_icon = QtGui.QIcon(str(ICONS_DIR / "folder-open-solid.svg"))
        open_log_dir_action.setIcon(open_log_dir_icon)
        open_log_dir_action.triggered.connect(self._open_log_dir)
        file_menu.addAction(open_log_dir_action)

        query_menu = menu_bar.addMenu("&Query")

        query_action = QtGui.QAction("&Query", self)
        query_icon = QtGui.QIcon(str(ICONS_DIR / "magnifying-glass-solid.svg"))
        query_action.setIcon(query_icon)
        query_action.setShortcut("Ctrl+Q")
        query_action.triggered.connect(self._do_query)
        query_menu.addAction(query_action)

        next_page_action = QtGui.QAction("&Next Page", self)
        next_page_icon = QtGui.QIcon(str(ICONS_DIR / "right-long-solid.svg"))
        next_page_action.setIcon(next_page_icon)
        next_page_action.triggered.connect(self.next_page)
        query_menu.addAction(next_page_action)

        previous_page_action = QtGui.QAction("&Previous Page", self)
        previous_page_icon = QtGui.QIcon(str(ICONS_DIR / "left-long-solid.svg"))
        previous_page_action.setIcon(previous_page_icon)
        previous_page_action.triggered.connect(self.previous_page)
        query_menu.addAction(previous_page_action)

        # Create a menu with icons on the left-side of the main window
        toolbar = QtWidgets.QToolBar()
        toolbar.setObjectName("toolbar")
        toolbar.addAction(settings_action)
        toolbar.addAction(query_action)
        toolbar.addAction(next_page_action)
        toolbar.addAction(previous_page_action)
        toolbar.addAction(open_log_dir_action)
        toolbar.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(QtCore.Qt.ToolBarArea.LeftToolBarArea, toolbar)

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
            self.sharktopoda_client._udp_client.logger.addHandler(handler)
            self.sharktopoda_client._udp_server.logger.addHandler(handler)

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

    def _sort_widgets(self):
        """
        Open the sort dialog and apply a sort method to the rect widgets.
        """
        if not self.loaded:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Loaded",
                "No results are loaded, so sorting cannot be performed.",
            )
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
        query_spec = self.run_query()
        if query_spec is None:  # User cancelled, do nothing
            return
        else:  # Unload
            if self.last_selected_rect is not None:
                self.image_mosaic.deselect(self.last_selected_rect)
            self.last_selected_rect = None

            if self.image_mosaic:
                self.image_mosaic.clear_view()

            self.box_handler = None
            self.clear_selected()
            self.ui.boundingBoxInfoTree.clear()
            self.ui.imageInfoTree.clear()

        # Run the query
        constraint_dict, limit, offset = query_spec
        constraint_spec = ConstraintSpec.from_dict(constraint_dict)
        query_request = QueryRequest(
            select=[
                "video_reference_uuid",
                "imaged_moment_uuid",
                "observation_uuid",
                "association_uuid",
                "image_reference_uuid",
                "video_sequence_name",
                "chief_scientist",
                "camera_platform",
                "dive_number",
                "video_start_timestamp",
                "video_container",
                "video_uri",
                "video_width",
                "video_height",
                "index_elapsed_time_millis",
                "index_recorded_timestamp",
                "index_timecode",
                "image_url",
                "image_format",
                "observer",
                "concept",
                "link_name",
                "to_concept",
                "link_value",
                "depth_meters",
                "latitude",
                "longitude",
                "oxygen_ml_per_l",
                "pressure_dbar",
                "salinity",
                "temperature_celsius",
                "light_transmission",
                "observation_group",
            ],
            where=[
                QueryConstraint("link_name", equals="bounding box"),
            ],
            order_by=[
                "index_recorded_timestamp",
            ],
        )
        query_request.limit = limit
        query_request.offset = offset
        query_request.where.extend(constraint_spec.to_constraints())
        self._last_query_request = query_request
        try:
            query_data_raw = query_download(query_request)
            query_headers, query_rows = parse_tsv(query_data_raw)
        except Exception as e:
            LOGGER.error(f"Query failed: {e}")
            LOGGER.debug(f"Failed query request: {query_request}")
            LOGGER.debug(f"Query {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(self, "Query Failed", f"Query failed: {e}")
            return

        # Set the display flags
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.hide_unlabeled = self.ui.hideUnlabeled.isChecked()
        self.image_mosaic.hide_training = self.ui.hideTraining.isChecked()
        self.image_mosaic.hide_nontraining = self.ui.hideNontraining.isChecked()

        # Populate the image mosaic
        self.image_mosaic.populate(query_headers, query_rows)

        # Reset sort dialog and default sort method
        self.sort_dialog.clear()
        self._sort_method = RecordedTimestampSort

        self.image_mosaic.sort_rect_widgets(self._sort_method)
        self.image_mosaic.render_mosaic()

        # Show some stats about the images and annotations
        self.statusBar().showMessage(
            "Loaded "
            + str(self.image_mosaic.n_images)
            + " images and "
            + str(self.image_mosaic.n_localizations)
            + " localizations."
        )

        # Create the box handler
        try:
            kb_concepts = get_kb_concepts()
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts: {e}")
            return
        self.box_handler = BoxHandler(
            self.ui.roiDetailGraphicsView,
            self.image_mosaic,
            all_labels=kb_concepts,
        )

    def next_page(self) -> None:
        self._page(True)

    def previous_page(self) -> None:
        self._page(False)

    def _page(self, right: bool) -> None:
        """
        Go to the next or previous page of the query results.
        """
        if not self.loaded:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Loaded",
                "No results are loaded, so paging cannot be performed.",
            )
            return

        if self._last_query_request is None:
            return

        # Get the current offset
        offset = self._last_query_request.offset
        limit = self._last_query_request.limit

        # If offset is 0 and we are going back, do nothing
        if offset == 0 and not right:
            QtWidgets.QMessageBox.warning(
                self,
                "No Previous Page",
                "Already at the first page.",
            )
            return

        # Update the offset
        if right:
            offset += limit
        else:
            offset -= limit
        offset = max(0, offset)

        # Run the query again with the new offset
        self._last_query_request.offset = offset

        if self.last_selected_rect is not None:
            self.image_mosaic.deselect(self.last_selected_rect)
        self.last_selected_rect = None

        # Property clear the graphics view first
        if self.image_mosaic:
            self.image_mosaic.clear_view()

        self.box_handler = None
        self.clear_selected()
        self.ui.boundingBoxInfoTree.clear()
        self.ui.imageInfoTree.clear()

        try:
            query_data_raw = query_download(self._last_query_request)
            query_headers, query_rows = parse_tsv(query_data_raw)
        except Exception as e:
            LOGGER.error(f"Query failed: {e}")
            LOGGER.debug(f"Failed query request: {self._last_query_request}")
            LOGGER.debug(f"Query {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(self, "Query Failed", f"Query failed: {e}")
            return

        # Set the display flags
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.hide_unlabeled = self.ui.hideUnlabeled.isChecked()
        self.image_mosaic.hide_training = self.ui.hideTraining.isChecked()
        self.image_mosaic.hide_nontraining = self.ui.hideNontraining.isChecked()

        # Populate the image mosaic
        self.image_mosaic.populate(query_headers, query_rows)

        # Reset sort dialog and default sort method
        self.sort_dialog.clear()
        self._sort_method = RecordedTimestampSort

        self.image_mosaic.sort_rect_widgets(self._sort_method)
        self.image_mosaic.render_mosaic()

        # Show some stats about the images and annotations
        self.statusBar().showMessage(
            "Loaded "
            + str(self.image_mosaic.n_images)
            + " images and "
            + str(self.image_mosaic.n_localizations)
            + " localizations."
        )

        # Create the box handler
        try:
            kb_concepts = get_kb_concepts()
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts: {e}")
            return
        self.box_handler = BoxHandler(
            self.ui.roiDetailGraphicsView,
            self.image_mosaic,
            all_labels=kb_concepts,
        )

    def _setup_label_boxes(self):
        """
        Populate the label combo boxes
        """
        try:
            kb_concepts = get_kb_concepts()
            kb_parts = get_kb_parts()
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts or parts: {e}")
            return

        # Set up the combo boxes
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
        self.ui.styleComboBox.setCurrentText(SETTINGS.gui_style.value)

    def _save_gui(self):
        SETTINGS.gui_geometry.value = self.saveGeometry()
        SETTINGS.gui_window_state.value = self.saveState()
        SETTINGS.gui_splitter1_state.value = self.ui.splitter1.saveState()
        SETTINGS.gui_splitter2_state.value = self.ui.splitter2.saveState()
        SETTINGS.gui_style.value = self.ui.styleComboBox.currentText()

    def _style_buttons(self):
        """
        Style the main window buttons.
        """
        style = self.style()

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

        self.ui.labelSelectedButton.setStyleSheet("background-color: #085d8e;")
        self.ui.verifySelectedButton.setStyleSheet(
            "background-color: #088e0d;"
        )  # green
        self.ui.unverifySelectedButton.setStyleSheet(
            "background-color: #8e4708;"
        )  # orange
        self.ui.markTrainingSelectedButton.setStyleSheet(
            "background-color: #088e8e;"
        )  # cyan variant
        self.ui.unmarkTrainingSelectedButton.setStyleSheet(
            "background-color: #8e8e08;"
        )  # yellow variant
        self.ui.discardButton.setStyleSheet("background-color: #8f0808;")

    def label_selected(self):
        """
        Label selected localizations. Uses the concept & part from the respective combo boxes. If the part is empty, "self" is used.
        """
        if not self.loaded:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Loaded",
                "No results are loaded, so labels cannot be applied.",
            )
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

        if concept not in get_kb_concepts():
            QtWidgets.QMessageBox.critical(
                self, "Bad Concept", f'Bad concept "{concept}".'
            )
            return
        if part not in get_kb_parts() and part != "self":
            QtWidgets.QMessageBox.critical(self, "Bad Part", f'Bad part "{part}".')
            return

        # Remap concept name
        try:
            remapped_concept = get_kb_name(concept)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f'Could not get KB name for concept "{concept}": {e}'
            )
            return

        if remapped_concept != concept:  # show dialog if remapped
            QtWidgets.QMessageBox.information(
                self,
                "Remapped name",
                f"Remapped concept from '{concept}' to '{remapped_concept}'.",
            )

        to_label = self.image_mosaic.get_selected()
        if len(to_label) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Label",
                "Label {} localizations as {}?".format(
                    len(to_label),
                    f"'{remapped_concept}'"
                    + (f" with part '{part}'" if part != "self" else ""),
                ),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            # Apply labels to all selected localizations, push to VARS
            self.image_mosaic.label_selected(remapped_concept, part)

            # Update the label of the selected localization in the image view (if necessary)
            self.box_handler.update_labels()

            # Render the mosaic
            self.image_mosaic.render_mosaic()

    def verify_selected(self):
        """
        Verify the selected localizations.
        """
        to_verify = self.image_mosaic.get_selected()
        if len(to_verify) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Verification",
                "Verify {} localizations?".format(len(to_verify)),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self.image_mosaic.verify_selected()

            self.image_mosaic.render_mosaic()

    def unverify_selected(self):
        """
        Unverify the selected localizations.
        """
        to_unverify = self.image_mosaic.get_selected()
        if len(to_unverify) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Unverification",
                "Unverify {} localizations?".format(len(to_unverify)),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self.image_mosaic.unverify_selected()

            self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot()
    def mark_training_selected(self) -> None:
        """
        Mark the selected localizations for training.
        """
        to_mark = self.image_mosaic.get_selected()
        if len(to_mark) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Mark Training",
                "Mark {} localizations for training?".format(len(to_mark)),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self.image_mosaic.mark_training_selected()

            self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot()
    def unmark_training_selected(self) -> None:
        """
        Unmark the selected localizations for training.
        """
        to_unmark = self.image_mosaic.get_selected()
        if len(to_unmark) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Unmark Training",
                "Unmark {} localizations for training?".format(len(to_unmark)),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self.image_mosaic.unmark_training_selected()

            self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot()
    def delete(self):
        if not self.loaded:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Loaded",
                "No results are loaded, so deletions cannot be performed.",
            )
            return

        to_delete = self.image_mosaic.get_selected()
        opt = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            "Delete {} localizations?\nThis operation cannot be undone.".format(
                len(to_delete)
            ),
            defaultButton=QtWidgets.QMessageBox.StandardButton.No,
        )
        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self.image_mosaic.delete_selected()
            self.box_handler.roi_detail.clear()
            self.box_handler.clear()
            self.ui.boundingBoxInfoTree.clear()
            self.ui.imageInfoTree.clear()

            self.image_mosaic.render_mosaic()

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
        if embeddings_enabled:
            from vars_gridview.lib.embedding import DreamSimEmbedding

            if self._embedding_model is None:
                try:
                    self._embedding_model = DreamSimEmbedding()
                except Exception as e:
                    LOGGER.error(f"Could not create embedding model: {e}")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error",
                        f"Could not create embedding model: {e}",
                    )
                    return
            if self.image_mosaic is not None:
                self.image_mosaic.update_embedding_model(self._embedding_model)

    @QtCore.pyqtSlot(object, object)
    def rect_clicked(self, rect: RectWidget, event: Optional[QtGui.QMouseEvent]):
        if not self.loaded:
            return

        # Get modifier (ctrl, shift) states
        if event is not None:
            ctrl = event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
            shift = event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        else:
            ctrl = False
            shift = False

        # Save information to VARS for any moved/resized boxes
        try:
            self.box_handler.save_all()
        except Exception as e:
            LOGGER.error(f"Could not save localizations: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Error", f"An error occurred while saving localizations: {e}"
            )
            return

        # Select the widget
        if shift:
            self.image_mosaic.select_range(self.last_selected_rect, rect)
        elif ctrl and rect.is_selected:
            self.image_mosaic.deselect(rect)
        else:
            self.image_mosaic.select(rect, clear=not ctrl)

        # Remove highlight from the last selected ROI
        if self.last_selected_rect is not None:
            self.box_handler.clear()
            self.last_selected_rect.is_last_selected = False
            self.last_selected_rect.update()

        # Check if the roiGraphicsView is minimized
        image_view_minimized = (
            self.ui.roiDetailGraphicsView.width() == 0
            or self.ui.roiDetailGraphicsView.height() == 0
        )

        # Check if new rect image is different than last rect image
        rect_image = rect.get_image()
        last_rect_image = (
            self.last_selected_rect.get_image() if self.last_selected_rect else None
        )
        same_image = rect_image is last_rect_image
        needs_autorange = not (same_image or image_view_minimized)

        # Update the last selection
        rect.is_last_selected = True
        rect.update()
        self.last_selected_rect = rect

        # Update the image and add the boxes (only if the roiGraphicsView isn't minimized by the splitter)
        if not image_view_minimized:
            rect_full_image = rect.get_full_image()
            if rect_full_image is None:
                return
            self.box_handler.roi_detail.setImage(
                cv2.cvtColor(rect_full_image, cv2.COLOR_BGR2RGB)
            )
            if needs_autorange:
                self.box_handler.view_box.autoRange()
            self.box_handler.add_annotation(rect.localization_index, rect)

        # Add localization data to the panel
        self.ui.boundingBoxInfoTree.set_data(rect.association.data)

        # Add ancillary data to the image info list
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

    @QtCore.pyqtSlot()
    def open_video(self):
        """
        Open the video of the last selected ROI, if available
        """
        if not self.last_selected_rect:
            QtWidgets.QMessageBox.warning(self, "No ROI Selected", "No ROI selected.")
            return

        selected_rect = self.last_selected_rect

        # Get the annotation imaged moment UUID
        imaged_moment_uuid = selected_rect.imaged_moment_uuid

        # Get the annotation MP4 video data
        mp4_video_data = self.image_mosaic.moment_mp4_data.get(imaged_moment_uuid, None)
        if mp4_video_data is None:
            QtWidgets.QMessageBox.warning(self, "Missing Video", "ROI lacks MP4 video.")
            return

        mp4_video = mp4_video_data["video"]
        mp4_video_reference = mp4_video_data["video_reference"]

        mp4_video_url = mp4_video_reference.get("uri", None)
        mp4_start_timestamp = parse_date(mp4_video["start_timestamp"])

        # Get the annotation timestamp
        annotation_datetime = self.image_mosaic.moment_timestamps[imaged_moment_uuid]

        # Compute the timedelta between the annotation and video start
        annotation_timedelta = annotation_datetime - mp4_start_timestamp

        if not self.sharktopoda_connected:
            # Open the MP4 video at the computed timedelta (in seconds)
            annotation_seconds = max(annotation_timedelta.total_seconds(), 0)
            url = mp4_video_url + "#t={},{}".format(
                annotation_seconds, annotation_seconds + 1e-3
            )  # "pause" at the annotation
            webbrowser.open(url)
            return

        # Open the video in Sharktopoda 2
        annotation_milliseconds = max(annotation_timedelta.total_seconds() * 1000, 0)
        video_reference_uuid = UUID(mp4_video_reference["uuid"])

        mp4_width = mp4_video_reference.get("width", None)
        mp4_height = mp4_video_reference.get("height", None)

        if mp4_width is None or mp4_height is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Bad MP4 Metadata",
                "MP4 video metadata is missing width or height.",
            )
            return
        elif mp4_width == 0 or mp4_height == 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Bad MP4 Metadata",
                f"MP4 video metadata has resolution: {mp4_width}x{mp4_height}.",
            )
            return

        image_width = selected_rect.image_width
        image_height = selected_rect.image_height
        if image_width is None or image_height is None:
            QtWidgets.QMessageBox.critical(
                self,
                "Could not get image size",
                "Could not load the image for the annotation, so rescaling cannot be assessed.",
            )
            return

        rescale_x = mp4_width / image_width
        rescale_y = mp4_height / image_height

        # Show warning if rescale dimensions are different
        if abs(rescale_x / rescale_y - 1) > 0.01:  # 1% tolerance
            QtWidgets.QMessageBox.warning(
                self,
                "Different MP4 Aspect Ratio",
                "MP4 video has different aspect ratio than ROI source image. The bounding box may not be displayed correctly.",
            )

        # Collect localizations for all rects that are on the same video
        localizations = []
        for rect in self.image_mosaic._rect_widgets:
            imaged_moment_uuid_other = rect.imaged_moment_uuid
            mp4_video_data_other = self.image_mosaic.moment_mp4_data.get(
                imaged_moment_uuid_other, None
            )
            if mp4_video_data_other is None:
                continue
            mp4_video_reference_other = mp4_video_data_other["video_reference"]
            video_reference_uuid_other = UUID(mp4_video_reference_other["uuid"])
            if video_reference_uuid_other != video_reference_uuid:
                continue

            # Get the annotation timestamp
            annotation_datetime_other = self.image_mosaic.moment_timestamps[
                imaged_moment_uuid_other
            ]

            # Compute the timedelta between the annotation and video start
            annotation_timedelta_other = annotation_datetime_other - mp4_start_timestamp

            annotation_milliseconds_other = max(
                annotation_timedelta_other.total_seconds() * 1000, 0
            )

            localization = Localization(
                uuid=uuid4(),
                concept=rect.association.concept,
                elapsed_time_millis=annotation_milliseconds_other,
                x=rescale_x * rect.association.x,
                y=rescale_y * rect.association.y,
                width=rescale_x * rect.association.width,
                height=rescale_y * rect.association.height,
                duration_millis=1000,
                color=color_for_concept(rect.association.concept).name(),
            )

            localizations.append(localization)

        def show_localizations():
            sleep(
                0.5
            )  # A hack, since Sharktopoda 2 crashes if you send it a command too soon
            self.sharktopoda_client.seek_elapsed_time(
                video_reference_uuid, annotation_milliseconds
            )
            self.sharktopoda_client.clear_localizations(video_reference_uuid)

            # Add localizations in chunks
            chunk_size = 20
            for i in range(0, len(localizations), chunk_size):
                chunk = localizations[i : i + chunk_size]

                self.sharktopoda_client.add_localizations(video_reference_uuid, chunk)

            self.sharktopoda_client.show(video_reference_uuid)

            # If on macOS, call the open command to bring Sharktopoda to the front
            if sys.platform == "darwin":
                try:
                    os.system(f"open -a {SHARKTOPODA_APP_NAME}")
                except Exception as e:
                    LOGGER.warning(f"Could not open Sharktopoda: {e}")

        self.sharktopoda_client.open(
            video_reference_uuid, mp4_video_url, callback=show_localizations
        )

    @QtCore.pyqtSlot()
    def _style_gui(self):
        """
        Set the GUI stylesheet.
        """
        # setup stylesheet
        # set the environment variable to use a specific wrapper
        # it can be set to PyQt, PyQt5, PyQt6 PySide or PySide2 (not implemented yet)
        if self.ui.styleComboBox.currentText().lower() == "darkstyle":
            os.environ["PYQTGRAPH_QT_LIB"] = "PyQt6"
            self._app.setStyleSheet(
                qdarkstyle.load_stylesheet(qt_api=os.environ["PYQTGRAPH_QT_LIB"])
            )
        elif self.ui.styleComboBox.currentText().lower() == "darkbreeze":
            file = QtCore.QFile(str(STYLE_DIR / "dark.qss"))
            file.open(
                QtCore.QFile.OpenModeFlag.ReadOnly | QtCore.QFile.OpenModeFlag.Text
            )
            stream = QtCore.QTextStream(file)
            self._app.setStyleSheet(stream.readAll())
        elif self.ui.styleComboBox.currentText().lower() == "default":
            self._app.setStyleSheet("")

    def closeEvent(self, event):
        self._save_gui()
        if self.loaded:
            self.box_handler.save_all()
        QtWidgets.QMainWindow.closeEvent(self, event)

    def run_query(self) -> Optional[Tuple[dict, int, int]]:
        """
        Show the query dialog and return the constraints dictionary, limit, and offset.

        Returns:
            Optional[Tuple[dict, int, int]]: A tuple containing the constraints dictionary, limit, and offset. None if the dialog was cancelled.
        """
        dialog = QueryDialog(parent=self)
        ok = dialog.exec()
        return (dialog.constraints_dict(), dialog.limit, dialog.offset) if ok else None
