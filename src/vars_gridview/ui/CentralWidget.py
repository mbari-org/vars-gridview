from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QStatusBar, QMenuBar
from PyQt6.QtCore import Qt

from vars_gridview.ui.ControlBar import ControlBar
from vars_gridview.ui.InfoPanel import InfoPanel
from vars_gridview.ui.RoiGraphicsView import RoiGraphicsView


class CentralWidget(QWidget):
    """
    Central application widget. All other widgets are children of this widget.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        flags: Qt.WindowType = Qt.WindowType.Window,
    ) -> None:
        super().__init__(parent, flags)

        # Central splitter. Image mosaic on the left, ROI data on the right.
        self._central_splitter = QSplitter()
        self._central_splitter.setOrientation(Qt.Orientation.Horizontal)

        # Image mosaic. Shows a grid of RectWidgets.
        self._image_mosaic = QWidget()  # TODO: Replace with ImageMosaic

        # ROI data splitter. ROI graphics view on top, ROI info panel on bottom.
        self._roi_data_splitter = QSplitter()
        self._roi_data_splitter.setOrientation(Qt.Orientation.Vertical)

        # ROI graphics view. Shows the full image with ROIs drawn on top. Provides controls for editing ROI bounds.
        self._roi_graphics_view = RoiGraphicsView()

        # ROI info panel. Shows information about the currently selected ROI.
        self._info_panel = InfoPanel()

        # Control bar. Contains buttons and input fields.
        self._control_bar = ControlBar()

        # Status bar. Shows status messages.
        self._status_bar = QStatusBar(parent=self)

        # Menu bar. Contains menus and actions.
        self._menu_bar = QMenuBar(parent=self)

        self._connect()
        self._layout()

    def _connect(self) -> None:
        """
        Connect signals and slots.
        """
        pass

    def _layout(self) -> None:
        """
        Lay out the widget.
        """
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Stack the ROI graphics view and the ROI info panel
        self._roi_data_splitter.addWidget(self._roi_graphics_view)
        self._roi_data_splitter.addWidget(self._info_panel)

        # Stack the image mosaic and the ROI data splitter
        self._central_splitter.addWidget(self._image_mosaic)
        self._central_splitter.addWidget(self._roi_data_splitter)

        # Stack the central splitter, control bar, and status bar
        layout.addWidget(self._central_splitter, stretch=1)
        layout.addWidget(self._control_bar, stretch=0)
        layout.addWidget(self._status_bar, stretch=0)

        # Add the menu bar
        layout.setMenuBar(self._menu_bar)


def _test() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication([])

    widget = CentralWidget()
    widget.show()

    app.exec()


if __name__ == "__main__":
    _test()


__all__ = ["CentralWidget"]
