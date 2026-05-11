"""Handler for multiple :class:`~vars_gridview.ui.mosaic.bounding_box.BoundingBox` overlays."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui
from uuid import UUID
from typing import TYPE_CHECKING

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.ui.mosaic.bounding_box import BoundingBox
from vars_gridview.ui.mosaic.rect_widget import RectWidget

if TYPE_CHECKING:
    from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic


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
        settings: AppSettings | None = None,
    ) -> None:
        """Construct a :class:`BoxHandler`.

        Args:
            graphics_view: The detail view in which bounding-box overlays are
                rendered.
            image_mosaic: The :class:`~vars_gridview.ui.mosaic.image_mosaic.ImageMosaic`
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
        self._settings = settings or get_settings()

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
        q_color = QtGui.QColor.fromString(
            self._settings.selection_highlight_color.value
        )
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

    def retarget_annotations_for_same_source(self, rect_widget: RectWidget) -> bool:
        """Retarget current overlays to *rect_widget* without reloading the image.

        Returns:
            ``True`` when existing overlays were safely reused, otherwise ``False``.
        """
        active_assocs = [
            assoc for assoc in rect_widget.associations if not assoc.deleted
        ]
        if not self.boxes or len(self.boxes) != len(active_assocs):
            return False

        active_by_uuid = {str(assoc.uuid): assoc for assoc in active_assocs}
        selected_assoc_uuid = str(rect_widget.association.uuid)

        q_color = QtGui.QColor.fromString(
            self._settings.selection_highlight_color.value
        )
        selected_color = q_color.getRgb()
        selected_style = QtCore.Qt.PenStyle.DashLine

        for box in self.boxes:
            assoc = active_by_uuid.get(str(box.association.uuid))
            if assoc is None:
                return False

            box.association = assoc
            box.rect_widget = rect_widget

            color = selected_color
            if str(assoc.uuid) != selected_assoc_uuid:
                avg = int(sum(color) / len(color))
                color = (avg, avg, avg)

            box.color = color
            box.setPen(pg.mkPen(color, width=3, style=selected_style))
            box.update_label()

        return True

    def save_all(self) -> None:
        """
        Save all changes to the bounding boxes.
        """
        for box in self.boxes:
            if box.dirty:
                if self._push_changes_callback is not None:
                    self._push_changes_callback(box.association)
                    box.dirty = False
                else:
                    LOGGER.error(
                        "Cannot persist dirty association without push callback; "
                        "configure BoxHandler with an AnnotationService-backed callback"
                    )

    def get_dirty_associations(self) -> list:
        """Return dirty, non-deleted associations from current overlays.

        This method must be called on the UI thread. The returned associations
        are plain model objects and can be handed to a worker for network I/O.
        """
        return [
            box.association
            for box in self.boxes
            if box.dirty and not box.association.deleted
        ]

    def clear_dirty_for(self, association_uuids: set[UUID]) -> None:
        """Clear dirty flags for boxes whose associations were saved."""
        if not association_uuids:
            return
        for box in self.boxes:
            if box.association.uuid in association_uuids:
                box.dirty = False

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
