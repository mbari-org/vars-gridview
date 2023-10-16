from typing import Tuple
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets
from vars_gridview.lib.grid_view import GridViewController

from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.operations import get_kb_concepts, get_kb_parts
from vars_gridview.lib.models import BoundingBox
from vars_gridview.lib.widgets import RectWidget


class GraphicalBoundingBox(pg.RectROI):
    """
    Graphics bounding box for a localization.
    """
    def __init__(
        self,
        view: pg.GraphicsView,
        pos,
        size,
        rect_widget: RectWidget,
        bounding_box: BoundingBox,
        verifier: str,
        grid_view_controller: GridViewController,
        color=(255, 0, 0),
    ):
        super().__init__(
            pos,
            size,
            pen=pg.mkPen(color, width=3, style=QtCore.Qt.PenStyle.DashLine),
            invertible=True,
            rotatable=False,
            removable=False,
            sideScalers=True,
        )
        
        self._bounding_box = bounding_box
        self._rect_widget = rect_widget
        self._verifier = verifier
        self._grid_view_controller = grid_view_controller
        self._color = color
        self._text_item = None
        self._view = view
        self._dirty = False
        
        # Add scale handles (for resizing)
        self.addScaleHandle([1, 0], [0, 1])
        self.addScaleHandle([0, 1], [1, 0])
        
        # Add translate handle (for moving)
        self.addTranslateHandle([0.5, 0.5])
        
        # Connect signals for removal & box change
        self.sigRemoveRequested.connect(self._remove_view_items)
        self.sigRegionChanged.connect(self._update_text_item)
        self.sigRegionChangeFinished.connect(self._update_bounding_box_bounds)
        self.sigRegionChanged.connect(self._dirty)


        # Initialize the text item
        self._update_text_item()

        # Add the graphical bounding box and its label text item to the view
        self._add_view_items()

        
        
        self._menu = QtWidgets.QMenu()
        self._setup_menu()
        
        self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)
        self.sigClicked.connect(lambda bbox, ev: self._rect_widget.clicked.emit(self._rect_widget, ev))  # Pass click event to rect
    
    @property
    def label(self):
        """
        Get the label for the graphical bounding box.
        """
        return self._bounding_box.label
    
    def _setup_menu(self):
        """
        Set up the context menu for the bounding box.
        """
        self._menu.addAction("Change concept", self._do_change_concept)
        self._menu.addAction("Change part", self._do_change_part)
        self._menu.addSeparator()
        self._menu.addAction("Delete", self._do_delete)
    
    def contextMenuEvent(self, ev):
        """
        Show the context menu.
        """
        self._menu.popup(ev.screenPos())

    def _do_delete(self):
        """
        Delete (clicked from context menu).
        """
        self._grid_view_controller.select(self._rect_widget)
        self._grid_view_controller.delete_selected()
    
    def _do_change_concept(self):
        """
        Change concept (clicked from context menu).
        """
        concept, ok = QtWidgets.QInputDialog.getItem(
            self._grid_view_controller._graphics_view,
            "Change concept",
            "Concept:",
            get_kb_concepts()
        )
        
        if not ok:
            return
        
        self._grid_view_controller.select(self._rect_widget)
        self._grid_view_controller.apply_label(concept, "")
    
    def _do_change_part(self):
        """
        Change part (clicked from context menu).
        """
        part, ok = QtWidgets.QInputDialog.getItem(
            self._grid_view_controller._graphics_view,
            "Change part",
            "Part:",
            get_kb_parts()
        )
        
        if not ok:
            return
        
        self._grid_view_controller.select(self._rect_widget)
        self._grid_view_controller.apply_label("", part)

    def _keep_in_bounds(self):
        """
        Keep the bounding box in the bounds of the image. Will move the box if it is out of bounds.
        """
        x, y = self.pos()
        w, h = self.size()
        h = -h  # Fix negative height

        min_x = 0
        max_x = self._rect_widget.image_width - w

        min_y = h
        max_y = self._rect_widget.image_height

        if x < min_x or y < min_y or x > max_x or y > max_y:
            self.setPos(min(max_x, max(min_x, x)), min(max_y, max(min_y, y)))

    @property
    def is_selected(self):
        return self._rect_widget.is_selected

    def _dirty(self):
        self._dirty = True

    def _update_bounding_box_bounds(self):
        # Keep the bounding box in the bounds of the image
        self._keep_in_bounds()
        
        x, y, w, h = self._get_box()
        y = self._rect_widget.image_height - y
        self.localization.set_box(x, y, w, h)
        self.localization.rect.update_roi_pic()

    def _add_view_items(self):
        """
        Add the graphical bounding box and its label to the view.
        """
        self._view.addItem(self)
        self._view.addItem(self.text_item)

    def _remove_view_items(self, _):
        """
        Remove the graphical bounding box and its label from the view.
        """
        self._view.removeItem(self)
        if self._text_item is not None:
            self._view.removeItem(self._text_item)

    def _get_box(self) -> Tuple[int, int, int, int]:
        """
        Get the bounding box coordinates.
        
        Returns:
            A tuple (x, y, width, height) where x and y are the top left corner of the box.
        """
        x, y = self.pos()
        w, h = self.size()

        # Need to convert box coordinates to account for positive or
        # negative width/height values from pyqtgraph ROI object
        if h > 0:
            y = y + h
        if w < 0:
            x = x + w

        return x, y, np.abs(w), np.abs(h)

    @property
    def text_item(self) -> pg.TextItem:
        """
        Get the text item for the graphical bounding box. Creates the text item if it doesn't exist.
        """
        if self._text_item is None:  # Create the text item
            self._text_item = pg.TextItem(
                text=self.label, color=np.array(self._color) / 2, fill=(200, 200, 200)
            )
        return self._text_item

    def _update_text_item(self):
        """
        Update the text item position and text.
        """
        pos = self.pos()
        size = self.size()
        
        x = pos.x()
        y = pos.y()
        width = size[0]
        height = size[1]
        
        # Keep in bounds
        if width < 0:
            x -= np.abs(width)
        if height < 0:
            y -= np.abs(height)

        self.text_item.setText(self.label)
        self.text_item.setPos(x, y)


class GraphicalBoundingBoxController:
    def __init__(
        self,
        graphics_view: pg.GraphicsView,
        grid_view_controller: GridViewController,
        localization=None,
        all_labels=[],
        verifier=None,
    ):
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

        self.grid_view_controller = grid_view_controller

    def update_labels(self):
        for box in self.boxes:
            if box.is_selected:
                box.update_label()

    def add_annotation(self, obj_idx, rect):
        for idx, localization in enumerate(rect.localizations):
            if localization.deleted:
                continue
            selected_loc = idx == obj_idx

            # Set color of the box
            color = (52, 161, 235)  # Nice light blue
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
                bb = GraphicalBoundingBox(
                    self.view_box,
                    [xmin, height - ymin],
                    [xmax - xmin, -1 * (ymax - ymin)],
                    localization.rect,
                    localization,
                    self.verifier,
                    self.grid_view_controller,
                    color=color,
                    label=label,
                )

                # Add it to the list
                self.boxes.append(bb)

        self.localization = rect.localizations[obj_idx]

    def save_all(self, verifier):
        for box in self.boxes:
            if box.dirty:
                box.localization.push_changes(verifier)

    def map_pos_to_item(self, pos):
        pt = self.view_box.mapSceneToView(pos)
        pt = self.view_box.mapFromViewToItem(self.roi_detail, pt)
        return pt

    def clear(self):
        for box in self.boxes:
            box.remove(None)
        self.boxes = []
