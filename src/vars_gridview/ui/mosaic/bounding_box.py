"""Bounding-box overlay widget rendered on top of a pyqtgraph ``ViewBox``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.runtime.log import LOGGER

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


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
        pos: tuple[float, float],
        size: tuple[float, float],
        rect_widget: RectWidget,
        association: BoundingBoxAssociation,
        image_mosaic: ImageMosaic,
        max_bounds: QtCore.QRectF | None = None,
        change_concept_callback=None,
        change_part_callback=None,
        delete_callback=None,
        color: tuple[int, int, int] = (255, 0, 0),
        label: str = "ROI",
    ) -> None:
        """Construct a bounding-box overlay.

        Args:
            view: The pyqtgraph ``ViewBox`` to which the box is added.
            pos: ``(x, y)`` position of the box origin, in image pixel space.
            size: ``(width, height)`` of the box, in image pixel space.
            rect_widget: The :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
                backing this box in the mosaic.
            association: Underlying :class:`~vars_gridview.lib.annotation.association.BoundingBoxAssociation`.
            image_mosaic: The controlling :class:`~vars_gridview.ui.mosaic.image_mosaic.ImageMosaic`.
            max_bounds: Optional rectangle (image bounds) the box may not be
                dragged or resized outside of.
            change_concept_callback: Optional callback for concept changes.
            change_part_callback: Optional callback for part changes.
            delete_callback: Optional callback for deletion.
            color: RGB fill colour for the box pen. Defaults to red.
            label: Display label. Defaults to ``"ROI"``.
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
            maxBounds=max_bounds,
        )
        self.association = association
        self.rect_widget = rect_widget
        self.image_mosaic = image_mosaic
        self._change_concept_callback = change_concept_callback
        self._change_part_callback = change_part_callback
        self._delete_callback = delete_callback

        # GUI things. RectROI.__init__ (with sideScalers=True) already adds
        # scale handles at the top-right corner and the top/right edge
        # midpoints; fill in the remaining corner and edge midpoints so all
        # four corners and edges can be dragged independently.
        self.addScaleHandle([1, 0], [0, 1])
        self.addScaleHandle([0, 1], [1, 0])
        self.addScaleHandle([0, 0], [1, 1])
        self.addScaleHandle([0, 0.5], [1, 0.5])
        self.addScaleHandle([0.5, 0], [0.5, 1])
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
        if self._delete_callback is not None:
            self._delete_callback(self.rect_widget)
            return
        LOGGER.error("Delete callback is not configured for BoundingBox context action")

    def _do_change_concept(self) -> None:
        """
        Change the concept of the bounding box (clicked from context menu).
        """
        if self._change_concept_callback is not None:
            concept = self._change_concept_callback(
                self.rect_widget,
                self.association.concept,
            )
            if concept:
                self.image_mosaic.select(self.rect_widget)
            return
        LOGGER.error(
            "Concept-change callback is not configured for BoundingBox context action"
        )

    def _do_change_part(self) -> None:
        """
        Change the part of the bounding box (clicked from context menu).
        """
        if self._change_part_callback is not None:
            part = self._change_part_callback(
                self.rect_widget,
                self.association.part,
            )
            if part:
                self.image_mosaic.select(self.rect_widget)
            return
        LOGGER.error(
            "Part-change callback is not configured for BoundingBox context action"
        )

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
        self.association.update_data(x=x, y=y, width=w, height=h)
        self.rect_widget.request_roi_refresh()

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

    def get_box(self) -> list[float]:
        """Return ``[x, y, width, height]`` coordinates of the bounding box, in
        top-left-origin, y-down image pixel space."""
        x, y = self.pos()
        w, h = self.size()

        # Scale handles are invertible, so dragging one past the opposite
        # edge/corner can leave width and/or height negative; normalize back
        # to a canonical top-left origin with positive width/height.
        if w < 0:
            x = x + w
        if h < 0:
            y = y + h

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
                text=self.label,
                color=(255, 255, 255),
                fill=(70, 70, 70),
                anchor=(0, 1),
            )
            self.textItem.setPos(x, y)
            self.view.addItem(self.textItem)
        else:
            self.textItem.setText(self.label)
            self.textItem.setPos(x, y)
