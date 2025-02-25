"""
App settings management.
"""

from typing import Any, Dict, Optional

from PyQt6 import QtCore


class SettingProxy(QtCore.QObject):
    """
    Proxy for a single setting value. Emits valueChanged when the value is set.
    """

    valueChanged = QtCore.pyqtSignal(object)
    """
    Signal emitted when the value is set.
    """

    def __init__(self, settings: QtCore.QSettings, key: str, type=str, default=None):
        super().__init__()

        self._settings = settings
        self._key = key
        self._type = type
        self._default = default

        if default is not None and self.value is None:
            self.value = default

    @property
    def value(self) -> Any:
        """
        Get the value of the setting.

        Returns:
            Any: The value of the setting.
        """
        return self._settings.value(
            self._key, type=self._type, defaultValue=self._default
        )

    @value.setter
    def value(self, value: Any) -> None:
        """
        Set the value of the setting. Emits valueChanged with the new value.

        Args:
            value (Any): The new value of the setting.
        """
        self._settings.setValue(self._key, value)
        self.valueChanged.emit(value)


class SettingsManager:
    """
    Settings manager. Maintains a namespace of settings proxies.

    Example of a str-valued setting with no default:

    >>> settings = SettingsManager.get_instance()
    >>> settings.some_str = 'mysection/mykey'
    >>> settings.some_str.value = 'asdf'  # settings.some_str emits valueChanged with 'asdf'
    >>> settings.some_str.value  # returns 'asdf'

    Example of an int-valued setting with a default:
    >>> settings.some_int = ('mysection/mykey2', int, 42)
    >>> settings.some_int.value  # returns 42
    >>> settings.some_int.value = 24  # settings.some_int emits valueChanged with 24
    """

    _instance: "SettingsManager" = None

    def __init__(self, settings: Optional[QtCore.QSettings] = None):
        self._settings = settings or QtCore.QSettings()
        self._proxies: Dict[str, SettingProxy] = {}

    def __getattribute__(self, __name: str) -> SettingProxy:
        if __name in ("_settings", "_proxies"):
            return super().__getattribute__(__name)
        elif __name in self._proxies:
            return self._proxies[__name]
        else:
            raise AttributeError(f"No such setting: {__name}")

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in ("_settings", "_proxies"):
            super().__setattr__(__name, __value)
        elif isinstance(__value, SettingProxy):
            self._proxies[__name] = __value
        elif isinstance(__value, str):
            self._proxies[__name] = SettingProxy(self._settings, __value)
        elif isinstance(__value, tuple):
            self._proxies[__name] = SettingProxy(
                self._settings, __value[0], *__value[1:]
            )
