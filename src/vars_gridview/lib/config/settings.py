"""Typed application settings backed by :class:`QtCore.QSettings`.

Each setting is exposed as an attribute of type :class:`SettingProxy`, which:
* Persists the value through ``QSettings``.
* Emits ``valueChanged`` whenever the value changes.
* Provides full IDE autocomplete (no ``__getattribute__`` magic).

Usage example::

    from vars_gridview.lib.config.settings import AppSettings, build_settings
    settings = build_settings()
    settings.label_font_size.value = 10
    settings.label_font_size.valueChanged.connect(my_slot)
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from PyQt6 import QtCore

from vars_gridview.ui.style import DEFAULT_SELECTION_HIGHLIGHT_COLOR

T = TypeVar("T")


class SettingProxy(QtCore.QObject, Generic[T]):
    """A typed proxy that wraps a single ``QSettings`` key.

    Emits :attr:`valueChanged` only when the persisted value actually changes.

    Args:
        qsettings: The underlying ``QSettings`` store.
        key: The dot-less ini key, e.g. ``"appearance/label_font_size"``.
        type_: The Python type to use when reading from ``QSettings``.
        default: Default value used when the key is not yet present in the store.
    """

    valueChanged = QtCore.pyqtSignal(object)
    """Emitted with the new value whenever :attr:`value` is assigned."""

    def __init__(
        self,
        qsettings: QtCore.QSettings,
        key: str,
        type_: type,
        default: Optional[T],
    ) -> None:
        super().__init__()
        self._settings = qsettings
        self._key = key
        self._type = type_
        self._default = default
        # Write the default if the key has never been set.
        if default is not None and self._settings.value(self._key) is None:
            self._settings.setValue(self._key, default)

    @property
    def value(self) -> T:
        """The current value, read from the persistent store."""
        return self._settings.value(
            self._key, type=self._type, defaultValue=self._default
        )

    @value.setter
    def value(self, new_value: T) -> None:
        """Persist *new_value* and emit :attr:`valueChanged` when changed."""
        self.set_value(new_value)

    @property
    def key(self) -> str:
        """Underlying ``QSettings`` key for this proxy."""
        return self._key

    def set_value(self, new_value: T) -> bool:
        """Persist *new_value* and return whether it changed.

        Returns:
            ``True`` when the stored value changed and ``valueChanged`` was
            emitted, otherwise ``False``.
        """
        old_value = self.value
        if old_value == new_value:
            return False
        self._settings.setValue(self._key, new_value)
        self.valueChanged.emit(new_value)
        return True


class AppSettings:
    """All application settings as explicitly-typed :class:`SettingProxy` attributes.

    Construct via :func:`build_settings`; pass the resulting instance wherever
    settings are needed rather than importing a global.

    Attributes:
        raziel_url: URL of the Raziel configuration server.
        username: Last-used VARS username.
        label_font_size: Font size (pt) for bounding-box labels.
        selection_highlight_color: Hex colour string for the selection highlight.
        sharktopoda_host: Hostname / IP of the Sharktopoda video player.
        sharktopoda_outgoing_port: UDP port for outgoing Sharktopoda messages.
        sharktopoda_incoming_port: UDP port for incoming Sharktopoda responses.
        sharktopoda_autoconnect: Whether to connect to Sharktopoda on startup.
        cache_dir: Filesystem path to the on-disk image cache directory.
        embeddings_enabled: Whether embedding-backed similarity features are active.
        embedding_service_url: Base URL of the embedding HTTP service.
        embedding_model_name: Image model name to use on the embedding service.
        gui_geometry: Saved ``QMainWindow`` geometry bytes.
        gui_window_state: Saved ``QMainWindow`` toolbar/dock state bytes.
        gui_splitter1_state: Saved state of the main horizontal splitter.
        gui_splitter2_state: Saved state of the secondary vertical splitter.
        gui_style: Name of the active colour theme
            (``"default"``, ``"darkstyle"``, or ``"darkbreeze"``).
        gui_zoom: Current grid zoom factor in the range [0.1, 2.0].
    """

    def __init__(self, qsettings: QtCore.QSettings) -> None:
        """Initialise all proxies against the given *qsettings* store.

        Args:
            qsettings: Platform-scoped ``QSettings`` instance.
        """
        from pathlib import Path
        from platformdirs import user_cache_dir

        _s = qsettings

        # ── M3 connectivity ────────────────────────────────────────────────────
        self.raziel_url: SettingProxy[str] = SettingProxy(
            _s, "m3/raz_url", str, "https://m3.shore.mbari.org/config"
        )
        # Backward-compat alias used across existing UI code.
        self.raz_url: SettingProxy[str] = self.raziel_url
        self.username: SettingProxy[str] = SettingProxy(_s, "m3/username", str, "")

        # ── Appearance ─────────────────────────────────────────────────────────
        self.label_font_size: SettingProxy[int] = SettingProxy(
            _s, "appearance/label_font_size", int, 8
        )
        self.selection_highlight_color: SettingProxy[str] = SettingProxy(
            _s,
            "appearance/selection_highlight_color",
            str,
            DEFAULT_SELECTION_HIGHLIGHT_COLOR,
        )

        # ── Sharktopoda video player ───────────────────────────────────────────
        self.sharktopoda_host: SettingProxy[str] = SettingProxy(
            _s, "video/sharktopoda_host", str, "::1"
        )
        self.sharktopoda_outgoing_port: SettingProxy[int] = SettingProxy(
            _s, "video/sharktopoda_outgoing_port", int, 8800
        )
        self.sharktopoda_incoming_port: SettingProxy[int] = SettingProxy(
            _s, "video/sharktopoda_incoming_port", int, 8801
        )
        self.sharktopoda_autoconnect: SettingProxy[bool] = SettingProxy(
            _s, "video/sharktopoda_autoconnect", bool, True
        )

        # ── Cache ──────────────────────────────────────────────────────────────
        default_cache = str(Path(user_cache_dir("VARS GridView")))
        self.cache_dir: SettingProxy[str] = SettingProxy(
            _s, "cache/dir", str, default_cache
        )
        # Ensure the cache directory exists
        Path(self.cache_dir.value).mkdir(parents=True, exist_ok=True)

        # ── Embeddings ─────────────────────────────────────────────────────────
        self.embeddings_enabled: SettingProxy[bool] = SettingProxy(
            _s, "embeddings/enabled", bool, False
        )
        self.embedding_service_url: SettingProxy[str] = SettingProxy(
            _s,
            "embeddings/service_url",
            str,
            "http://donnager.shore.mbari.org:5000/",
        )
        self.embedding_model_name: SettingProxy[str] = SettingProxy(
            _s,
            "embeddings/model_name",
            str,
            "dinov3",
        )

        # ── GUI persistence ────────────────────────────────────────────────────
        self.gui_geometry: SettingProxy[QtCore.QByteArray] = SettingProxy(
            _s, "gui/geometry", QtCore.QByteArray, None
        )
        self.gui_window_state: SettingProxy[QtCore.QByteArray] = SettingProxy(
            _s, "gui/window_state", QtCore.QByteArray, None
        )
        self.gui_splitter1_state: SettingProxy[QtCore.QByteArray] = SettingProxy(
            _s, "gui/splitter1_state", QtCore.QByteArray, None
        )
        self.gui_splitter2_state: SettingProxy[QtCore.QByteArray] = SettingProxy(
            _s, "gui/splitter2_state", QtCore.QByteArray, None
        )
        self.gui_style: SettingProxy[str] = SettingProxy(
            _s, "gui/style", str, "default"
        )
        self.gui_zoom: SettingProxy[float] = SettingProxy(_s, "gui/zoom", float, 0.60)


def build_settings() -> AppSettings:
    """Create and return an :class:`AppSettings` backed by the platform store.

    The ``QSettings`` instance is scoped to the *MBARI* organisation and the
    *VARS GridView* application, and uses the INI format for readability.

    Returns:
        A fully-initialised :class:`AppSettings` instance.
    """
    qsettings = QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        "MBARI",
        "VARS GridView",
    )
    return AppSettings(qsettings)


__all__ = ["SettingProxy", "AppSettings", "build_settings"]
