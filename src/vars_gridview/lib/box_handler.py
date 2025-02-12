from typing import List, Optional

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui

from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.log import LOGGER
from vars_gridview.ui.BoundingBox import BoundingBox


class BoxHandler:
    """
    A class to handle multiple bounding boxes in an image.

    Attributes:
        graphics_view (pg.GraphicsView): The graphics view to which the bounding boxes are added.
        image_mosaic (object): The image mosaic object associated with the bounding boxes.
        localization (object, optional): The localization object associated with the bounding boxes.
        all_labels (list, optional): A list of all labels for the bounding boxes.
        verifier (object, optional): The verifier object associated with the bounding boxes.
    """

    def __init__(
        self,
        graphics_view: pg.GraphicsView,
        image_mosaic: object,
        localization: Optional[object] = None,
        all_labels: List[str] = [],
        verifier: Optional[object] = None,
    ) -> None:
        """
        Constructs all the necessary attributes for the box handler object.

        Args:
            graphics_view (pg.GraphicsView): The graphics view to which the bounding boxes are added.
            image_mosaic (object): The image mosaic object associated with the bounding boxes.
            localization (object, optional): The localization object associated with the bounding boxes.
            all_labels (list, optional): A list of all labels for the bounding boxes.
            verifier (object, optional): The verifier object associated with the bounding boxes.
        """
        self.boxes = []
        self.dragging = False

        self.view_box = pg.ViewBox()
        self.graphics_view = graphics_view
        self.graphics_view.setCentralItem(self.view_box)
        self.view_box.setAspectLocked()
        self.roi_detail = pg.ImageItem()
        self.view_box.addItem(self.roi_detail)
        self.localization = localization
        self.all_labels = all_labels
        self.verifier = verifier

        self.image_mosaic = image_mosaic

    def update_labels(self) -> None:
        """
        Update the labels of all selected bounding boxes.
        """
        for box in self.boxes:
            if box.is_selected:
                box.update_label()

    def add_annotation(self, obj_idx: int, rect: object) -> None:
        """
        Add an annotation to the image.

        Args:
            obj_idx (int): The index of the object to annotate.
            rect (object): The rectangle object associated with the annotation.
        """
        q_color = QtGui.QColor.fromString(SETTINGS.selection_highlight_color.value)
        for idx, localization in enumerate(rect.localizations):
            if localization.deleted:
                continue
            selected_loc = idx == obj_idx

            # Set color of the box
            color = q_color.getRgb()
            if not selected_loc:
                avg = int(sum(color) / len(color))
                color = (avg, avg, avg)  # Grayscale equivalent of original color

            # Grab the bounds
            xmin, ymin, xmax, ymax = localization.box
            if xmax - xmin <= 0 or ymax - ymin <= 0:  # Bad box bounds check
                LOGGER.warn("Bad box bounds, not adding to the view")
            else:
                label = localization.text_label
                height = rect.image_height

                # Create the bounding box
                bb = BoundingBox(
                    self.view_box,
                    [xmin, height - ymin],
                    [xmax - xmin, -1 * (ymax - ymin)],
                    localization.rect,
                    localization,
                    self.verifier,
                    self.image_mosaic,
                    color=color,
                    label=label,
                )

                # Add it to the list
                self.boxes.append(bb)

        self.localization = rect.localizations[obj_idx]

    def save_all(self, verifier: object) -> None:
        """
        Save all changes to the bounding boxes.

        Args:
            verifier (object): The verifier object to use for saving changes.
        """
        for box in self.boxes:
            if box.dirty:
                box.localization.push_changes(verifier)

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
            box.remove(None)
        self.boxes = []
