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

import datetime
import json
import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

import cv2
import pyqtgraph as pg
import qdarkstyle
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib import constants, m3, raziel, sql
from vars_gridview.lib.boxes import BoxHandler
from vars_gridview.lib.image_mosaic import ImageMosaic
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.operations import (
    get_kb_concepts,
    get_kb_parts,
    get_vars_imaged_moment,
    get_videos_at_datetime,
)
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
from vars_gridview.lib.widgets import RectWidget
from vars_gridview.ui.LoginDialog import LoginDialog
from vars_gridview.ui.QueryDialog import QueryDialog
from vars_gridview.ui.settings.SettingsDialog import SettingsDialog

# Define main window class from template
CWD = Path(__file__).parent
ASSETS_DIR = CWD.parent / "assets"
UI_FILE_PATH = ASSETS_DIR / "gridview.ui"
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(UI_FILE_PATH)

GUI_SETTINGS = QtCore.QSettings(str(constants.GUI_SETTINGS_FILE), QtCore.QSettings.Format.IniFormat)

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

    def __init__(self, app):
        QtWidgets.QMainWindow.__init__(self)
        TemplateBaseClass.__init__(self)

        self._app = app

        # Create the main window
        self.ui = WindowTemplate()
        self.ui.setupUi(self)

        # Set the window title
        self.setWindowTitle(constants.APP_NAME)

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

        # Connect signals to slots
        self.ui.discardButton.clicked.connect(self.delete)
        self.ui.clearSelections.clicked.connect(self.clear_selected)
        self.ui.labelSelectedButton.clicked.connect(self.update_labels)
        self.ui.zoomSpinBox.valueChanged.connect(self.update_zoom)
        self.ui.sortMethod.currentTextChanged.connect(self.update_layout)
        self.ui.hideLabeled.stateChanged.connect(self.update_layout)
        self.ui.styleComboBox.currentTextChanged.connect(self._style_gui)
        self.ui.openVideo.clicked.connect(self.open_video)

        self.settings_dialog = SettingsDialog(self)

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
            QtWidgets.QMessageBox.critical(self, "Login failed", "Login failed, exiting.")
            sys.exit(1)

        # Set up the label combo boxes
        self._setup_label_boxes()

        # Set up the sort method combo box
        self._setup_sort_methods()

        # Set up the menu bar
        self._setup_menu_bar()

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
        settings = SettingsManager.get_instance()
        if settings.raz_url.value != raziel_url:
            LOGGER.debug(f"Updating Raziel URL setting to {raziel_url}")
            settings.raz_url.value = raziel_url

        # Authenticate Raziel + get endpoint data
        endpoints = self._auth_raziel(raziel_url, username, password)
        if endpoints is None:  # Authentication failed
            return False

        # Authenticate M3 modules
        ok = self._setup_m3(endpoints)
        if not ok:
            return False

        # Connect to the database
        sql.connect_from_settings()

        # Set the verifier and endpoint data
        self.verifier = username
        self.endpoints = endpoints

        return True

    def _auth_raziel(self, raziel_url, username, password) -> Optional[list]:
        """
        Authenticate with Raziel. Return endpoints list on success, None on fail.
        """
        LOGGER.debug(
            f"Attempting to authenticate user {username} with Raziel at {raziel_url}"
        )
        try:
            endpoints = raziel.authenticate(raziel_url, username, password)
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
        LOGGER.debug("Attempting to set up M3")
        try:
            m3.setup_from_endpoint_data(endpoints)
            return True
        except ValueError as e:
            LOGGER.error(f"M3 setup failed: {e}")
            QtWidgets.QMessageBox.critical(self, "M3 setup failed", f"M3 setup failed: {e}")
            return False

    def _setup_menu_bar(self):
        """
        Populate the menu bar with menus and actions.
        """
        menu_bar = self.ui.menuBar

        file_menu = menu_bar.addMenu("&File")

        settings_action = QtGui.QAction("&Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        query_menu = menu_bar.addMenu("&Query")

        query_action = QtGui.QAction("&Query", self)
        query_action.setShortcut("Ctrl+Q")
        query_action.triggered.connect(self._do_query)
        query_menu.addAction(query_action)

    def _open_settings(self):
        """
        Open the settings dialog.
        """
        self.settings_dialog.show()

    def _setup_from_settings(self):
        """
        Propagate the settings to the app.
        """
        m3.setup_from_settings()
        sql.connect_from_settings()

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

        # Grab the beholder info
        beholder_endpoint = next(e for e in self.endpoints if e["name"] == "beholder")
        beholder_url = beholder_endpoint["url"]
        beholder_api_key = beholder_endpoint["secret"]

        # Create the image mosaic
        self.image_mosaic = ImageMosaic(
            self.ui.roiGraphicsView,
            query_data,
            query_headers,
            self.rect_clicked,
            self.verifier,
            beholder_url,
            beholder_api_key,
            zoom=self.ui.zoomSpinBox.value() / 100,
        )

        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic._hide_labeled = self.ui.hideLabeled.isChecked()

        # Render
        sort_method = self.ui.sortMethod.currentData()
        self.image_mosaic.sort_rect_widgets(sort_method)
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
        self.box_handler = BoxHandler(
            self.ui.roiDetailGraphicsView,
            self.image_mosaic,
            all_labels=get_kb_concepts(),
            verifier=self.verifier,
        )

    def _setup_label_boxes(self):
        """
        Populate the label combo boxes
        """
        # Set up the combo boxes
        self.ui.labelComboBox.clear()
        concepts = [""] + sorted([c for c in get_kb_concepts() if c != ""])
        self.ui.labelComboBox.addItems(concepts)
        self.ui.labelComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )

        self.ui.partComboBox.clear()
        parts = [""] + sorted([p for p in get_kb_parts() if p != ""])
        self.ui.partComboBox.addItems(parts)
        self.ui.partComboBox.completer().setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )

    def _setup_sort_methods(self):
        """
        Populate the sort method combo box
        """
        self.ui.sortMethod.clear()
        for method in ENABLED_SORT_METHODS:
            self.ui.sortMethod.addItem(method.NAME, userData=method)

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

    def _save_gui(self):
        GUI_SETTINGS.setValue("geometry", self.saveGeometry())
        GUI_SETTINGS.setValue("windowState", self.saveState())
        GUI_SETTINGS.setValue("splitter1state", self.ui.splitter1.saveState())
        GUI_SETTINGS.setValue("splitter2state", self.ui.splitter2.saveState())

    def update_labels(self):
        concept = self.ui.labelComboBox.currentText()
        part = self.ui.partComboBox.currentText()

        if concept not in get_kb_concepts() and concept != "":
            QtWidgets.QMessageBox.critical(
                self, "Bad Concept", f'Bad concept "{concept}". Canceling.'
            )
            return
        if part not in get_kb_parts() and part != "":
            QtWidgets.QMessageBox.critical(self, "Bad Part", f'Bad part "{part}". Canceling.')
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
            self.ui.varsObservationsLabel.clear()

    @QtCore.pyqtSlot()
    def clear_selected(self):
        if not self.loaded:
            return

        self.image_mosaic.clear_selected()

    @QtCore.pyqtSlot()
    def update_layout(self):
        if not self.loaded:
            return

        method = self.ui.sortMethod.currentData()
        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic._hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.sort_rect_widgets(method)
        self.image_mosaic.render_mosaic()

    @QtCore.pyqtSlot(int)
    def update_zoom(self, zoom):
        if not self.loaded:
            return

        self.image_mosaic.update_zoom(zoom / 100)

    @QtCore.pyqtSlot(object, object)
    def rect_clicked(self, rect: RectWidget, event: QtGui.QMouseEvent):
        if not self.loaded:
            return
        
        # Get modifier (ctrl, shift) states
        ctrl = event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        shift = event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier

        # Save information to VARS for any moved/resized boxes
        self.box_handler.save_all(self.verifier)

        # Select the widget
        if shift:
            self.image_mosaic.select_range(self.last_selected_rect, rect)
        else:
            self.image_mosaic.select(rect, clear=not ctrl)

        # Remove highlight from the last selected ROI
        if self.last_selected_rect is not None:
            self.box_handler.clear()
            self.last_selected_rect.is_last_selected = False
            self.last_selected_rect.update()

        # Update the last selection
        rect.is_last_selected = True
        rect.update()
        self.last_selected_rect = rect

        # Update the image and add the boxes
        rect_full_image = rect.get_full_image()
        if rect_full_image is None:
            return
        self.box_handler.roi_detail.setImage(cv2.cvtColor(rect_full_image, cv2.COLOR_BGR2RGB))
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
        self.ui.imageInfoList.addItems(
            [
                "{}: {}".format(key.replace("_", " ").capitalize(), value)
                for key, value in rect.ancillary_data.items()
            ]
        )

        # Update VARS observations label
        imaged_moment_uuid = rect.localization.imaged_moment_uuid
        if imaged_moment_uuid in self.cached_moment_concepts:  # cache hit
            concepts = self.cached_moment_concepts[imaged_moment_uuid]
        else:  # cache miss
            vars_moment_data = get_vars_imaged_moment(
                rect.localization.imaged_moment_uuid
            )
            concepts = sorted(
                set(obs["concept"] for obs in vars_moment_data["observations"])
            )
            self.cached_moment_concepts[imaged_moment_uuid] = concepts
        observed_concepts_str = ", ".join(concepts)
        self.ui.varsObservationsLabel.setText(observed_concepts_str)

    @QtCore.pyqtSlot()
    def open_video(self):
        """
        Open the video of the last selected ROI, if available
        """
        if not self.last_selected_rect:
            QtWidgets.QMessageBox.warning(self, "No ROI Selected", "No ROI selected.")
            return

        # Get the annotation recorded datetime
        annotation_datetime = self.last_selected_rect.annotation_datetime()
        annotation_platform = self.last_selected_rect.ancillary_data.get(
            "camera_platform", None
        )
        if not annotation_datetime or not annotation_platform:
            QtWidgets.QMessageBox.warning(
                self, "Missing Info", "ROI lacks necessary information to link video."
            )
            return

        # Ask M3 for videos at the given moment
        try:
            videos = get_videos_at_datetime(annotation_datetime)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error Finding Video",
                "An error occurred while finding the video: {}".format(e),
            )
            return

        # Find a matching video URL and timedelta
        video_url = None
        annotation_timedelta = None
        for video in videos:
            if not video["name"].startswith(
                annotation_platform
            ):  # Skip if platform doesn't match
                continue

            video_start_timestamp = video.get("start_timestamp", None)
            if video_start_timestamp is None:  # Skip if no start timestamp in video
                continue

            # Parse video start timestamp into datetime object
            try:
                video_start_datetime = datetime.datetime.strptime(
                    video_start_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except:
                video_start_datetime = datetime.datetime.strptime(
                    video_start_timestamp, "%Y-%m-%dT%H:%M:%SZ"
                )

            # Find a matching video reference (MP4 only)
            video_references = video.get("video_references", [])
            for video_reference in video_references:
                if video_reference["uri"].startswith("http") and video_reference[
                    "uri"
                ].endswith(".mp4"):
                    video_url = video_reference["uri"]
                    annotation_timedelta = annotation_datetime - video_start_datetime
                    break

        # Open the video at the computed time delta (in seconds)
        if video_url is not None:
            annotation_seconds = max(annotation_timedelta.total_seconds(), 0)
            url = video_url + "#t={},{}".format(
                annotation_seconds, annotation_seconds + 1e-3
            )  # "pause" at the annotation
            webbrowser.open(url)
        else:
            QtWidgets.QMessageBox.warning(self, "No Video Found", "No video found for this ROI.")

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
            file = QtCore.QFile(str(ASSETS_DIR / "style" / "dark.qss"))
            file.open(QtCore.QFile.OpenModeFlag.ReadOnly | QtCore.QFile.OpenModeFlag.Text)
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


def main():
    # Create the Qt application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setOrganizationName(constants.APP_ORGANIZATION)

    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    init_settings()

    # Create the main window and show it
    main = MainWindow(app)
    main.show()

    # Exit after app is finished
    status = app.exec()
    sys.exit(status)


if __name__ == "__main__":
    main()
