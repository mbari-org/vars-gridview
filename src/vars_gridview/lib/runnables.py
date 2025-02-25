import requests
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool, QTimer


def start(runnable: QRunnable) -> None:
    """
    Start a QRunnable in the global QThreadPool.

    Args:
        runnable (QRunnable): The QRunnable to start.
    """
    QThreadPool.globalInstance().start(runnable)


class HttpGetTask(QRunnable):
    class Signals(QObject):
        responseReceived = pyqtSignal(object)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self.signals = HttpGetTask.Signals()

    def run(self):
        response = requests.get(self._url)
        self.signals.responseReceived.emit(response)


def _test_httpget() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication([])

    urls = [
        "https://fathomnet.org/static/m3/framegrabs/Doc%20Ricketts/images/0025/01_26_40_17.png",
        "https://fathomnet.org/static/m3/framegrabs/Tiburon/images/1107/01_30_30_14.png",
        "https://fathomnet.org/static/m3/framegrabs/Ventana/images/2916/01_32_54_10.png",
    ]

    def handle_response(response: requests.Response) -> None:
        print(
            f"Received {response.status_code} response from {response.url}: {len(response.content)} bytes"
        )

    for url in urls:
        http_get = HttpGetTask(url)
        http_get.signals.responseReceived.connect(handle_response)
        start(http_get)

    quit_timer = QTimer()
    quit_timer.timeout.connect(app.quit)
    quit_timer.start(5000)  # Quit after 5 seconds

    app.exec()


if __name__ == "__main__":
    _test_httpget()


__all__ = ["start", "HttpGetTask"]
