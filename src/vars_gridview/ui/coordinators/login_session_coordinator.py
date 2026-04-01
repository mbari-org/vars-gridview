"""Coordinator for login dialog + session authentication workflow."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from PyQt6 import QtCore, QtWidgets

from vars_gridview.controllers.session_controller import SessionController
from vars_gridview.ui.dialogs.login_dialog import LoginDialog


class LoginSessionCoordinator(QtCore.QObject):
    """Own login prompting and blocking session authentication flow."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        session_controller: SessionController,
    ) -> None:
        super().__init__(parent)
        self._session_controller = session_controller
        self._login_event_loop: QtCore.QEventLoop | None = None
        self._login_success = False
        self._login_error: str | None = None

        self._session_controller.logged_in.connect(self._on_session_logged_in)
        self._session_controller.login_failed.connect(self._on_session_login_failed)

    def run_login(
        self,
        *,
        parent_widget: QtWidgets.QWidget,
        current_raziel_url: str,
        set_raziel_url: Callable[[str], None],
        login_dialog_factory: Callable[[QtWidgets.QWidget], object] | None = None,
    ) -> str | None:
        """Run login dialog + authentication. Returns username on success."""
        credentials = self._get_login(
            parent_widget=parent_widget,
            login_dialog_factory=login_dialog_factory,
        )
        if credentials is None:
            return None

        username, password, raziel_url = credentials
        if current_raziel_url != raziel_url:
            set_raziel_url(raziel_url)

        ok, error = self._authenticate_session(raziel_url, username, password)
        if not ok:
            message = error or "Unknown authentication error"
            QtWidgets.QMessageBox.critical(
                parent_widget,
                "Authentication failed",
                (
                    "Failed to authenticate with the configuration server. "
                    "Check your username and password.\n\n"
                    f"{message}"
                ),
            )
            return None

        return username

    def _get_login(
        self,
        *,
        parent_widget: QtWidgets.QWidget,
        login_dialog_factory: Callable[[QtWidgets.QWidget], object] | None = None,
    ) -> Optional[Tuple[str, str, str]]:
        factory = login_dialog_factory or (lambda parent: LoginDialog(parent=parent))
        login_dialog = factory(parent_widget)
        login_dialog.focus_username()
        ok = login_dialog.exec()
        if not ok:
            return None
        return (*login_dialog.credentials, login_dialog.raziel_url)

    def _authenticate_session(
        self,
        raziel_url: str,
        username: str,
        password: str,
    ) -> tuple[bool, str | None]:
        self._login_success = False
        self._login_error = None
        self._login_event_loop = QtCore.QEventLoop(self)

        self._session_controller.login(raziel_url, username, password)
        self._login_event_loop.exec()
        self._login_event_loop = None

        return self._login_success, self._login_error

    @QtCore.pyqtSlot(object)
    def _on_session_logged_in(self, _context: object) -> None:
        self._login_success = True
        self._login_error = None
        if self._login_event_loop is not None and self._login_event_loop.isRunning():
            self._login_event_loop.quit()

    @QtCore.pyqtSlot(str)
    def _on_session_login_failed(self, message: str) -> None:
        self._login_success = False
        self._login_error = message
        if self._login_event_loop is not None and self._login_event_loop.isRunning():
            self._login_event_loop.quit()


__all__ = ["LoginSessionCoordinator"]
