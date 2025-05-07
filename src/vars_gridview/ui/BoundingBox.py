"""
Bounding box widget in the image view.
"""

from typing import List, Tuple

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.operations import get_kb_concepts, get_kb_parts
from vars_gridview.ui.ImageMosaic import ImageMosaic
from vars_gridview.ui.RectWidget import RectWidget


class BoundingBox(pg.RectROI):
    """
    A class to represent a bounding box in an image.

    Attributes:
        view (pg.ViewBox): The view box to which the bounding box is added.
        pos (tuple): The position of the bounding box.
        size (tuple): The size of the bounding box.
        rect (RectWidget): The ROI widget tied to this bounding box.
        association (BoundingBoxAssociation): The bounding box association tied to this bounding box.
        image_mosaic (ImageMosaic): The image mosaic widget.
        color (tuple): The color of the bounding box. Default is red.
        label (str): The label of the bounding box. Default is "ROI".
    """

    def __init__(
        self,
        view: pg.ViewBox,
        pos: Tuple[float, float],
        size: Tuple[float, float],
        rect_widget: RectWidget,
        association: BoundingBoxAssociation,
        image_mosaic: ImageMosaic,
        color: Tuple[int, int, int] = (255, 0, 0),
        label: str = "ROI",
    ) -> None:
        """
        Constructs all the necessary attributes for the bounding box object.

        Args:
            view (pg.ViewBox): The view box to which the bounding box is added.
            pos (tuple): The position of the bounding box.
            size (tuple): The size of the bounding box.
            rect (RectWidget): The ROI widget tied to this bounding box.
            association (BoundingBoxAssociation): The bounding box association tied to this bounding box.
            image_mosaic (ImageMosaic): The image mosaic widget.
            color (tuple, optional): The color of the bounding box. Default is red.
            label (str, optional): The label of the bounding box. Default is "ROI".
        """
        pg.RectROI.__init__(
            self,
            pos,
            size,
            pen=pg.mkPen(color, width=3, style=QtCore.Qt.PenStyle.DashLine),
            invertible=True,
            rotatable=False,
            removable=False,
            sideScalers=True,
        )
        self.association = association
        self.rect_widget = rect_widget
        self.image_mosaic = image_mosaic

        # GUI things
        self.addScaleHandle([1, 0], [0, 1])
        self.addScaleHandle([0, 1], [1, 0])
        self.addTranslateHandle([0.5, 0.5])

        self.label = label
        self.color = color
        self.textItem = None

        self.view = view
        self.view.addItem(self)
        self.draw_name()

        self.dirty = False

        self._menu = QtWidgets.QMenu()
        self._setup_menu()

        self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)

        self._connect()

    def _connect(self) -> None:
        """
        Connect signals and slots.
        """
        self.sigRemoveRequested.connect(lambda _: self.remove())
        self.sigRegionChanged.connect(self.draw_name)
        self.sigRegionChanged.connect(self._dirty)
        self.sigRegionChangeFinished.connect(self.check_bounds)
        self.sigRegionChangeFinished.connect(self.update_association_box)
        self.sigClicked.connect(
            lambda _, ev: self.rect_widget.clicked.emit(self.rect_widget, ev)
        )

    def _setup_menu(self) -> None:
        """
        Set up the context menu for the bounding box.
        """
        self._menu.addAction("Change concept", self._do_change_concept)
        self._menu.addAction("Change part", self._do_change_part)
        self._menu.addSeparator()
        self._menu.addAction("Delete", self._do_delete)

    def contextMenuEvent(self, ev: QtGui.QContextMenuEvent) -> None:
        """
        Show the context menu.

        Args:
            ev (QtGui.QContextMenuEvent): The context menu event.
        """
        self._menu.popup(ev.screenPos())

    def _do_delete(self) -> None:
        """
        Delete the bounding box (clicked from context menu).
        """
        self.image_mosaic.select(self.rect_widget)
        self.image_mosaic.delete_selected()

    def _do_change_concept(self) -> None:
        """
        Change the concept of the bounding box (clicked from context menu).
        """
        try:
            kb_concepts = get_kb_concepts()
        except Exception as e:
            LOGGER.error(f"Could not get KB concepts: {e}")
            return

        concept, ok = QtWidgets.QInputDialog.getItem(
            self.image_mosaic._graphics_view, "Change concept", "Concept:", kb_concepts
        )

        if not ok:
            return

        self.image_mosaic.select(self.rect_widget)
        self.image_mosaic.label_selected(concept, None)

    def _do_change_part(self) -> None:
        """
        Change the part of the bounding box (clicked from context menu).
        """
        try:
            kb_parts = get_kb_parts()
        except Exception as e:
            LOGGER.error(f"Could not get KB parts: {e}")
            return

        part, ok = QtWidgets.QInputDialog.getItem(
            self.image_mosaic._graphics_view, "Change part", "Part:", kb_parts
        )

        if not ok:
            return

        self.image_mosaic.select(self.rect_widget)
        self.image_mosaic.label_selected(None, part)

    def check_bounds(self) -> None:
        """
        Check and adjust the bounds of the bounding box to ensure it stays within the image.
        """
        x, y = self.pos()
        w, h = self.size()
        h = -h  # Fix negative height

        image_width = self.rect_widget.image_width
        image_height = self.rect_widget.image_height
        if image_width is None or image_height is None:
            QtWidgets.QMessageBox.critical(
                self,
                "Could not get image size",
                "Could not load the image for the annotation, so bounding box validity cannot be assessed.",
            )
            return

        min_x = 0
        max_x = image_width - w

        min_y = h
        max_y = image_height

        if x < min_x or y < min_y or x > max_x or y > max_y:
            self.setPos(min(max_x, max(min_x, x)), min(max_y, max(min_y, y)))

    @property
    def is_selected(self) -> bool:
        """
        bool: Whether the bounding box is selected.
        """
        return self.rect_widget.is_selected

    def _dirty(self) -> None:
        """
        Mark the bounding box as dirty (modified).
        """
        self.dirty = True

    def update_association_box(self) -> None:
        """
        Update the bounding box association's coordinates with the current bounding box coordinates.
        """
        x, y, w, h = self.get_box()
        y = self.rect_widget.image_height - y
        self.association.update_data(x=x, y=y, width=w, height=h)
        self.association.rect_widget.update_roi_pic()

    def update_label(self) -> None:
        """
        Update the label of the bounding box.
        """
        self.label = self.association.text_label
        self.draw_name()

    def remove(self) -> None:
        """
        Remove the bounding box from the view.
        """
        self.view.removeItem(self.textItem)
        self.view.removeItem(self)

    def get_box(self) -> List[float]:
        """
        Get the coordinates of the bounding box.

        Returns:
            list: A list containing the x, y, width, and height of the bounding box.
        """
        x, y = self.pos()
        w, h = self.size()

        # need to convert box coordinates to account for positive or
        # negative width/height values from pyqtgraph roi object
        if h > 0:
            y = y + h
        if w < 0:
            x = x + w

        return [round(x), round(y), round(np.abs(w)), round(np.abs(h))]

    @QtCore.pyqtSlot()
    def draw_name(self) -> None:
        """
        Draw the label of the bounding box on the image.
        """
        roiSize = self.size()
        w = roiSize[0]
        h = roiSize[1]
        if w < 0:
            x = self.pos().x() - np.abs(w)
        else:
            x = self.pos().x()
        if h < 0:
            y = self.pos().y() - np.abs(h)
        else:
            y = self.pos().y()

        if self.textItem is None:
            self.textItem = pg.TextItem(
                text=self.label, color=(255, 255, 255), fill=(70, 70, 70)
            )
            self.textItem.setPos(x, y)
            self.view.addItem(self.textItem)
        else:
            self.textItem.setText(self.label)
            self.textItem.setPos(x, y)
