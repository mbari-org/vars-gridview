from PyQt6 import QtWidgets

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class VideoPlayerTab(AbstractSettingsTab):
    """
    Video player tab.
    """

    def __init__(self, connect_slot, connected_signal, parent=None):
        super().__init__("Video player", parent=parent)

        self.sharktopoda_autoconnect_checkbox = QtWidgets.QCheckBox()
        self.sharktopoda_autoconnect_checkbox.setChecked(
            SETTINGS.sharktopoda_autoconnect.value
        )
        self.sharktopoda_autoconnect_checkbox.stateChanged.connect(
            self.settingsChanged.emit
        )
        SETTINGS.sharktopoda_autoconnect.valueChanged.connect(
            self.sharktopoda_autoconnect_checkbox.setChecked
        )

        self.sharktopoda_host_edit = QtWidgets.QLineEdit()
        self.sharktopoda_host_edit.setText(SETTINGS.sharktopoda_host.value)
        self.sharktopoda_host_edit.textChanged.connect(self.settingsChanged.emit)
        SETTINGS.sharktopoda_host.valueChanged.connect(
            self.sharktopoda_host_edit.setText
        )

        self.sharktopoda_outgoing_port_edit = QtWidgets.QSpinBox()
        self.sharktopoda_outgoing_port_edit.setMinimum(0)
        self.sharktopoda_outgoing_port_edit.setMaximum(65535)
        self.sharktopoda_outgoing_port_edit.setValue(
            SETTINGS.sharktopoda_outgoing_port.value
        )
        self.sharktopoda_outgoing_port_edit.valueChanged.connect(
            self.settingsChanged.emit
        )
        SETTINGS.sharktopoda_outgoing_port.valueChanged.connect(
            self.sharktopoda_outgoing_port_edit.setValue
        )

        self.sharktopoda_incoming_port_edit = QtWidgets.QSpinBox()
        self.sharktopoda_incoming_port_edit.setMinimum(0)
        self.sharktopoda_incoming_port_edit.setMaximum(65535)
        self.sharktopoda_incoming_port_edit.setValue(
            SETTINGS.sharktopoda_incoming_port.value
        )
        self.sharktopoda_incoming_port_edit.valueChanged.connect(
            self.settingsChanged.emit
        )
        SETTINGS.sharktopoda_incoming_port.valueChanged.connect(
            self.sharktopoda_incoming_port_edit.setValue
        )

        self.sharktopoda_host_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.sharktopoda_outgoing_port_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.sharktopoda_incoming_port_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.connect_button = QtWidgets.QPushButton("Connect")

        def apply_then_connect():
            self.apply_settings()
            connect_slot()

        self.connect_button.clicked.connect(apply_then_connect)

        self.connected_icon = QtWidgets.QLabel()
        self.connected_icon.setPixmap(
            self.style()
            .standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton)
            .pixmap(16, 16)
        )
        self.connected_icon.setVisible(False)
        connected_signal.connect(lambda: self.connected_icon.setVisible(True))

        self.arrange()

    def arrange(self):
        layout = QtWidgets.QGridLayout()

        layout.addWidget(QtWidgets.QLabel("Sharktopoda host"), 0, 0)
        layout.addWidget(self.sharktopoda_host_edit, 0, 1)

        layout.addWidget(QtWidgets.QLabel("Sharktopoda outgoing port"), 1, 0)
        layout.addWidget(self.sharktopoda_outgoing_port_edit, 1, 1)

        layout.addWidget(QtWidgets.QLabel("Sharktopoda incoming port"), 2, 0)
        layout.addWidget(self.sharktopoda_incoming_port_edit, 2, 1)

        layout.addWidget(self.connect_button, 3, 0, 1, 2)
        layout.addWidget(self.connected_icon, 3, 2)

        layout.addWidget(QtWidgets.QLabel("Autoconnect"), 4, 0)
        layout.addWidget(self.sharktopoda_autoconnect_checkbox, 4, 1)

        self.setLayout(layout)

    def apply_settings(self):
        SETTINGS.sharktopoda_host.value = self.sharktopoda_host_edit.text()
        SETTINGS.sharktopoda_outgoing_port.value = (
            self.sharktopoda_outgoing_port_edit.value()
        )
        SETTINGS.sharktopoda_incoming_port.value = (
            self.sharktopoda_incoming_port_edit.value()
        )
        SETTINGS.sharktopoda_autoconnect.value = (
            self.sharktopoda_autoconnect_checkbox.isChecked()
        )
