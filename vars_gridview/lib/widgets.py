# -*- coding: utf-8 -*-
"""
widgets.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

import datetime
from typing import List, Optional

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.annotation import VARSLocalization
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.log import LOGGER


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.pyqtSignal(object)
    
    clicked = QtCore.pyqtSignal(object, object)  # self, event

    def __init__(
        self,
        localizations: List[VARSLocalization],
        image: np.ndarray,
        ancillary_data: dict,
        video_data: dict,
        localization_index: int,
        parent=None,
        text_label="rect widget",
    ):
        QtWidgets.QGraphicsWidget.__init__(self, parent)

        self.localizations = localizations
        self.image = image
        self.ancillary_data = ancillary_data
        self.video_data = video_data
        self.localization_index = localization_index

        self.labelheight = 30
        self.bordersize = 4
        self.picdims = [240, 240]
        self.zoom = 0.5
        self.text_label = text_label
        self._boundingRect = QtCore.QRect()
        self.background_color = QtCore.Qt.GlobalColor.darkGray
        self.hover_color = QtCore.Qt.GlobalColor.lightGray
        
        self.is_last_selected = False
        self.is_selected = False

        self.roi = None
        self.pic = None
        self.update_roi_pic()

        self._deleted = False  # Flag to indicate if this rect widget has been deleted. Used to prevent double deletion.

    @property
    def deleted(self) -> bool:
        """
        Check if this rect widget has been deleted.
        """
        return self._deleted
    
    @deleted.setter
    def deleted(self, value: bool) -> None:
        """
        Set the deleted flag for this rect widget and its localization.
        """
        self._deleted = value
        self.localization.deleted = value

    def delete(self, observation: bool = False) -> bool:
        """
        Delete this rect widget and its associated localization. If observation is True, delete the entire observation instead.
        
        Args:
            observation: If True, delete the entire observation instead of just the association.
        
        Returns:
            True if the rect widget was deleted successfully, False otherwise.
        """
        if self.deleted:  # Don't delete twice
            raise ValueError("This rect widget has already been deleted")
        
        if observation:
            try:
                operations.delete_observation(self.observation_uuid)
                self.deleted = True
            except Exception as e:
                LOGGER.error(f"Error deleting observation {self.observation_uuid} from rect widget: {e}")
        else:
            try:
                operations.delete_association(self.association_uuid)
                self.deleted = True
            except Exception as e:
                LOGGER.error(f"Error deleting association {self.association_uuid} from rect widget: {e}")
        
        return self.deleted

    @property
    def observation_uuid(self) -> str:
        """
        Get the UUID of the observation associated with this rect widget.
        """
        return self.localization.observation_uuid
    
    @property
    def association_uuid(self) -> str:
        """
        Get the UUID of the association associated with this rect widget.
        """
        return self.localization.association_uuid

    def update_roi_pic(self):
        self.roi = self.localization.get_roi(self.image)
        self.pic = self.getpic(self.roi)
        self.update()

    @property
    def is_verified(self) -> bool:
        return self.localizations[self.localization_index].verified

    @property
    def localization(self) -> VARSLocalization:
        return self.localizations[self.localization_index]

    @property
    def image_width(self):
        return self.image.shape[1]

    @property
    def image_height(self):
        return self.image.shape[0]

    def annotation_datetime(self) -> Optional[datetime.datetime]:
        video_start_datetime = self.video_data["video_start_timestamp"]

        elapsed_time_millis = self.video_data.get("index_elapsed_time_millis", None)
        timecode = self.video_data.get("index_timecode", None)
        recorded_timestamp = self.video_data.get("index_recorded_timestamp", None)

        # Get annotation video time index
        annotation_datetime = None
        if recorded_timestamp is not None:
            annotation_datetime = recorded_timestamp
        elif elapsed_time_millis is not None:
            annotation_datetime = video_start_datetime + datetime.timedelta(
                milliseconds=int(elapsed_time_millis)
            )
        elif timecode is not None:
            hours, minutes, seconds, frames = map(int, timecode.split(":"))
            annotation_datetime = video_start_datetime + datetime.timedelta(
                hours=hours, minutes=minutes, seconds=seconds
            )
        else:
            raise ValueError("No video time index found")

        return annotation_datetime

    def toqimage(self, img):
        height, width, bytesPerComponent = img.shape
        bytesPerLine = bytesPerComponent * width
        cv2.cvtColor(img, cv2.COLOR_BGR2RGB, img)
        qimg = QtGui.QImage(
            img.copy(), width, height, bytesPerLine, QtGui.QImage.Format.Format_RGB888
        )

        return qimg

    def update_zoom(self, zoom):
        self.zoom = zoom
        self.boundingRect()
        self.updateGeometry()

    def get_full_image(self):
        return np.rot90(self.image, 3, (0, 1))

    def boundingRect(self):
        # scale and zoom
        width = self.zoom * (self.picdims[0] + self.bordersize * 2)
        height = self.zoom * (self.picdims[1] + self.labelheight + self.bordersize * 2)

        thumb_widget_rect = QtCore.QRectF(0.0, 0.0, width, height)
        self._boundingRect = thumb_widget_rect

        return thumb_widget_rect

    def sizeHint(self, which, constraint=QtCore.QSizeF()):
        return self._boundingRect.size()

    def getpic(self, roi):
        height, width, channels = roi.shape
        if height >= width:
            scale = self.picdims[0] / height
        else:
            scale = self.picdims[0] / width
        new_width = int(width * scale) - 2 * self.bordersize
        new_height = int(height * scale) - 2 * self.bordersize
        roi = cv2.resize(roi, (new_width, new_height))

        # center roi on dims
        w_pad = int((self.picdims[0] - new_width) / 2)
        h_pad = int((self.picdims[1] - new_height) / 2)

        roi = cv2.copyMakeBorder(
            roi,
            h_pad,
            h_pad,
            w_pad,
            w_pad,
            cv2.BORDER_CONSTANT,
            value=(45, 35, 25),
        )

        qimg = self.toqimage(roi)
        orpixmap = QtGui.QPixmap.fromImage(qimg)
        return orpixmap

    def paint(self, painter, option, widget):
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setBrush(QtCore.Qt.GlobalColor.black)
        painter.setPen(pen)

        # very simple selection and annotation logic
        if self.is_selected:
            fill_color = QtCore.Qt.GlobalColor.green
        elif self.is_verified:
            fill_color = QtCore.Qt.GlobalColor.yellow
        else:
            fill_color = QtCore.Qt.GlobalColor.darkGray

        def color_for_concept(concept: str):
            hash = sum(map(ord, concept)) << 5
            color = QtGui.QColor()
            color.setHsl(round((hash % 360) / 360 * 255), 255, 217, 255)
            return color
        
        # Fill outline if selected
        if self.is_selected:
            painter.fillRect(
                QtCore.QRect(
                    -2,
                    -2,
                    self.boundingRect().width() + 4,
                    self.boundingRect().height() + 4,
                ),
                QtGui.QColor(61, 174, 233, 255),
            )

        # Fill background if verified
        if self.is_verified:
            painter.fillRect(
                QtCore.QRect(
                    0,
                    0,
                    self.boundingRect().width(),
                    self.boundingRect().height(),
                ),
                color_for_concept(self.text_label),
            )
            
        # Fill label
        painter.fillRect(
            QtCore.QRect(
                int(self.zoom * self.bordersize),
                int(self.zoom * (self.bordersize + self.pic.rect().height())),
                int(self.zoom * self.pic.rect().width()),
                int(self.zoom * self.labelheight),
            ),
            color_for_concept(self.text_label),
        )

        # Draw image
        painter.setBackgroundMode(QtCore.Qt.BGMode.TransparentMode)
        painter.drawPixmap(
            QtCore.QRect(
                int(self.zoom * self.bordersize),
                int(self.zoom * self.bordersize),
                int(self.zoom * self.pic.rect().width()),
                int(self.zoom * self.pic.rect().height()),
            ),
            self.pic,
            self.pic.rect(),
        )

        # Draw text
        text_rect = QtCore.QRect(
            0,
            int(self.zoom * (self.pic.rect().y() + self.pic.rect().height())),
            int(self.zoom * self.pic.rect().width()),
            int(self.zoom * self.labelheight),
        )
        
        # Set font
        font = QtGui.QFont(
            'Arial', int(self.zoom * self.labelheight * 0.5), QtGui.QFont.Weight.Bold, False
        )
        painter.setFont(font)

        painter.drawText(
            text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.text_label
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self, event)
