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

import json
import os
import sys
from typing import Optional

import cv2
import pyqtgraph
import pyqtgraph as pg
import qdarkstyle
from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QDialog, QVBoxLayout, QPushButton, QStyle, QWidget, \
    QHBoxLayout, QDialogButtonBox, QListWidget, QAbstractItemView, QListWidgetItem
from pyqtgraph.Qt import QtCore, QtWidgets

from libs import vars
from libs.image_mosaic import ImageMosaic
from libs.boxes import BoxHandler

# Define main window class from template
path = os.path.dirname(os.path.abspath(__file__))
uiFile = os.path.join(path, 'gridview.ui')
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(uiFile)


class MainWindow(TemplateBaseClass):
    settings = QtCore.QSettings(os.path.join("config", "gui.ini"), QtCore.QSettings.IniFormat)
    sources = QtCore.QSettings(os.path.join("config", "sources.ini"), QtCore.QSettings.IniFormat)

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)

        TemplateBaseClass.__init__(self)
        self.setWindowTitle('GridView (VARS) - Python - Qt')

        # Create the main window
        self.ui = WindowTemplate()
        self.ui.setupUi(self)

        # restore window size and splitters
        self.gui_restore()

        # set the gui style
        self.set_gui_style()

        # get users from VARS
        users = vars.get_all_users()
        self.username_dict = {
            u['username']: {**u} for u in users
        }

        # get login (verifier)
        self.verifier = self.login()

        # response prompt
        if not self.verifier:
            QMessageBox.critical(self, 'Bad Login', 'No login provided.')
            sys.exit(1)
        else:
            QMessageBox.information(self, 'Logged in', f'Logged in: {self.verifier_str}')

        # hold labels to apply to boxes
        self.all_labels = []

        # hold concept parts
        self.all_parts = []

        # load the label & part names from VARS
        self.get_labels()

        # show query dialog
        self.filter_str = self.query_dialog()
        if self.filter_str is None:
            QMessageBox.critical(self, 'Query Canceled', 'Query dialog canceled, exiting.')
            sys.exit(1)
        if self.filter_str == '':
            self.filter_str = '1=1'  # Accept anything (equivalent to no WHERE)

        # generate query
        query_str = vars.make_query(self.filter_str)
        query_data, query_headers = vars.sql_query(query_str)

        # last selected ROI
        self.last_selected_roi = None

        # signals and slots
        # self.ui.needsReviewButton.clicked.connect(self.move_to_review)
        self.ui.discardButton.clicked.connect(self.move_to_discard)
        # self.ui.moveBack.clicked.connect(self.move_back)
        self.ui.clearSelections.clicked.connect(self.clear_selected)
        self.ui.labelSelectedButton.clicked.connect(self.update_labels)
        self.ui.zoomSpinBox.valueChanged.connect(self.update_zoom)
        self.ui.sortMethod.currentTextChanged.connect(self.update_layout)
        self.ui.hideLabeled.stateChanged.connect(self.update_layout)
        # self.ui.hideToReview.stateChanged.connect(self.update_layout)
        # self.ui.hideDiscarded.stateChanged.connect(self.update_layout)
        self.ui.styleComboBox.currentTextChanged.connect(self.set_gui_style)

        # The image mosaic holds all of the thumbnails as a grid of RectWidgets
        self.image_mosaic = ImageMosaic(self.ui.roiGraphicsView, query_data, query_headers, self.rect_click,
                                        self.verifier,
                                        zoom=self.ui.zoomSpinBox.value() / 100)

        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()

        # rendering the mosaic will load images and annotations and populate the mosaic
        self.image_mosaic.render_mosaic()

        # Sow some stats about the images and annotations
        self.statusBar().showMessage('Loaded ' + str(self.image_mosaic.n_images) +
                                     ' images and ' + str(self.image_mosaic.n_localizations) + ' localizations.')

        # create the box handler
        self.box_handler = BoxHandler(self.ui.roiDetailGraphicsView,
                                      self.image_mosaic,
                                      all_labels=self.all_labels,
                                      verifier=self.verifier)

    def get_labels(self):
        # try to get vars concepts
        self.all_labels = vars.pull_all_concepts()

        # Pull VARS parts
        self.all_parts = vars.pull_all_parts()

        # setup the combo boxes
        self.all_labels = sorted(self.all_labels)
        self.ui.labelComboBox.clear()
        self.ui.labelComboBox.addItems(self.all_labels)
        self.ui.labelComboBox.completer().setCompletionMode(QtWidgets.QCompleter.PopupCompletion)

        self.ui.partComboBox.clear()
        self.ui.partComboBox.addItems(self.all_parts)
        self.ui.partComboBox.completer().setCompletionMode(QtWidgets.QCompleter.PopupCompletion)

    def gui_restore(self):
        finfo = QtCore.QFileInfo(self.settings.fileName())
        if finfo.exists() and finfo.isFile():
            self.restoreGeometry(self.settings.value("geometry"))
            self.restoreState(self.settings.value("windowState"))
            self.ui.splitter1.restoreState(self.settings.value("splitter1state"))
            self.ui.splitter2.restoreState(self.settings.value("splitter2state"))

    def gui_save(self):
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('windowState', self.saveState())
        self.settings.setValue('splitter1state', self.ui.splitter1.saveState())
        self.settings.setValue('splitter2state', self.ui.splitter2.saveState())

    def update_labels(self):
        concept = self.ui.labelComboBox.currentText()
        part = self.ui.partComboBox.currentText()

        if concept not in self.all_labels:
            QMessageBox.critical(self, 'Bad Concept', f'Bad concept \"{concept}\". Canceling.')
            return
        if part not in self.all_parts:
            QMessageBox.critical(self, 'Bad Part', f'Bad part \"{part}\". Canceling.')
            return

        # Apply labels to all selected localizations, push to VARS
        self.image_mosaic.apply_label(concept, part)

        # Update the label of the selected localization in the image view (if necessary)
        self.box_handler.update_labels()

    def move_to_discard(self):
        to_delete = [thumb for thumb in self.image_mosaic.thumbs if thumb.isSelected]
        opt = QMessageBox.question(self, 'Confirm Deletion',
                                   'Delete {} localizations?\nThis operation cannot be undone.'.format(len(to_delete)),
                                   defaultButton=QMessageBox.No)
        if opt == QMessageBox.Yes:
            self.image_mosaic.delete_selected()

    def clear_selected(self):
        self.image_mosaic.clear_selected()

    def update_layout(self):
        method = self.ui.sortMethod.currentText()
        self.image_mosaic.hide_discarded = False
        self.image_mosaic.hide_to_review = False
        self.image_mosaic.hide_labeled = self.ui.hideLabeled.isChecked()
        self.image_mosaic.render_mosaic(sort_key=method)

    def update_zoom(self, zoom):
        self.image_mosaic.update_zoom(zoom / 100)

    def rect_click(self, rect):
        # Save information to VARS for any moved/resized boxes
        self.box_handler.save_all(self.verifier)

        # remove highlight from the last selected ROI
        if self.last_selected_roi is not None:
            self.box_handler.clear()
            self.last_selected_roi.isLastSelected = False
            self.last_selected_roi.update()

        # update the new selection
        rect.isLastSelected = True
        rect.update()
        self.last_selected_roi = rect

        full_img = rect.getFullImage()
        if full_img is None:
            print('No image found')
            return

        # Update the image and add the boxes
        self.box_handler.roiDetail.setImage(cv2.cvtColor(full_img, cv2.COLOR_BGR2RGB))
        self.box_handler.add_annotation(rect.index, rect)

        # Add localization data to the panel
        self.ui.annotationXML.clear()
        self.ui.annotationXML.insertPlainText(json.dumps(rect.localization.json, indent=2))

    def closeEvent(self, event):
        self.gui_save()
        self.box_handler.save_all(self.verifier)
        QtWidgets.QMainWindow.closeEvent(self, event)

    def set_gui_style(self):
        # setup stylesheet
        # set the environment variable to use a specific wrapper
        # it can be set to PyQt, PyQt5, PySide or PySide2 (not implemented yet)
        if self.ui.styleComboBox.currentText().lower() == 'darkstyle':
            os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'
            app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api=os.environ['PYQTGRAPH_QT_LIB']))
        elif self.ui.styleComboBox.currentText().lower() == 'darkbreeze':
            file = QtCore.QFile("style/dark.qss")
            file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text)
            stream = QtCore.QTextStream(file)
            app.setStyleSheet(stream.readAll())
        elif self.ui.styleComboBox.currentText().lower() == 'default':
            app.setStyleSheet("")

    def login(self) -> Optional[str]:
        usernames = list(sorted(self.username_dict.keys()))

        username, ok = QInputDialog.getItem(self, 'Login', 'Username', usernames)
        if username not in usernames:
            ok = False
            QMessageBox.critical(self, 'Login error', f'Invalid username "{username}"')

        if not ok:
            username = None

        return username

    @property
    def verifier_str(self) -> str:
        v_str = self.verifier
        u = self.username_dict[self.verifier]
        if 'firstName' in u:
            firstname = u['firstName']
            if firstname:
                v_str = firstname
                if 'lastName' in u:
                    lastname = u['lastName']
                    if lastname:
                        v_str += f' {lastname}'
                v_str += f' ({self.verifier})'
        return v_str

    def query_dialog(self):
        dialog = QueryDialog(parent=self)
        ok = dialog.exec_()
        return dialog.filter_str if ok else None


