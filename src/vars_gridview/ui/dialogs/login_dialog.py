"""Login dialog for VARS GridView authentication."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.ui.style import UiDimensions


class LoginDialog(QtWidgets.QDialog):
    """
    Dialog to get a username and password. Completer optional for username.
    """

    class LoginForm(QtWidgets.QWidget):
        """
        Login form widget.
        """

        def __init__(
            self,
            parent: QtWidgets.QWidget | None = None,
            completer: QtWidgets.QCompleter | None = None,
            settings: AppSettings | None = None,
        ) -> None:
            super().__init__(parent)
            self._settings = settings or get_settings()

            self._username_line_edit = QtWidgets.QLineEdit()
            self._username_line_edit.setText(self._settings.username.value)
            if completer is not None:
                self._username_line_edit.setCompleter(completer)

            self._password_line_edit = QtWidgets.QLineEdit()
            self._password_line_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

            raziel_url = self._settings.raz_url.value
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

        def _arrange(self) -> None:
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
            self._settings.raz_url.value = text

        @property
        def credentials(self) -> tuple[str, str]:
            """Return ``(username, password)``."""
            return self._username_line_edit.text(), self._password_line_edit.text()

        @property
        def raziel_url(self) -> str:
            """Return the Raziel config-server URL entered by the user."""
            return self._raziel_url_line_edit.text()

        def focus_username(self) -> None:
            """Focus the username input field."""
            self._username_line_edit.setFocus()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        completer: QtWidgets.QCompleter | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Login")

        self.setMinimumWidth(UiDimensions.DIALOG_MIN_WIDTH)

        self._login_form = LoginDialog.LoginForm(self, completer, settings=settings)

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

    def _arrange(self) -> None:
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self._login_form)
        layout.addWidget(self._dialog_buttons)

        self.setLayout(layout)

    @property
    def credentials(self) -> tuple[str, str]:
        """Return ``(username, password)`` from the embedded form."""
        return self._login_form.credentials

    @property
    def raziel_url(self) -> str:
        """Return the Raziel URL entered in the embedded form."""
        return self._login_form.raziel_url

    def focus_username(self) -> None:
        """Focus the username field in the embedded login form."""
        self._login_form.focus_username()
