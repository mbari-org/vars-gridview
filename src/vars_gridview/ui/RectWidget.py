"""
RectWidget class for displaying a single localization in the grid view.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from requests import HTTPError
from scipy.spatial.distance import cosine

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.constants import ICONS_DIR, SETTINGS
from vars_gridview.lib.embedding import Embedding
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.utils import fetch_image, get_timestamp


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.pyqtSignal(object)

    clicked = QtCore.pyqtSignal(object, object)  # self, event
    similaritySort = QtCore.pyqtSignal(object, bool)  # self, same_class_only

    def __init__(
        self,
        associations: List[BoundingBoxAssociation],
        source_url: str,
        ancillary_data: dict,
        video_data: dict,
        association_index: int,
        clicked_slot: callable,
        similarity_sort_slot: callable,
        embedding_model: Optional[Embedding] = None,
        parent=None,
        text_label="rect widget",
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        elapsed_time_millis: Optional[int] = None,
    ):
        QtWidgets.QGraphicsWidget.__init__(self, parent)

        self.associations = associations
        self.source_url = source_url
        self.elapsed_time_millis = elapsed_time_millis
        self.ancillary_data = ancillary_data
        self.video_data = video_data
        self.localization_index = association_index
        self._zoom = SETTINGS.gui_zoom.value
        self._scale_x = scale_x
        self._scale_y = scale_y

        self.labelheight = 30
        self.bordersize = 6
        self.outlinesize = 12
        self.picdims = [240, 240]
        self.text_label = text_label
        self._boundingRect = QtCore.QRect()
        self.background_color = QtGui.QColor.fromRgb(25, 35, 45)
        self.hover_color = QtCore.Qt.GlobalColor.lightGray

        self.is_last_selected = False
        self.is_selected = False

        self._embedding_model = embedding_model

        self.roi = None
        self.pic = None
        self._embedding = None
        self.update_roi_pic()

        self._clicked_slot = clicked_slot
        self._similarity_sort_slot = similarity_sort_slot

        self.association.rect_widget = self  # back-reference

        self._deleted = False  # Flag to indicate if this rect widget has been deleted. Used to prevent double deletion.

        self._connect()

    def _connect(self) -> None:
        """
        Connect signals and slots.
        """
        self.clicked.connect(self._clicked_slot)
        self.similaritySort.connect(self._similarity_sort_slot)

    def get_image(self) -> Optional[np.ndarray]:
        """
        Get the image data for this rect widget.
        """
        try:
            image = fetch_image(self.source_url, self.elapsed_time_millis)
        except HTTPError as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Could not load image",
                f"Failed to load image from {self.source_url}: {e}",
            )
            return None
        except Exception as e:
            LOGGER.error(f"Unexpected error while fetching image: {e}")
            return None

        if self._scale_x != 1.0 or self._scale_y != 1.0:
            image = cv2.resize(
                image,
                None,
                fx=self._scale_x,
                fy=self._scale_y,
                interpolation=cv2.INTER_CUBIC,  # see OpenCV docs: https://docs.opencv.org/4.8.0/da/d54/group__imgproc__transform.html#ga47a974309e9102f5f08231edc7e7529d
            )

        return image

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
        self.association.deleted = value

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
            observation_uuid = self.association.observation.uuid
            try:
                operations.delete_observation(observation_uuid)
                self.deleted = True
            except Exception as e:
                LOGGER.error(
                    f"Error deleting observation {observation_uuid} from rect widget: {e}"
                )
        else:
            association_uuid = self.association.uuid
            try:
                operations.delete_association(association_uuid)
                self.deleted = True
            except Exception as e:
                LOGGER.error(
                    f"Error deleting association {association_uuid} from rect widget: {e}"
                )

        return self.deleted

    @property
    def imaged_moment_uuid(self) -> UUID:
        """
        Get the UUID of the imaged moment associated with this rect widget.
        """
        return self.association.observation.imaged_moment_uuid

    @property
    def observation_uuid(self) -> UUID:
        """
        Get the UUID of the observation associated with this rect widget.
        """
        return self.association.observation.uuid

    @property
    def association_uuid(self) -> UUID:
        """
        Get the UUID of the association associated with this rect widget.
        """
        return self.association.uuid

    @property
    def embedding(self):
        if self._embedding is None:
            self.update_embedding()
        return self._embedding

    def update_embedding(self):
        """
        Update the embedding value.

        Raises:
            ValueError: If the embedding model is None.
        """
        if self._embedding_model is None:
            raise ValueError(
                "Embedding model is not provided; cannot compute embedding"
            )

        self._embedding = self._embedding_model.embed(
            self.get_roi()[::-1],
        )

    def get_roi(self) -> np.ndarray:
        """
        Get the region of interest for this rect widget.
        """
        # Get the image from the Skimmer
        response = operations.crop(
            self.source_url,
            round(self.association.x / self._scale_x),
            round(self.association.y / self._scale_y),
            round(self.association.xf / self._scale_x),
            round(self.association.yf / self._scale_y),
            ms=self.elapsed_time_millis,
        )

        # Decode the image
        image = cv2.imdecode(
            np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR
        )
        return image

    def update_roi_pic(self):
        self.roi = self.get_roi()
        self.pic = self.getpic(self.roi)
        if self._embedding_model is not None:
            self.update_embedding()
        self.update()

    def embedding_distance(self, other: "RectWidget") -> float:
        """
        Calculate the embedding distance between this rect widget and another.

        Args:
            other: The other rect widget to compare to.

        Returns:
            The embedding distance between the two rect widgets.
        """
        return cosine(self.embedding, other.embedding)

    def update_embedding_model(self, embedding_model: Embedding):
        self._embedding_model = embedding_model

    @property
    def is_verified(self) -> bool:
        return self.association.verified

    @property
    def is_training(self) -> bool:
        return self.association.is_training

    @property
    def association(self) -> BoundingBoxAssociation:
        return self.associations[self.localization_index]

    @property
    def image_width(self) -> Optional[int]:
        image = self.get_image()
        if image is None:
            return None
        return image.shape[1]

    @property
    def image_height(self) -> Optional[int]:
        image = self.get_image()
        if image is None:
            return None
        return image.shape[0]

    def annotation_datetime(self) -> Optional[datetime]:
        video_start_datetime = self.video_data["video_start_timestamp"]

        elapsed_time_millis = self.video_data.get("index_elapsed_time_millis", None)
        timecode = self.video_data.get("index_timecode", None)
        recorded_timestamp = self.video_data.get("index_recorded_timestamp", None)

        # Get annotation video time index
        return get_timestamp(
            video_start_datetime, recorded_timestamp, elapsed_time_millis, timecode
        )

    def toqimage(self, img):
        height, width, bytesPerComponent = img.shape
        bytesPerLine = bytesPerComponent * width
        cv2.cvtColor(img, cv2.COLOR_BGR2RGB, img)
        qimg = QtGui.QImage(
            img.copy(), width, height, bytesPerLine, QtGui.QImage.Format.Format_RGB888
        )

        return qimg

    def update_zoom(self, zoom: int):
        self._zoom = zoom
        self.boundingRect()
        self.updateGeometry()

    def get_full_image(self) -> Optional[np.ndarray]:
        """
        Get the full image that this ROI comes from.

        Returns:
            Optional[np.ndarray]: The full image, or None if an error occurs.
        """
        try:
            return np.rot90(self.get_image(), 3, (0, 1))
        except Exception as e:
            LOGGER.error(f"Error getting full image: {e}")
            return None

    @property
    def outline_x(self):
        return 0

    @property
    def outline_y(self):
        return 0

    @property
    def outline_width(self):
        return self.picdims[0] + self.bordersize * 2 + self.outlinesize * 2

    @property
    def outline_height(self):
        return (
            self.picdims[1]
            + self.labelheight
            + self.bordersize * 2
            + self.outlinesize * 2
        )

    @property
    def border_x(self):
        return self.outline_x + self.outlinesize

    @property
    def border_y(self):
        return self.outline_y + self.outlinesize

    @property
    def border_width(self):
        return self.outline_width - self.outlinesize * 2

    @property
    def border_height(self):
        return self.outline_height - self.outlinesize * 2

    @property
    def pic_x(self):
        return self.border_x + self.bordersize

    @property
    def pic_y(self):
        return self.border_y + self.bordersize

    @property
    def pic_width(self):
        return self.picdims[0]

    @property
    def pic_height(self):
        return self.picdims[1]

    @property
    def label_x(self):
        return self.pic_x

    @property
    def label_y(self):
        return self.pic_y + self.pic_height

    @property
    def label_width(self):
        return self.pic_width

    @property
    def label_height(self):
        return self.labelheight

    def scale_rect(self, rect: QtCore.QRectF) -> QtCore.QRect:
        return QtCore.QRect(
            round(rect.x() * self._zoom),
            round(rect.y() * self._zoom),
            round(rect.width() * self._zoom),
            round(rect.height() * self._zoom),
        )

    @property
    def outline_rect(self):
        rect = QtCore.QRectF(
            self.outline_x,
            self.outline_y,
            self.outline_width,
            self.outline_height,
        )
        return self.scale_rect(rect)

    @property
    def border_rect(self):
        rect = QtCore.QRectF(
            self.border_x,
            self.border_y,
            self.border_width,
            self.border_height,
        )
        return self.scale_rect(rect)

    @property
    def pic_rect(self):
        rect = QtCore.QRectF(
            self.pic_x,
            self.pic_y,
            self.pic_width,
            self.pic_height,
        )
        return self.scale_rect(rect)

    @property
    def label_rect(self):
        rect = QtCore.QRectF(
            self.label_x,
            self.label_y,
            self.label_width,
            self.label_height,
        )
        return self.scale_rect(rect)

    @property
    def checkmark_rect(self) -> QtCore.QRect:
        label_rect = self.label_rect
        padding = 2
        rect = QtCore.QRect(
            label_rect.x() + padding,
            label_rect.y() + padding,
            label_rect.height() - padding * 2,
            label_rect.height() - padding * 2,
        )
        return rect

    def boundingRect(self):
        return QtCore.QRectF(
            self._zoom * self.outline_x,
            self._zoom * self.outline_y,
            self._zoom * self.outline_width,
            self._zoom * self.outline_height,
        )

    def sizeHint(self, which, constraint=QtCore.QSizeF()):
        return self.boundingRect().size()

    def getpic(self, roi: np.ndarray) -> QtGui.QPixmap:
        """
        Get the scaled and padded pixmap for the given ROI.

        Fits the ROI into a square of size picdims, scaling it up or down as necessary.
        Then, pads the ROI with a border to fit the square.

        Args:
            roi: The ROI to get the pixmap for.

        Returns:
            The scaled and padded pixmap.
        """
        # Get relevant dimensions
        roi_height, roi_width, _ = roi.shape
        max_width = self.pic_width
        max_height = self.pic_height

        # Scale the ROI to fit the square
        scale = min(max_width / roi_width, max_height / roi_height)
        roi = cv2.resize(roi, (0, 0), fx=scale, fy=scale)

        # Pad the image with a border
        pad_x = (max_width - roi.shape[1]) // 2
        pad_y = (max_height - roi.shape[0]) // 2
        roi_padded = cv2.copyMakeBorder(
            roi,
            pad_y,
            pad_y,
            pad_x,
            pad_x,
            cv2.BORDER_CONSTANT,
            value=(45, 35, 25),
        )

        # Convert to Qt pixmap
        qimg = self.toqimage(roi_padded)
        orpixmap = QtGui.QPixmap.fromImage(qimg)
        return orpixmap

    def paint(self, painter, option, widget):
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setBrush(QtCore.Qt.GlobalColor.black)
        painter.setPen(pen)

        def color_for_concept(concept: str):
            hash = sum(map(ord, concept)) << 5
            color = QtGui.QColor()
            color.setHsl(round((hash % 360) / 360 * 255), 255, 217, 255)
            return color

        # Fill outline background if selected
        if self.is_selected:
            painter.fillRect(
                self.outline_rect,
                QtGui.QColor.fromString(SETTINGS.selection_highlight_color.value),
            )

        # Fill border background if verified
        if self.is_verified:
            painter.fillRect(
                self.border_rect,
                color_for_concept(self.text_label),
            )
        else:
            painter.fillRect(
                self.border_rect,
                self.background_color,
            )

        # Fill label background
        painter.fillRect(
            self.label_rect,
            color_for_concept(self.text_label),
        )

        # Draw image
        painter.setBackgroundMode(QtCore.Qt.BGMode.TransparentMode)
        painter.drawPixmap(
            self.pic_rect,
            self.pic,
            self.pic.rect(),
        )

        # Draw green check mark if marked for training
        if self.is_training:
            check_mark = QtGui.QPixmap(str(ICONS_DIR / "checkmark.png"))
            check_rect = self.checkmark_rect
            check_mark = check_mark.scaled(
                check_rect.width(),
                check_rect.height(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            )
            painter.drawPixmap(check_rect, check_mark)

        # Set font
        font = QtGui.QFont(
            "Arial", SETTINGS.label_font_size.value, QtGui.QFont.Weight.Bold, False
        )
        painter.setFont(font)

        # Draw label text
        painter.drawText(
            self.label_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.text_label
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self, event)
        else:
            self.handle_right_click(event)

    def handle_right_click(self, event):
        """
        Handle a right click event. Open a context menu with options.
        """
        menu = QtWidgets.QMenu()
        similarity_sort = menu.addAction("Find similar")
        similarity_sort.triggered.connect(lambda: self.similaritySort.emit(self, False))
        similarity_sort_same_label = menu.addAction("Find similar with same label")
        similarity_sort_same_label.triggered.connect(
            lambda: self.similaritySort.emit(self, True)
        )
        no_embedding_model = self._embedding_model is None
        similarity_sort.setDisabled(no_embedding_model)
        similarity_sort_same_label.setDisabled(no_embedding_model)
        menu.exec(event.screenPos())
