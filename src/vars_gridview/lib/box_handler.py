"""Handler for multiple :class:`~vars_gridview.ui.BoundingBox.BoundingBox` overlays."""

from __future__ import annotations

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
        all_labels: list[str] | None = None,
        push_changes_callback=None,
        change_concept_callback=None,
        change_part_callback=None,
        delete_callback=None,
    ) -> None:
        """Construct a :class:`BoxHandler`.

        Args:
            graphics_view: The detail view in which bounding-box overlays are
                rendered.
            image_mosaic: The :class:`~vars_gridview.ui.ImageMosaic.ImageMosaic`
                instance managing the mosaic grid.
            all_labels: Optional list of known concept labels used for
                drop-downs inside individual boxes.
            push_changes_callback: Optional callable accepting a
                ``BoundingBoxAssociation`` used to persist dirty box changes.
            change_concept_callback: Optional callable invoked as
                ``(rect_widget, current_concept) -> concept|None``.
            change_part_callback: Optional callable invoked as
                ``(rect_widget, current_part) -> part|None``.
            delete_callback: Optional callable invoked as ``(rect_widget)``.
        """
        self.boxes: list[BoundingBox] = []
        self.dragging = False

        self.view_box = pg.ViewBox()
        self.graphics_view = graphics_view
        self.graphics_view.setCentralItem(self.view_box)
        self.view_box.setAspectLocked()
        self.roi_detail = pg.ImageItem()
        self.view_box.addItem(self.roi_detail)
        self.all_labels = all_labels or []
        self._push_changes_callback = push_changes_callback
        self._change_concept_callback = change_concept_callback
        self._change_part_callback = change_part_callback
        self._delete_callback = delete_callback

        self.image_mosaic = image_mosaic

    def update_labels(self) -> None:
        """
        Update the labels of all selected bounding boxes.
        """
        for box in self.boxes:
            if box.is_selected:
                box.update_label()

    def add_annotation(
        self,
        obj_idx: int,
        rect_widget: RectWidget,
        image_height: int | None = None,
    ) -> None:
        """
        Add an annotation to the image.

        Args:
            obj_idx (int): The index of the object to annotate.
            rect_widget: ROI widget.
            image_height: Optional known image height to avoid re-fetching image
                metadata from the rect widget.
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
                height = (
                    image_height
                    if image_height is not None
                    else rect_widget.image_height
                )
                if height is None:
                    LOGGER.error("No height for the image, not adding to the view")
                    return

                # Create the bounding box
                bb = BoundingBox(
                    self.view_box,
                    [xmin, height - ymin],
                    [xmax - xmin, -1 * (ymax - ymin)],
                    rect_widget,
                    association,
                    self.image_mosaic,
                    change_concept_callback=self._change_concept_callback,
                    change_part_callback=self._change_part_callback,
                    delete_callback=self._delete_callback,
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
                if self._push_changes_callback is not None:
                    self._push_changes_callback(box.association)
                else:
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
