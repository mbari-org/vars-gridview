# -*- coding: utf-8 -*-
"""
gridview.py -- A small python app to display ROIs and edit labels driven by FathomNet annotations
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

The app loads images from a directory and then sorts them by label, time, or height. Based on the max
image size and the scree width, it divides the layout into columns and rows and then
fills these with RectWidgets. Each rect widget controls an ROI and annotation and
new annotations can be applied to groups of selected widgets

The app also provides a view similar to rectlabel, where existing annotations can be dragged to adjust and
new annotations can be added.

This was inspired from a PyQt4 GraphicsGridLayout example found here:
http://synapses.awardspace.info/pages-scripts/python/pages/python-pyqt_qgraphicsview-thumbnails-grid.py.html
"""

import argparse
import json
import logging
import os
import sys
import traceback
import webbrowser
from pathlib import Path
from time import sleep
from typing import Optional, Tuple
from uuid import UUID, uuid4

import cv2
import pyqtgraph as pg
import qdarkstyle
from PyQt6 import QtCore, QtGui, QtWidgets
from sharktopoda_client.client import SharktopodaClient
from sharktopoda_client.dto import Localization

from vars_gridview.lib import constants, m3, raziel, sql
from vars_gridview.lib.boxes import BoxHandler
from vars_gridview.lib.image_mosaic import ImageMosaic
from vars_gridview.lib.log import LOGGER, AppLogger
from vars_gridview.lib.m3.operations import get_kb_concepts, get_kb_parts
from vars_gridview.lib.settings import SettingsManager
from vars_gridview.lib.sort_methods import (
    AreaSort,
    AssociationUUIDSort,
    DepthSort,
    HeightSort,
    ImageReferenceUUIDSort,
    LabelSort,
    MeanHueSort,
    MeanIntensitySort,
    ObservationUUIDSort,
    RecordedTimestampSort,
    RegionMeanHueSort,
    WidthSort,
)
from vars_gridview.lib.util import parse_iso
from vars_gridview.lib.widgets import RectWidget
from vars_gridview.ui.LoginDialog import LoginDialog
from vars_gridview.ui.QueryDialog import QueryDialog
from vars_gridview.ui.settings.SettingsDialog import SettingsDialog
from vars_gridview.ui.SortDialog import SortDialog

# Define main window class from template
CWD = Path(__file__).parent
ICONS_DIR = constants.ASSETS_DIR / "icons"
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(constants.UI_FILE)

GUI_SETTINGS = QtCore.QSettings(
    str(constants.GUI_SETTINGS_FILE), QtCore.QSettings.Format.IniFormat
)

ENABLED_SORT_METHODS = [
    RecordedTimestampSort,
    AssociationUUIDSort,
    ObservationUUIDSort,
    ImageReferenceUUIDSort,
    LabelSort,
    WidthSort,
    HeightSort,
    AreaSort,
    MeanIntensitySort,
    MeanHueSort,
    RegionMeanHueSort,
    DepthSort,
]


