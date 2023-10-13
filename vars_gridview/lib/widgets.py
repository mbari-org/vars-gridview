# -*- coding: utf-8 -*-
"""
widgets.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

import datetime
from typing import List, Optional
from uuid import UUID

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.m3 import operations
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.models import BoundingBox, ImageSource
from vars_gridview.lib.settings import SettingsManager
from vars_gridview.lib.util import get_timestamp


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.pyqtSignal(object)
    
    clicked = QtCore.pyqtSignal(object, object)  # self, event

    def __init__(self, image_source: ImageSource, bounding_box: BoundingBox, clicked_slot: callable, parent=None):
        super().__init__(parent=parent)
        
        self._image_source = image_source
        self._bounding_box = bounding_box
        self.clicked.connect(clicked_slot)

        # self.localizations = localizations
        # self.image = image
        # self.ancillary_data = ancillary_data
        # self.video_data = video_data
        # self.localization_index = localization_index

        self.label_height = 30
        self.border_size = 4
        self.roi_dimensions = [240, 240]
        self.zoom = 0.5
        self._boundingRect = QtCore.QRect()
        
        self.background_color = QtCore.Qt.GlobalColor.darkGray
        self.hover_color = QtCore.Qt.GlobalColor.lightGray
        
        self.is_last_selected = False
        self.is_selected = False

        self._pixmap = None
        self.update_pixmap()

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
        # self.localization.deleted = value

    def delete(self, observation: bool = False) -> bool:
        """
        Delete this rect widget and its associated localization. If observation is True, delete the entire observation instead.
        
        Args:
            observation: If True, delete the entire observation instead of just the association.
        
        Returns:
            True if the rect widget was deleted successfully, False otherwise.
        """
        # TODO: Replace this
        # if self.deleted:  # Don't delete twice
        #     raise ValueError("This rect widget has already been deleted")
        
        # if observation:
        #     try:
        #         operations.delete_observation(self.observation_uuid)
        #         self.deleted = True
        #     except Exception as e:
        #         LOGGER.error(f"Error deleting observation {self.observation_uuid} from rect widget: {e}")
        # else:
        #     try:
        #         operations.delete_association(self.association_uuid)
        #         self.deleted = True
        #     except Exception as e:
        #         LOGGER.error(f"Error deleting association {self.association_uuid} from rect widget: {e}")
        
        # return self.deleted

    @property
    def imaged_moment_uuid(self) -> UUID:
        """
        Get the UUID of the imaged moment associated with this rect widget.
        """
        return self._bounding_box.association.observation.imaged_moment.uuid

    @property
    def observation_uuid(self) -> UUID:
        """
        Get the UUID of the observation associated with this rect widget.
        """
        return self._bounding_box.association.observation.uuid
    
    @property
    def association_uuid(self) -> str:
        """
        Get the UUID of the association associated with this rect widget.
        """
        return self._bounding_box.association.uuid

    def update_pixmap(self):
        """
        Update the pixmap for this rect widget.
        """
        # Get the full image
        self._full_image = self._image_source.get_display_image()
        
        # Crop it
        crop_image = self._full_image[self._bounding_box.y_slice, self._bounding_box.x_slice, :]
        
        self._pixmap = self._get_padded_pixmap(crop_image)
        
        self.update()

    @property
    def image_width(self):
        return self._image_source.width

    @property
    def image_height(self):
        return self._image_source.height

    def annotation_datetime(self) -> Optional[datetime.datetime]:
        video_start_datetime = self.video_data["video_start_timestamp"]

        elapsed_time_millis = self.video_data.get("index_elapsed_time_millis", None)
        timecode = self.video_data.get("index_timecode", None)
        recorded_timestamp = self.video_data.get("index_recorded_timestamp", None)

        # Get annotation video time index
        return get_timestamp(video_start_datetime, recorded_timestamp, elapsed_time_millis, timecode)

    @staticmethod
    def convert_to_q_image(image) -> QtGui.QImage:
        """
        Convert an OpenCV image to a QImage.
        
        Args:
            image: Image to convert. Must be in BGR format.
        
        Returns:
            Converted QImage.
        """
        height, width, bytes_per_component = image.shape
        bytes_per_line = bytes_per_component * width
        
        q_img = QtGui.QImage(
            cv2.cvtColor(image, cv2.COLOR_BGR2RGB), 
            width, 
            height, 
            bytes_per_line, 
            QtGui.QImage.Format.Format_RGB888
        )

        return q_img

    def update_zoom(self, zoom):
        self.zoom = zoom
        self.boundingRect()
        self.updateGeometry()

    def get_full_image(self):
        return np.rot90(self._full_image, 3, (0, 1))

    @property
    def label(self) -> str:
        """
        Get the text label for this rect widget.
        """
        return self._bounding_box.label

    def boundingRect(self):
        # Scale and zoom
        width = self.zoom * (self.roi_dimensions[0] + self.border_size * 2)
        height = self.zoom * (self.roi_dimensions[1] + self.label_height + self.border_size * 2)

        thumb_widget_rect = QtCore.QRectF(0.0, 0.0, width, height)
        self._boundingRect = thumb_widget_rect

        return thumb_widget_rect

    @property
    def is_verified(self) -> bool:
        """
        Check if the bounding box for this rect widget is verified.
        
        Returns:
            True if the bounding box is verified, False otherwise.
        """
        return self._bounding_box.metadata.get("verifier", None) is not None

    def sizeHint(self, which, constraint=QtCore.QSizeF()):
        return self._boundingRect.size()

    def _get_padded_pixmap(self, crop_image: np.ndarray):
        """
        Get a padded pixmap of the cropped image.
        
        Args:
            crop_image: Image to crop as an OpenCV numpy array.
        """
        height, width, _ = crop_image.shape
        
        if height >= width:
            scale = self.roi_dimensions[0] / height
        else:
            scale = self.roi_dimensions[0] / width
        
        new_width = int(width * scale) - 2 * self.border_size
        new_height = int(height * scale) - 2 * self.border_size
        crop_image = cv2.resize(crop_image, (new_width, new_height))

        # Center ROI on dimensions
        w_pad = int((self.roi_dimensions[0] - new_width) / 2)
        h_pad = int((self.roi_dimensions[1] - new_height) / 2)

        # Add border
        crop_image = cv2.copyMakeBorder(
            crop_image,
            h_pad,
            h_pad,
            w_pad,
            w_pad,
            cv2.BORDER_CONSTANT,
            value=(45, 35, 25),
        )

        # Convert OpenCV image to QImage
        q_image = RectWidget.convert_to_q_image(crop_image)
        
        # Convert QImage to QPixmap
        pixmap = QtGui.QPixmap.fromImage(q_image)
        
        return pixmap

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
                    int(self.boundingRect().width() + 4),
                    int(self.boundingRect().height() + 4),
                ),
                QtGui.QColor(61, 174, 233, 255),
            )

        # Fill background if verified
        if self.is_verified:
            painter.fillRect(
                QtCore.QRect(
                    0,
                    0,
                    int(self.boundingRect().width()),
                    int(self.boundingRect().height()),
                ),
                color_for_concept(self.label),
            )
            
        # Fill label
        painter.fillRect(
            QtCore.QRect(
                int(self.zoom * self.border_size),
                int(self.zoom * (self.border_size + self._pixmap.rect().height())),
                int(self.zoom * self._pixmap.rect().width()),
                int(self.zoom * self.label_height),
            ),
            color_for_concept(self.label),
        )

        # Draw image
        painter.setBackgroundMode(QtCore.Qt.BGMode.TransparentMode)
        painter.drawPixmap(
            QtCore.QRect(
                int(self.zoom * self.border_size),
                int(self.zoom * self.border_size),
                int(self.zoom * self._pixmap.rect().width()),
                int(self.zoom * self._pixmap.rect().height()),
            ),
            self._pixmap,
            self._pixmap.rect(),
        )

        # Draw text
        text_rect = QtCore.QRect(
            0,
            int(self.zoom * (self._pixmap.rect().y() + self._pixmap.rect().height())),
            int(self.zoom * self._pixmap.rect().width()),
            int(self.zoom * self.label_height),
        )
        
        # Set font
        settings = SettingsManager.get_instance()
        font = QtGui.QFont(
            'Arial', 
            settings.label_font_size.value, 
            QtGui.QFont.Weight.Bold, 
            False
        )
        painter.setFont(font)

        painter.drawText(
            text_rect, 
            QtCore.Qt.AlignmentFlag.AlignCenter, 
            self.label
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self, event)
