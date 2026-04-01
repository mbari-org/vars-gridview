"""Session controller — authentication and service wiring.

:class:`SessionController` owns the :class:`~vars_gridview.lib.m3.M3Context`
and is responsible for:

1. Authenticating a user against Raziel.
2. Constructing all service objects when login succeeds.
3. Tearing down the session on logout.

It emits typed Qt signals so that the UI layer can react without being coupled
to the Raziel / HTTP internals.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from vars_gridview.lib.m3 import M3Context
from vars_gridview.lib.auth.raziel import authenticate
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.services.annotation_service import AnnotationService
from vars_gridview.services.knowledge_base_service import KnowledgeBaseService
from vars_gridview.services.roi_service import RoiService

_LOG = logging.getLogger(__name__)


class SessionController(QObject):
    """Controller that manages the login lifecycle.

    Typical usage::

        ctrl = SessionController(parent=app)
        ctrl.logged_in.connect(on_logged_in)
        ctrl.login_failed.connect(on_login_failed)
        ctrl.login(raziel_url, username, password)

    Signals:
        logged_in: Emitted after a successful login.  The argument is the
            newly-created :class:`~vars_gridview.lib.m3.M3Context`.
        login_failed: Emitted when authentication fails.  The argument is a
            human-readable error message.
        logged_out: Emitted when :meth:`logout` is called.
    """

    logged_in = pyqtSignal(object)  # M3Context
    login_failed = pyqtSignal(str)
    logged_out = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._context: M3Context | None = None
        self._knowledge_base: KnowledgeBaseService | None = None
        self._annotations: AnnotationService | None = None
        self._roi: RoiService | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def context(self) -> M3Context | None:
        """The active :class:`~vars_gridview.lib.m3.M3Context`, or ``None``."""
        return self._context

    @property
    def knowledge_base(self) -> KnowledgeBaseService | None:
        """The active :class:`~vars_gridview.services.KnowledgeBaseService`."""
        return self._knowledge_base

    @property
    def annotations(self) -> AnnotationService | None:
        """The active :class:`~vars_gridview.services.AnnotationService`."""
        return self._annotations

    @property
    def roi(self) -> RoiService | None:
        """The active :class:`~vars_gridview.services.RoiService`."""
        return self._roi

    @property
    def is_logged_in(self) -> bool:
        """``True`` while a session is active."""
        return self._context is not None

    def login(self, raziel_url: str, username: str, password: str) -> None:
        """Authenticate asynchronously and emit :attr:`logged_in` on success.

        Authentication is performed in a thread-pool worker so the Qt event loop
        is never blocked.  On success :attr:`logged_in` is emitted with the new
        :class:`~vars_gridview.lib.m3.M3Context`; on failure :attr:`login_failed`
        is emitted with an error message.

        Args:
            raziel_url: Base URL of the Raziel service-registry endpoint.
            username: VARS user name.
            password: VARS password.
        """
        worker = Worker(self._authenticate, raziel_url, username, password)
        worker.signals.result.connect(self._on_auth_result)
        worker.signals.error.connect(self._on_auth_error)
        QThreadPool.globalInstance().start(worker)

    def logout(self) -> None:
        """Tear down the active session and emit :attr:`logged_out`."""
        self._context = None
        self._knowledge_base = None
        self._annotations = None
        self._roi = None
        self.logged_out.emit()

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _authenticate(raziel_url: str, username: str, password: str) -> M3Context:
        """Call Raziel and build an :class:`~vars_gridview.lib.m3.M3Context`.

        This method runs in a thread-pool worker.

        Args:
            raziel_url: Raziel base URL.
            username: VARS user name.
            password: VARS password.

        Returns:
            A fully initialised :class:`~vars_gridview.lib.m3.M3Context`.

        Raises:
            Exception: Any network or authentication error.
        """
        endpoints = authenticate(raziel_url, username, password)
        return M3Context.from_endpoint_data(endpoints)

    def _on_auth_result(self, context: M3Context) -> None:
        """Handle a successful authentication.

        Args:
            context: The newly-created :class:`~vars_gridview.lib.m3.M3Context`.
        """
        self._context = context
        self._knowledge_base = KnowledgeBaseService(
            context.vars_kb_server,
            context.vampire_squid,
        )
        self._annotations = AnnotationService(
            context.annosaurus,
            default_observer="",
        )
        self._roi = RoiService(
            skimmer=context.skimmer,
            beholder=context.beholder,
        )
        _LOG.info("Authenticated — context ready")
        self.logged_in.emit(context)

    def _on_auth_error(self, error: tuple) -> None:
        """Handle an authentication failure.

        Args:
            error: ``(exc_type, exc_value, traceback)`` tuple from the worker.
        """
        exc_type, exc_value, _tb = error
        msg = f"{exc_type.__name__}: {exc_value}"
        _LOG.error("Login failed: %s", msg)
        self.login_failed.emit(msg)


__all__ = ["SessionController"]