class MainWindow(TemplateBaseClass):
    """
    Main application window.
    """

    sharktopodaConnected = QtCore.pyqtSignal()

    def __init__(self, app):
        QtWidgets.QMainWindow.__init__(self)
        TemplateBaseClass.__init__(self)

        self._app = app

        # Create the main window
        self.ui = WindowTemplate()
        self.ui.setupUi(self)

        # Set the window title
        self.setWindowTitle(constants.APP_NAME)
        self.setWindowIcon(
            QtGui.QIcon(str(ICONS_DIR / "VARSGridView.iconset" / "icon_256x256.png"))
        )

        # Restore and style GUI
        self._restore_gui()
        self._style_gui()

        self.verifier = None  # The username of the current verifier
        self.endpoints = None  # The list of endpoint data from Raziel

        self.last_selected_rect = None  # Last selected ROI

        self.image_mosaic = (
            None  # Image mosaic (holds the thumbnails as a grid of RectWidgets)
        )
        self.box_handler = None  # Box handler (handles the ROIs and annotations)

        self.cached_moment_concepts = (
            {}
        )  # Cache for imaged moment -> set of observed concepts

        self.sharktopoda_client = None  # Sharktopoda client
        self.sharktopoda_connected = (
            False  # Whether the Sharktopoda client is connected
        )

        # Connect signals to slots
        self.ui.discardButton.clicked.connect(self.delete)
        self.ui.clearSelections.clicked.connect(self.clear_selected)
        self.ui.labelSelectedButton.clicked.connect(self.update_labels)
        self.ui.zoomSpinBox.valueChanged.connect(self.update_zoom)
        # self.ui.sortMethod.currentTextChanged.connect(self.update_layout)
        self.ui.hideLabeled.stateChanged.connect(self.update_layout)
        self.ui.styleComboBox.currentTextChanged.connect(self._style_gui)
        self.ui.openVideo.clicked.connect(self.open_video)
        self.ui.sortButton.clicked.connect(self._sort_widgets)

        self._settings = SettingsManager.get_instance()
        self._settings.label_font_size.valueChanged.connect(self.update_layout)

        self.settings_dialog = SettingsDialog(
            self._setup_sharktopoda_client, self.sharktopodaConnected, parent=self
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
            QtWidgets.QMessageBox.critical(
                self, "Login failed", "Login failed, exiting."
            )
            sys.exit(1)

        # Set up the label combo boxes
        self._setup_label_boxes()

        # Set up the menu bar
        self._setup_menu_bar()

        # Set up Sharktopoda client
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
        if self._settings.raz_url.value != raziel_url:
            LOGGER.debug(f"Updating Raziel URL setting to {raziel_url}")
            self._settings.raz_url.value = raziel_url

        # Authenticate Raziel + get endpoint data
        endpoints = self._auth_raziel(raziel_url, username, password)
        if endpoints is None:  # Authentication failed
            return False

        # Authenticate M3 modules
        ok = self._setup_m3(endpoints)
        if not ok:
            return False

        # Connect to the database
        while True:
            try:
                sql.connect_from_settings()
                break
            except Exception as e:
                LOGGER.error(f"Could not connect to SQL server: {e}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "SQL connection failed",
                    f"Could not connect to the SQL server. Check the database URL and your username and password.\n\n{e}",
                )
                if self.settings_dialog.exec() == QtWidgets.QDialog.DialogCode.Rejected:
                    return False

        # Set the verifier and endpoint data
        self.verifier = username
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

        query_menu = menu_bar.addMenu("&Query")

        query_action = QtGui.QAction("&Query", self)
        query_icon = QtGui.QIcon(str(ICONS_DIR / "magnifying-glass-solid.svg"))
        query_action.setIcon(query_icon)
        query_action.setShortcut("Ctrl+Q")
        query_action.triggered.connect(self._do_query)
        query_menu.addAction(query_action)

        # Create a menu with icons on the left-side of the main window
        toolbar = QtWidgets.QToolBar()
        toolbar.setObjectName("toolbar")
        toolbar.addAction(settings_action)
        toolbar.addAction(query_action)
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
                self._settings.sharktopoda_host.value,
                self._settings.sharktopoda_outgoing_port.value,
                self._settings.sharktopoda_incoming_port.value,
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

    def _open_settings(self):
        """
        Open the settings dialog.
        """
        self.settings_dialog.show()

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

        # Show a sort dialog
        sort_dialog = SortDialog(parent=self)
        ok = sort_dialog.exec()
        if not ok:
            return
        method = sort_dialog.method
        if method is None:
            return

        self.image_mosaic.sort_rect_widgets(method)
        self.image_mosaic.render_mosaic()

    def _do_query(self):
        """
        Perform a query based on the filter string.
        """
        # Show a query dialog
        constraint_dict = self.query()
        if constraint_dict is None:  # User cancelled, do nothing
            return
        else:  # Unload
            self.last_selected_rect = None
            self.image_mosaic = None
            self.box_handler = None

        # Run the query
        query_data, query_headers = sql.query(constraint_dict)

        # Create the image mosaic
        self.image_mosaic = ImageMosaic(
            self.ui.roiGraphicsView,
            query_data,
            query_headers,
            self.rect_clicked,
            self.verifier,
            zoom=self.ui.zoomSpinBox.value() / 100,
        )

        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic._hide_labeled = self.ui.hideLabeled.isChecked()

        default_sort_method = RecordedTimestampSort
        self.image_mosaic.sort_rect_widgets(default_sort_method)
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
            verifier=self.verifier,
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
        concepts = [""] + sorted([c for c in kb_concepts if c != ""])
        self.ui.labelComboBox.addItems(concepts)
        self.ui.labelComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )

        self.ui.partComboBox.clear()
        parts = [""] + sorted([p for p in kb_parts if p != ""])
        self.ui.partComboBox.addItems(parts)
        self.ui.partComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )

    def _restore_gui(self):
        """
        Restore window size and splitter states
        """
        finfo = QtCore.QFileInfo(GUI_SETTINGS.fileName())
        if finfo.exists() and finfo.isFile():
            self.restoreGeometry(GUI_SETTINGS.value("geometry"))
            self.restoreState(GUI_SETTINGS.value("windowState"))
            self.ui.splitter1.restoreState(GUI_SETTINGS.value("splitter1state"))
            self.ui.splitter2.restoreState(GUI_SETTINGS.value("splitter2state"))
            self.ui.styleComboBox.setCurrentText(GUI_SETTINGS.value("style"))

    def _save_gui(self):
        GUI_SETTINGS.setValue("geometry", self.saveGeometry())
        GUI_SETTINGS.setValue("windowState", self.saveState())
        GUI_SETTINGS.setValue("splitter1state", self.ui.splitter1.saveState())
        GUI_SETTINGS.setValue("splitter2state", self.ui.splitter2.saveState())
        GUI_SETTINGS.setValue("style", self.ui.styleComboBox.currentText())

    def update_labels(self):
        if not self.loaded:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Loaded",
                "No results are loaded, so labels cannot be applied.",
            )
            return

        concept = self.ui.labelComboBox.currentText()
        part = self.ui.partComboBox.currentText()

        try:
            kb_concepts = get_kb_concepts()
            kb_parts = get_kb_parts()
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts or parts: {e}")
            return

        if concept not in kb_concepts and concept != "":
            QtWidgets.QMessageBox.critical(
                self, "Bad Concept", f'Bad concept "{concept}". Canceling.'
            )
            return
        if part not in kb_parts and part != "":
            QtWidgets.QMessageBox.critical(
                self, "Bad Part", f'Bad part "{part}". Canceling.'
            )
            return

        to_label = self.image_mosaic.get_selected()
        if len(to_label) > 1:
            opt = QtWidgets.QMessageBox.question(
                self,
                "Confirm Label",
                "Label {} localizations?".format(len(to_label)),
                defaultButton=QtWidgets.QMessageBox.StandardButton.No,
            )
        else:
            opt = QtWidgets.QMessageBox.StandardButton.Yes

        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            # Apply labels to all selected localizations, push to VARS
            self.image_mosaic.apply_label(concept, part)

            # Update the label of the selected localization in the image view (if necessary)
            self.box_handler.update_labels()

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
            self.ui.annotationXML.clear()
            self.ui.imageInfoList.clear()

    @QtCore.pyqtSlot()
    def clear_selected(self):
        if not self.loaded:
            return

        self.image_mosaic.clear_selected()

    @QtCore.pyqtSlot()
    def update_layout(self):
        if not self.loaded:
            return

        # method = self.ui.sortMethod.currentData()
        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic._hide_labeled = self.ui.hideLabeled.isChecked()
        # self.image_mosaic.sort_rect_widgets(method)
        self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot(int)
    def update_zoom(self, zoom):
        if not self.loaded:
            return

        self.image_mosaic.update_zoom(zoom / 100)

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
        self.box_handler.save_all(self.verifier)

        # Select the widget
        if shift:
            self.image_mosaic.select_range(self.last_selected_rect, rect)
        elif ctrl and rect.is_selected:
            self.image_mosaic.deselect(rect)
        else:
            self.image_mosaic.select(rect, clear=not ctrl)

        # Remove highlight from the last selected ROI
        needs_autorange = True
        if self.last_selected_rect is not None:
            self.box_handler.clear()
            self.last_selected_rect.is_last_selected = False
            self.last_selected_rect.update()

            # Check if new rect image is different than last rect image
            needs_autorange = rect.image is not self.last_selected_rect.image

        # Update the last selection
        rect.is_last_selected = True
        rect.update()
        self.last_selected_rect = rect

        # Update the image and add the boxes
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
        self.ui.annotationXML.clear()
        self.ui.annotationXML.insertPlainText(
            json.dumps(rect.localization.json, indent=2)
        )

        # Add ancillary data to the image info list
        self.ui.imageInfoList.clear()
        self.ui.imageInfoList.addItem(
            "Derived timestamp: {}".format(
                rect.annotation_datetime().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        self.ui.imageInfoList.addItem("Observation observer: {}".format(rect.observer))
        self.ui.imageInfoList.addItems(
            [
                "{}: {}".format(key.replace("_", " ").capitalize(), value)
                for key, value in rect.ancillary_data.items()
            ]
        )

    @QtCore.pyqtSlot()
    def open_video(self):
        """
        Open the video of the last selected ROI, if available
        """
        if not self.last_selected_rect:
            QtWidgets.QMessageBox.warning(self, "No ROI Selected", "No ROI selected.")
            return

        rect = self.last_selected_rect

        # Get the annotation imaged moment UUID
        imaged_moment_uuid = rect.imaged_moment_uuid

        # Get the annotation MP4 video data
        mp4_video_data = self.image_mosaic.moment_mp4_data.get(imaged_moment_uuid, None)
        if mp4_video_data is None:
            QtWidgets.QMessageBox.warning(self, "Missing Video", "ROI lacks MP4 video.")
            return

        mp4_video = mp4_video_data["video"]
        mp4_video_reference = mp4_video_data["video_reference"]

        mp4_video_url = mp4_video_reference.get("uri", None)
        mp4_start_timestamp = parse_iso(mp4_video["start_timestamp"])

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

        def color_for_concept(concept: str):
            hash = sum(map(ord, concept)) << 5
            color = QtGui.QColor()
            color.setHsl(round((hash % 360) / 360 * 255), 255, 217, 255)
            return color

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

        rescale_x = mp4_width / rect.image.shape[1]
        rescale_y = mp4_height / rect.image.shape[0]

        # Show warning if rescale dimensions are different
        if abs(rescale_x / rescale_y - 1) > 0.01:  # 1% tolerance
            QtWidgets.QMessageBox.warning(
                self,
                "Different MP4 Aspect Ratio",
                "MP4 video has different aspect ratio than ROI source image. The bounding box may not be displayed correctly.",
            )

        localization = Localization(
            uuid=uuid4(),
            concept=rect.localization.concept,
            elapsed_time_millis=annotation_milliseconds,
            x=rescale_x * rect.localization.x,
            y=rescale_y * rect.localization.y,
            width=rescale_x * rect.localization.width,
            height=rescale_y * rect.localization.height,
            duration_millis=1000,
            color=color_for_concept(rect.localization.concept).name(),
        )

        def show_localization():
            sleep(
                0.5
            )  # A hack, since Sharktopoda 2 crashes if you send it a command too soon
            self.sharktopoda_client.seek_elapsed_time(
                video_reference_uuid, annotation_milliseconds
            )
            self.sharktopoda_client.clear_localizations(video_reference_uuid)
            self.sharktopoda_client.add_localizations(
                video_reference_uuid, [localization]
            )

        self.sharktopoda_client.open(
            video_reference_uuid, mp4_video_url, callback=show_localization
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
            file = QtCore.QFile(str(constants.STYLE_DIR / "dark.qss"))
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
            self.box_handler.save_all(self.verifier)
        QtWidgets.QMainWindow.closeEvent(self, event)

    def query(self) -> Optional[dict]:
        dialog = QueryDialog(parent=self)
        ok = dialog.exec()
        return dialog.constraints_dict() if ok else None


def init_settings():
    """
    Initialize the application settings.
    """
    settings = SettingsManager.get_instance()

    settings.sql_url = ("sql/url", str, constants.SQL_URL_DEFAULT)
    settings.sql_user = ("sql/user", str, constants.SQL_USER_DEFAULT)
    settings.sql_password = ("sql/password", str, constants.SQL_PASSWORD_DEFAULT)
    settings.sql_database = ("sql/database", str, constants.SQL_DATABASE_DEFAULT)

    settings.raz_url = ("m3/raz_url", str, constants.RAZIEL_URL_DEFAULT)

    settings.label_font_size = (
        "appearance/label_font_size",
        int,
        constants.LABEL_FONT_SIZE_DEFAULT,
    )
    settings.selection_highlight_color = (
        "appearance/selection_highlight_color",
        str,
        constants.SELECTION_HIGHLIGHT_COLOR_DEFAULT,
    )

    settings.sharktopoda_host = (
        "video/sharktopoda_host",
        str,
        constants.SHARKTOPODA_HOST_DEFAULT,
    )
    settings.sharktopoda_outgoing_port = (
        "video/sharktopoda_outgoing_port",
        int,
        constants.SHARKTOPODA_OUTGOING_PORT_DEFAULT,
    )
    settings.sharktopoda_incoming_port = (
        "video/sharktopoda_incoming_port",
        int,
        constants.SHARKTOPODA_INCOMING_PORT_DEFAULT,
    )


def parse_args():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description="VARS Gridview")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging to console"
    )
    return parser.parse_args()


def main():
    # Parse command line arguments
    args = parse_args()

    # Set up logging
    if args.verbose:
        AppLogger.get_instance().set_stream_level(logging.DEBUG)

    # Create the Qt application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setOrganizationName(constants.APP_ORGANIZATION)

    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    init_settings()

    # Create the main window and show it
    try:
        main = MainWindow(app)
        main.show()
    except Exception as e:
        LOGGER.critical(f"Could not create main window: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        sys.exit(1)

    # Exit after app is finished
    try:
        status = app.exec()
    except Exception as e:
        LOGGER.critical(f"Fatal exception: {e}")
        LOGGER.debug(traceback.format_exc())  # Log the full traceback
        status = 1

    sys.exit(status)


if __name__ == "__main__":
    main()
