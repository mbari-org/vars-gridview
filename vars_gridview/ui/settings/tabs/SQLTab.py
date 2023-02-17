from PyQt6 import QtWidgets

from vars_gridview.ui.settings.tabs.AbstractSettingsTab import AbstractSettingsTab


class SQLTab(AbstractSettingsTab):
    """
    SQL server tab.
    """

    def __init__(self, parent=None):
        super().__init__("SQL", parent=parent)

        self.sql_url_edit = QtWidgets.QLineEdit(self._settings.sql_url.value)
        self.sql_url_edit.textChanged.connect(self.settingsChanged.emit)

        self.user_edit = QtWidgets.QLineEdit(self._settings.sql_user.value)
        self.user_edit.textChanged.connect(self.settingsChanged.emit)

        self.password_edit = QtWidgets.QLineEdit(self._settings.sql_password.value)
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password_edit.textChanged.connect(self.settingsChanged.emit)

        self.database_edit = QtWidgets.QLineEdit(self._settings.sql_database.value)
        self.database_edit.textChanged.connect(self.settingsChanged.emit)

        self.arrange()

    def arrange(self):
        layout = QtWidgets.QFormLayout()
        
        layout.addRow(
            "",
            QtWidgets.QLabel(
                "Changes in this tab will only take effect after restarting the application."
            )
        )

        layout.addRow("Server URL", self.sql_url_edit)
        layout.addRow("Username", self.user_edit)
        layout.addRow("Password", self.password_edit)
        layout.addRow(
            "",
            QtWidgets.QLabel(
                "The password is stored in plain text. For this reason, it is recommended to use a read-only login."
            ),
        )
        layout.addRow("Database", self.database_edit)

        self.setLayout(layout)

    def apply_settings(self):
        self._settings.sql_url.value = self.sql_url_edit.text()
        self._settings.sql_user.value = self.user_edit.text()
        self._settings.sql_password.value = self.password_edit.text()
        self._settings.sql_database.value = self.database_edit.text()
