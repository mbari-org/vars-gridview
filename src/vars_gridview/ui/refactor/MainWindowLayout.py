"""Programmatic MainWindow layout replacing Designer-based gridview.ui loading."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.ui.JSONTree import JSONTree
from vars_gridview.ui.style import UiGeometry, UiTypography, control_font


class MainWindowLayout:
    """Build the MainWindow widget tree in code while preserving widget names."""

    def setupUi(self, main_window: QtWidgets.QMainWindow) -> None:
        main_window.setObjectName("MainWindow")
        main_window.resize(UiGeometry.WINDOW_WIDTH, UiGeometry.WINDOW_HEIGHT)

        base_font = QtGui.QFont()
        base_font.setPointSize(UiTypography.BASE_POINT_SIZE)
        main_window.setFont(base_font)

        self.centralwidget = QtWidgets.QWidget(main_window)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")

        self.splitter2 = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter2.setObjectName("splitter2")

        left_panel = QtWidgets.QWidget(self.splitter2)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setObjectName("verticalLayout_3")

        self.roiGraphicsView = QtWidgets.QGraphicsView(left_panel)
        self.roiGraphicsView.setObjectName("roiGraphicsView")
        self.roiGraphicsView.setMinimumSize(
            QtCore.QSize(UiGeometry.ROI_GRAPHICS_MIN_WIDTH, 0)
        )
        left_layout.addWidget(self.roiGraphicsView)

        self.statusInfoContainer = QtWidgets.QWidget(left_panel)
        self.statusInfoContainer.setObjectName("statusInfoContainer")
        self.statusInfoLayout = QtWidgets.QVBoxLayout(self.statusInfoContainer)
        self.statusInfoLayout.setObjectName("statusInfoLayout")
        self.statusInfoLayout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.statusInfoContainer)

        self.splitter1 = QtWidgets.QSplitter(self.splitter2)
        self.splitter1.setObjectName("splitter1")
        self.splitter1.setOrientation(QtCore.Qt.Orientation.Vertical)

        self.roiDetailGraphicsView = pg.GraphicsView(self.splitter1)
        self.roiDetailGraphicsView.setObjectName("roiDetailGraphicsView")
        self.roiDetailGraphicsView.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        info_panel = QtWidgets.QWidget(self.splitter1)
        info_panel.setObjectName("infoPanel")
        info_layout = QtWidgets.QVBoxLayout(info_panel)
        info_layout.setObjectName("verticalLayout_2")

        info_splitter = QtWidgets.QSplitter(info_panel)
        info_splitter.setObjectName("splitter")
        info_splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)

        info_font = QtGui.QFont()
        info_font.setPointSize(UiTypography.INFO_PANEL_POINT_SIZE)

        self.boundingBoxInfoTree = JSONTree(parent=info_splitter)
        self.boundingBoxInfoTree.setObjectName("boundingBoxInfoTree")
        self.boundingBoxInfoTree.setFont(info_font)

        self.imageInfoTree = JSONTree(parent=info_splitter)
        self.imageInfoTree.setObjectName("imageInfoTree")
        self.imageInfoTree.setFont(info_font)

        info_layout.addWidget(info_splitter)

        self.verticalLayout.addWidget(self.splitter2)

        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        controls_font = control_font()

        self.quitButton = QtWidgets.QPushButton(self.centralwidget)
        self.quitButton.setObjectName("quitButton")
        self.quitButton.setFont(controls_font)
        self.quitButton.setText("QUIT")
        self.horizontalLayout_2.addWidget(self.quitButton)

        zoom_label = QtWidgets.QLabel(self.centralwidget)
        zoom_label.setObjectName("Zoom")
        zoom_label.setFont(controls_font)
        zoom_label.setText("Zoom")
        zoom_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.horizontalLayout_2.addWidget(zoom_label)

        self.zoomSpinBox = QtWidgets.QSpinBox(self.centralwidget)
        self.zoomSpinBox.setObjectName("zoomSpinBox")
        self.zoomSpinBox.setFont(controls_font)
        self.zoomSpinBox.setMaximumSize(
            QtCore.QSize(UiGeometry.ZOOM_SPINBOX_MAX_WIDTH, 16777215)
        )
        self.zoomSpinBox.setRange(UiGeometry.ZOOM_MIN, UiGeometry.ZOOM_MAX)
        self.zoomSpinBox.setSingleStep(UiGeometry.ZOOM_STEP)
        self.zoomSpinBox.setValue(UiGeometry.ZOOM_DEFAULT)
        self.horizontalLayout_2.addWidget(self.zoomSpinBox)

        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.labeledCheckboxesLayout = QtWidgets.QVBoxLayout()
        self.labeledCheckboxesLayout.setObjectName("labeledCheckboxesLayout")
        self.hideLabeled = QtWidgets.QCheckBox(self.centralwidget)
        self.hideLabeled.setObjectName("hideLabeled")
        self.hideLabeled.setFont(controls_font)
        self.hideLabeled.setText("Hide Verified")
        self.labeledCheckboxesLayout.addWidget(self.hideLabeled)
        self.hideUnlabeled = QtWidgets.QCheckBox(self.centralwidget)
        self.hideUnlabeled.setObjectName("hideUnlabeled")
        self.hideUnlabeled.setFont(controls_font)
        self.hideUnlabeled.setText("Hide Unverified")
        self.labeledCheckboxesLayout.addWidget(self.hideUnlabeled)
        self.horizontalLayout.addLayout(self.labeledCheckboxesLayout)

        self.trainingCheckboxesLayout = QtWidgets.QVBoxLayout()
        self.trainingCheckboxesLayout.setObjectName("trainingCheckboxesLayout")
        self.hideTraining = QtWidgets.QCheckBox(self.centralwidget)
        self.hideTraining.setObjectName("hideTraining")
        self.hideTraining.setFont(controls_font)
        self.hideTraining.setText("Hide Training")
        self.trainingCheckboxesLayout.addWidget(self.hideTraining)
        self.hideNontraining = QtWidgets.QCheckBox(self.centralwidget)
        self.hideNontraining.setObjectName("hideNontraining")
        self.hideNontraining.setFont(controls_font)
        self.hideNontraining.setText("Hide Non-training")
        self.trainingCheckboxesLayout.addWidget(self.hideNontraining)
        self.horizontalLayout.addLayout(self.trainingCheckboxesLayout)

        self.sortButton = QtWidgets.QPushButton(self.centralwidget)
        self.sortButton.setObjectName("sortButton")
        self.sortButton.setFont(controls_font)
        self.sortButton.setText("SORT")
        self.horizontalLayout.addWidget(self.sortButton)

        self.openVideo = QtWidgets.QPushButton(self.centralwidget)
        self.openVideo.setObjectName("openVideo")
        self.openVideo.setFont(controls_font)
        self.openVideo.setToolTip(
            "Open the relevant video in a web browser, if available (Ctrl-V)"
        )
        self.openVideo.setText("OPEN VIDEO")
        self.openVideo.setShortcut("Ctrl+V")
        self.horizontalLayout.addWidget(self.openVideo)

        self.verificationButtonsLayout = QtWidgets.QVBoxLayout()
        self.verificationButtonsLayout.setObjectName("verificationButtonsLayout")
        self.verifySelectedButton = QtWidgets.QPushButton(self.centralwidget)
        self.verifySelectedButton.setObjectName("verifySelectedButton")
        self.verifySelectedButton.setFont(controls_font)
        self.verifySelectedButton.setToolTip("Verify selected localizations")
        self.verifySelectedButton.setText("VERIFY")
        self.verificationButtonsLayout.addWidget(self.verifySelectedButton)
        self.unverifySelectedButton = QtWidgets.QPushButton(self.centralwidget)
        self.unverifySelectedButton.setObjectName("unverifySelectedButton")
        self.unverifySelectedButton.setFont(controls_font)
        self.unverifySelectedButton.setToolTip("Unverify selected localizations")
        self.unverifySelectedButton.setText("UNVERIFY")
        self.verificationButtonsLayout.addWidget(self.unverifySelectedButton)
        self.horizontalLayout.addLayout(self.verificationButtonsLayout)

        self.markTrainingButtonsLayout = QtWidgets.QVBoxLayout()
        self.markTrainingButtonsLayout.setObjectName("markTrainingButtonsLayout")
        self.markTrainingSelectedButton = QtWidgets.QPushButton(self.centralwidget)
        self.markTrainingSelectedButton.setObjectName("markTrainingSelectedButton")
        self.markTrainingSelectedButton.setFont(controls_font)
        self.markTrainingSelectedButton.setToolTip(
            "Mark selected localizations for training"
        )
        self.markTrainingSelectedButton.setText("MARK TRAINING")
        self.markTrainingButtonsLayout.addWidget(self.markTrainingSelectedButton)
        self.unmarkTrainingSelectedButton = QtWidgets.QPushButton(self.centralwidget)
        self.unmarkTrainingSelectedButton.setObjectName("unmarkTrainingSelectedButton")
        self.unmarkTrainingSelectedButton.setFont(controls_font)
        self.unmarkTrainingSelectedButton.setToolTip(
            "Unmark selected localizations for training"
        )
        self.unmarkTrainingSelectedButton.setText("UNMARK TRAINING")
        self.markTrainingButtonsLayout.addWidget(self.unmarkTrainingSelectedButton)
        self.horizontalLayout.addLayout(self.markTrainingButtonsLayout)

        self.horizontalLayout_2.addLayout(self.horizontalLayout)

        spacer = QtWidgets.QSpacerItem(
            200,
            20,
            QtWidgets.QSizePolicy.Policy.Maximum,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout_2.addItem(spacer)

        class_label = QtWidgets.QLabel(self.centralwidget)
        class_label.setObjectName("label")
        class_label.setFont(controls_font)
        class_label.setText("Class Label")
        class_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.horizontalLayout_2.addWidget(class_label)

        self.labelComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.labelComboBox.setObjectName("labelComboBox")
        self.labelComboBox.setFont(controls_font)
        self.labelComboBox.setToolTip("The concept label to apply to annotations")
        self.labelComboBox.setEditable(True)
        self.horizontalLayout_2.addWidget(self.labelComboBox)

        self.partComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.partComboBox.setObjectName("partComboBox")
        self.partComboBox.setFont(controls_font)
        self.partComboBox.setToolTip("The part label to apply to annotations")
        self.partComboBox.setEditable(True)
        self.horizontalLayout_2.addWidget(self.partComboBox)

        self.labelSelectedButton = QtWidgets.QPushButton(self.centralwidget)
        self.labelSelectedButton.setObjectName("labelSelectedButton")
        self.labelSelectedButton.setFont(controls_font)
        self.labelSelectedButton.setToolTip(
            "Apply concept and part labels to selected localizations"
        )
        self.labelSelectedButton.setText("LABEL")
        self.horizontalLayout_2.addWidget(self.labelSelectedButton)

        self.clearSelections = QtWidgets.QPushButton(self.centralwidget)
        self.clearSelections.setObjectName("clearSelections")
        self.clearSelections.setFont(controls_font)
        self.clearSelections.setToolTip("Clear all current selections")
        self.clearSelections.setText("CLEAR SELECTIONS")
        self.clearSelections.setShortcut("Ctrl+C")
        self.horizontalLayout_2.addWidget(self.clearSelections)

        self.discardButton = QtWidgets.QPushButton(self.centralwidget)
        self.discardButton.setObjectName("discardButton")
        self.discardButton.setFont(controls_font)
        self.discardButton.setToolTip("Delete selected localizations")
        self.discardButton.setText("DELETE")
        self.horizontalLayout_2.addWidget(self.discardButton)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        main_window.setCentralWidget(self.centralwidget)

        self.menuBar = QtWidgets.QMenuBar(main_window)
        self.menuBar.setObjectName("menuBar")
        self.menuBar.setGeometry(
            QtCore.QRect(0, 0, UiGeometry.WINDOW_WIDTH, UiGeometry.MENU_BAR_HEIGHT)
        )
        main_window.setMenuBar(self.menuBar)

        self.quitButton.pressed.connect(main_window.close)
