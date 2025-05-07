from typing import List

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.log import LOGGER
from vars_gridview.ui.BoundingBox import BoundingBox
from vars_gridview.ui.ImageMosaic import ImageMosaic
from vars_gridview.ui.RectWidget import RectWidget


class BoxHandler:
    """
    A class to handle multiple bounding boxes in an image.

    Attributes:
        graphics_view (pg.GraphicsView): The graphics view to which the bounding boxes are added.
        image_mosaic (ImageMosaic): The image mosaic instance.
        all_labels (list, optional): A list of all labels for the bounding boxes.
    """

    def __init__(
        self,
        graphics_view: pg.GraphicsView,
        image_mosaic: ImageMosaic,
        all_labels: List[str] = [],
    ) -> None:
        """
        Constructs all the necessary attributes for the box handler object.

        Args:
            graphics_view (pg.GraphicsView): The graphics view to which the bounding boxes are added.
            image_mosaic (object): The image mosaic object associated with the bounding boxes.
            all_labels (list, optional): A list of all labels for the bounding boxes.
        """
        self.boxes: List[BoundingBox] = []
        self.dragging = False

        self.view_box = pg.ViewBox()
        self.graphics_view = graphics_view
        self.graphics_view.setCentralItem(self.view_box)
        self.view_box.setAspectLocked()
        self.roi_detail = pg.ImageItem()
        self.view_box.addItem(self.roi_detail)
        self.all_labels = all_labels

        self.image_mosaic = image_mosaic

    def update_labels(self) -> None:
        """
        Update the labels of all selected bounding boxes.
        """
        for box in self.boxes:
            if box.is_selected:
                box.update_label()

    def add_annotation(self, obj_idx: int, rect_widget: RectWidget) -> None:
        """
        Add an annotation to the image.

        Args:
            obj_idx (int): The index of the object to annotate.
            rect_widget: ROI widget.
        """
        q_color = QtGui.QColor.fromString(SETTINGS.selection_highlight_color.value)
        for idx, association in enumerate(rect_widget.associations):
            if association.deleted:
                continue
            selected_loc = idx == obj_idx

            # Set color of the box
            color = q_color.getRgb()
            if not selected_loc:
                avg = int(sum(color) / len(color))
                color = (avg, avg, avg)  # Grayscale equivalent of original color

            # Grab the bounds
            xmin, ymin, xmax, ymax = association.box
            if xmax - xmin <= 0 or ymax - ymin <= 0:  # Bad box bounds check
                LOGGER.warning("Bad box bounds, not adding to the view")
            else:
                label = association.text_label
                height = rect_widget.image_height
                if height is None:
                    LOGGER.error("No height for the image, not adding to the view")
                    return

                # Create the bounding box
                bb = BoundingBox(
                    self.view_box,
                    [xmin, height - ymin],
                    [xmax - xmin, -1 * (ymax - ymin)],
                    association.rect_widget,
                    association,
                    self.image_mosaic,
                    color=color,
                    label=label,
                )

                # Add it to the list
                self.boxes.append(bb)

    def save_all(self) -> None:
        """
        Save all changes to the bounding boxes.
        """
        for box in self.boxes:
            if box.dirty:
                box.association.push_changes()

    def map_pos_to_item(self, pos: QtCore.QPointF) -> QtCore.QPointF:
        """
        Map a position to the item in the view box.

        Args:
            pos (QtCore.QPointF): The position to map.

        Returns:
            QtCore.QPointF: The mapped position.
        """
        pt = self.view_box.mapSceneToView(pos)
        pt = self.view_box.mapFromViewToItem(self.roi_detail, pt)
        return pt

    def clear(self) -> None:
        """
        Clear all bounding boxes from the view.
        """
        for box in self.boxes:
            box.remove()
        self.boxes = []
