from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.constants import SETTINGS


class LoginDialog(QtWidgets.QDialog):
    """
    Dialog to get a username and password. Completer optional for username.
    """

    class LoginForm(QtWidgets.QWidget):
        """
        Login form widget.
        """

        def __init__(self, parent=None, completer=None):
            super().__init__(parent)

            self._username_line_edit = QtWidgets.QLineEdit()
            self._username_line_edit.setText(SETTINGS.username.value)
            if completer is not None:
                self._username_line_edit.setCompleter(completer)

            self._password_line_edit = QtWidgets.QLineEdit()
            self._password_line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

            raziel_url = SETTINGS.raz_url.value
            self._raziel_url_line_edit = QtWidgets.QLineEdit()
            self._raziel_url_line_edit.setText(raziel_url)
            self._raziel_url_line_edit.setPlaceholderText(raziel_url)

            self._username_line_edit.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            self._password_line_edit.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            self._raziel_url_line_edit.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )

            self._raziel_url_line_edit.textChanged.connect(
                self._update_raziel_url_setting
            )

            self._arrange()

        def _arrange(self):
            layout = QtWidgets.QFormLayout()
            layout.setFieldGrowthPolicy(
                QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )

            layout.addRow("Username:", self._username_line_edit)
            layout.addRow("Password:", self._password_line_edit)
            layout.addRow("Config server:", self._raziel_url_line_edit)

            self.setLayout(layout)

        @QtCore.pyqtSlot(str)
        def _update_raziel_url_setting(self, text):
            SETTINGS.raz_url.value = text

        @property
        def credentials(self):
            return self._username_line_edit.text(), self._password_line_edit.text()

        @property
        def raziel_url(self):
            return self._raziel_url_line_edit.text()

    def __init__(self, parent=None, completer=None):
        super().__init__(parent)

        self.setWindowTitle("Login")

        self.setMinimumWidth(400)

        self._login_form = LoginDialog.LoginForm(self, completer)

        self._dialog_buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._dialog_buttons.accepted.connect(self.accept)
        self._dialog_buttons.rejected.connect(self.reject)
        self._dialog_buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        ).setText("Login")

        self._arrange()

    def _arrange(self):
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self._login_form)
        layout.addWidget(self._dialog_buttons)

        self.setLayout(layout)

    @property
    def credentials(self):
        return self._login_form.credentials

    @property
    def raziel_url(self):
        return self._login_form.raziel_url
