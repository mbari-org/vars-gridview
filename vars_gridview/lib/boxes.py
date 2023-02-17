# -*- coding: utf-8 -*-
"""
rectlabel.py -- Tools to implement a labeling UI for bounding boxes in images
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore

from vars_gridview.lib.log import LOGGER


class BoundingBox(pg.RectROI):
    def __init__(
        self,
        view,
        pos,
        size,
        rect,
        localization,
        verifier,
        color=(255, 0, 0),
        label="ROI",
    ):
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
        # GUI things
        self.addScaleHandle([1, 0], [0, 1])
        self.addScaleHandle([0, 1], [1, 0])
        self.addTranslateHandle([0.5, 0.5])
        self.sigRemoveRequested.connect(self.remove)
        self.sigRegionChanged.connect(self.draw_name)

        self.sigRegionChangeFinished.connect(self.check_bounds)

        self.label = label
        self.color = color
        self.textItem = None

        self.view = view
        self.view.addItem(self)
        self.draw_name()

        self.verifier = verifier

        self.dirty = False
        self.sigRegionChanged.connect(self._dirty)

        self.sigRegionChangeFinished.connect(self.update_localization_box)

        self.localization = localization
        self.rect = rect

    def check_bounds(self):
        x, y = self.pos()
        w, h = self.size()
        h = -h  # Fix negative height

        min_x = 0
        max_x = self.rect.image_width - w

        min_y = h
        max_y = self.rect.image_height

        if x < min_x or y < min_y or x > max_x or y > max_y:
            self.setPos(min(max_x, max(min_x, x)), min(max_y, max(min_y, y)))

    @property
    def is_selected(self):
        return self.rect.is_selected

    def _dirty(self):
        self.dirty = True

    def update_localization_box(self):
        x, y, w, h = self.get_box()
        y = self.rect.image_height - y
        self.localization.set_box(x, y, w, h)
        self.localization.rect.update_roi_pic()

    def update_label(self):
        self.label = self.localization.text_label
        self.draw_name()

    def remove(self, dummy):
        self.view.removeItem(self.textItem)
        self.view.removeItem(self)

    def get_box(self):
        x, y = self.pos()
        w, h = self.size()

        # need to convert box coordinates to account for positive or
        # negative width/height values from pyqtgraph roi object
        if h > 0:
            y = y + h
        if w < 0:
            x = x + w

        return [x, y, np.abs(w), np.abs(h)]

    def draw_name(self):
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
                text=self.label, color=np.array(self.color) / 2, fill=(200, 200, 200)
            )
            self.textItem.setPos(x, y)
            self.view.addItem(self.textItem)
        else:
            self.textItem.setText(self.label)
            self.textItem.setPos(x, y)

    def mouseClickEvent(self, ev):
        if (
            ev.button() == QtCore.Qt.MouseButton.RightButton
        ):  # Capture and ignore right clicks
            pass


class BoxHandler:
    def __init__(
        self,
        graphics_view,
        image_mosaic,
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

        self.image_mosaic = image_mosaic

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
                bb = BoundingBox(
                    self.view_box,
                    [xmin, height - ymin],
                    [xmax - xmin, -1 * (ymax - ymin)],
                    rect,
                    localization,
                    self.verifier,
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