class QueryDialog(QDialog):
    FILTER_TYPES = [
        'Concept',
        'Concept + descendants',
        'Dive Number',
        'Chief Scientist',
        'Platform',
        'Observer',
        'Imaged Moment UUID',
        'Observation UUID',
        'Association UUID',
        'Image Reference UUID',
        'Video Reference UUID'
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Localization Query')
        self.setLayout(QVBoxLayout())

        # Button bar (add, remove, clear filters)
        self.add_filter_button = QPushButton('Add Filter')
        self.add_filter_button.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
        self.remove_filter_button = QPushButton('Remove Selected')
        self.remove_filter_button.setIcon(self.style().standardIcon(QStyle.SP_DialogNoButton))
        self.clear_filters_button = QPushButton('Clear Filters')
        self.clear_filters_button.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))

        self.button_bar = QWidget()
        self.button_bar.setLayout(QHBoxLayout())
        self.button_bar.layout().addWidget(self.add_filter_button)
        self.button_bar.layout().addWidget(self.remove_filter_button)
        self.button_bar.layout().addWidget(self.clear_filters_button)

        self.layout().addWidget(self.button_bar)

        # Filters list
        self.filters = []

        # Filters ListWidget
        self.filters_widget = QListWidget()
        self.filters_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.layout().addWidget(self.filters_widget)

        self.add_filter_button.pressed.connect(self.add_filter)
        self.remove_filter_button.pressed.connect(self.remove_selected_filters)
        self.clear_filters_button.pressed.connect(self.filters_widget.clear)

        # Dialog button box (just Ok button)
        self.dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        self.dialog_buttons.accepted.connect(self.accept)
        self.layout().addWidget(self.dialog_buttons)

    def add_filter_item(self, data, text: str):
        item = QListWidgetItem(self.filters_widget)
        item.setData(Qt.UserRole, data)
        item.setText(text)

    def add_filter(self):
        # Real janky
        filter_type, ok = QInputDialog.getItem(self, 'Filter Type', 'Filter type',
                                               QueryDialog.FILTER_TYPES, editable=False)

        if not ok:
            return None

        if filter_type == 'Concept':
            concept, ok = QInputDialog.getItem(self, 'Select a Concept', 'Concept', self.parent().all_labels)
            if ok and concept in self.parent().all_labels:
                data = {
                    'key': 'concept',
                    'quant': 'AND',
                    'items': [concept]
                }
                text = f'Concept = \'{concept}\''
                self.add_filter_item(data, text)

        elif filter_type == 'Concept + descendants':
            concept, ok = QInputDialog.getItem(self, 'Select a Concept', 'Concept', self.parent().all_labels)
            if ok and concept in self.parent().all_labels:
                items = [concept] + sorted(list(vars.get_concept_descendants(concept)))
                data = {
                    'key': 'concept',
                    'quant': 'OR',
                    'items': items
                }
                text = 'Concept in {' + ', '.join(items) + '}'
                self.add_filter_item(data, text)

        elif filter_type == 'Dive Number':
            dive_number, ok = QInputDialog.getText(self, 'Specify a Dive Number', 'Dive Number')
            if ok:
                data = {
                    'key': 'dive_number',
                    'quant': 'AND',
                    'items': [dive_number]
                }
                text = f'Dive Number = {dive_number}'
                self.add_filter_item(data, text)

        elif filter_type == 'Chief Scientist':
            chief_scientist, ok = QInputDialog.getText(self, 'Specify a Chief Scientist', 'Chief Scientist')
            if ok:
                data = {
                    'key': 'chief_scientist',
                    'quant': 'AND',
                    'items': [chief_scientist]
                }
                text = f'Chief Scientist = {chief_scientist}'
                self.add_filter_item(data, text)

        elif filter_type == 'Platform':
            platform, ok = QInputDialog.getText(self, 'Specify a Platform', 'Platform')
            if ok:
                data = {
                    'key': 'camera_platform',
                    'quant': 'AND',
                    'items': [platform]
                }
                text = f'Platform = {platform}'
                self.add_filter_item(data, text)

        elif filter_type == 'Observer':
            observer, ok = QInputDialog.getItem(self, 'Select an Observer', 'Observer',
                                                list(self.parent().username_dict.keys()))
            if ok:
                data = {
                    'key': 'observer',
                    'quant': 'AND',
                    'items': [observer]
                }
                text = f'Observer = {observer}'
                self.add_filter_item(data, text)

        elif filter_type == 'Imaged Moment UUID':
            imaged_moment_uuid, ok = QInputDialog.getText(self, 'Specify an Imaged Moment UUID', 'Imaged Moment UUID')
            if ok:
                data = {
                    'key': 'imaged_moment_uuid',
                    'quant': 'AND',
                    'items': [imaged_moment_uuid]
                }
                text = f'Imaged Moment UUID = {imaged_moment_uuid}'
                self.add_filter_item(data, text)

        elif filter_type == 'Observation UUID':
            observation_uuid, ok = QInputDialog.getText(self, 'Specify an Observation UUID', 'Observation UUID')
            if ok:
                data = {
                    'key': 'anno.observation_uuid',
                    'quant': 'AND',
                    'items': [observation_uuid]
                }
                text = f'Observation UUID = {observation_uuid}'
                self.add_filter_item(data, text)

        elif filter_type == 'Association UUID':
            association_uuid, ok = QInputDialog.getText(self, 'Specify an Association UUID',
                                                        'Association UUID')
            if ok:
                data = {
                    'key': 'assoc.association_uuid',
                    'quant': 'AND',
                    'items': [association_uuid]
                }
                text = f'Association UUID = {association_uuid}'
                self.add_filter_item(data, text)

        elif filter_type == 'Image Reference UUID':
            image_reference_uuid, ok = QInputDialog.getText(self, 'Specify an Image Reference UUID',
                                                            'Image Reference UUID')
            if ok:
                data = {
                    'key': 'image_reference_uuid',
                    'quant': 'AND',
                    'items': [image_reference_uuid]
                }
                text = f'Image Reference UUID = {image_reference_uuid}'
                self.add_filter_item(data, text)

        elif filter_type == 'Video Reference UUID':
            video_reference_uuid, ok = QInputDialog.getText(self, 'Specify a Video Reference UUID',
                                                            'Video Reference UUID')
            if ok:
                data = {
                    'key': 'video_reference_uuid',
                    'quant': 'AND',
                    'items': [video_reference_uuid]
                }
                text = f'Video Reference UUID = {video_reference_uuid}'
                self.add_filter_item(data, text)

    @property
    def filter_str(self):
        # Even more janky, somehow
        data = (self.filters_widget.item(row).data(Qt.UserRole) for row in range(self.filters_widget.count()))

        filter_strs = []
        for d in data:
            filter_strs.append('(' + f' {d["quant"]} '.join([f'{d["key"]}=\'{item}\'' for item in d['items']]) + ')')

        return ' AND '.join(filter_strs)

    def remove_selected_filters(self):
        for item in self.filters_widget.selectedItems():
            self.filters_widget.takeItem(self.filters_widget.row(item))


if __name__ == "__main__":
    # create the Qt application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GridView (VARS)")

    # create the main window
    # try:
    main = MainWindow()
    main.show()
    # except Exception as e:
    #     print(e)
    #     sys.exit(1)
    # exit the app after the window is closed
    sys.exit(app.exec_())
