"""Single-localization tile widget for the image mosaic grid."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QThreadPool
from requests import HTTPError
from scipy.spatial.distance import cosine

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.constants import ICONS_DIR, SETTINGS
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.runnables import Worker
from vars_gridview.lib.utils import color_for_concept, fetch_image, get_timestamp

if TYPE_CHECKING:
    from vars_gridview.lib.embedding import Embedding


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.pyqtSignal(object)
    roiRefreshed = QtCore.pyqtSignal(object)  # self

    clicked = QtCore.pyqtSignal(object, object)  # self, event
    similaritySort = QtCore.pyqtSignal(object, bool)  # self, same_class_only
    label = QtCore.pyqtSignal(object)  # self
    verify = QtCore.pyqtSignal(object)  # self
    markForTraining = QtCore.pyqtSignal(object)  # self

    def __init__(
        self,
        associations: list[BoundingBoxAssociation],
        source_url: str,
        is_image: bool,
        ancillary_data: dict,
        video_data: dict,
        association_index: int,
        clicked_slot: callable,
        similarity_sort_slot: callable,
        label_slot: callable,
        verify_slot: callable,
        mark_training_slot: callable,
        embedding_model: Embedding | None = None,
        parent=None,
        text_label: str = "rect widget",
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        video_url: str | None = None,
        elapsed_time_millis: int | None = None,
        preload_roi: bool = True,
    ) -> None:
        QtWidgets.QGraphicsWidget.__init__(self, parent)

        self.associations = associations
        self.source_url = source_url
        self.is_image = is_image
        self.video_url = video_url
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
        self._roi_loaded = False
        self._embedding = None
        self._embedding_refresh_generation = 0
        if preload_roi:
            self.update_roi_pic()
        else:
            # Paint a cheap placeholder immediately, then fetch ROI asynchronously.
            self.roi = np.zeros((self.picdims[1], self.picdims[0], 3), dtype=np.uint8)
            self.pic = self.getpic(self.roi)

        self._clicked_slot = clicked_slot
        self._similarity_sort_slot = similarity_sort_slot
        self._label_slot = label_slot
        self._verify_slot = verify_slot
        self._mark_training_slot = mark_training_slot

        self._deleted = False  # Flag to indicate if this rect widget has been deleted. Used to prevent double deletion.
        self._roi_refresh_generation = 0
        self._roi_batch_generation = 0

        self._connect()

    def _connect(self) -> None:
        """
        Connect signals and slots.
        """
        self.clicked.connect(self._clicked_slot)
        self.similaritySort.connect(self._similarity_sort_slot)
        self.label.connect(self._label_slot)
        self.verify.connect(self._verify_slot)
        self.markForTraining.connect(self._mark_training_slot)

    def get_image(self) -> np.ndarray | None:
        """Return the full source image for this ROI, or ``None`` on error."""
        try:
            image = fetch_image(
                self.source_url, self.elapsed_time_millis if not self.is_image else None
            )
        except HTTPError as e:
            LOGGER.error(f"Failed to load image from {self.source_url}: {e}")
            return None
        except Exception as e:
            LOGGER.error(f"Unexpected error while fetching image: {e}")
            return None

        if not self.is_image and (self._scale_x != 1.0 or self._scale_y != 1.0):
            image = cv2.resize(
                image,
                None,
                fx=self._scale_x,
                fy=self._scale_y,
                interpolation=cv2.INTER_CUBIC,  # see OpenCV docs: https://docs.opencv.org/4.8.0/da/d54/group__imgproc__transform.html#ga47a974309e9102f5f08231edc7e7529d
            )

        return image

    @property
    def scale_x(self) -> float:
        """
        Get the scale factor in the x direction.
        """
        return self._scale_x

    @property
    def scale_y(self) -> float:
        """
        Get the scale factor in the y direction.
        """
        return self._scale_y

    @property
    def deleted(self) -> bool:
        """Whether this rect widget (and its association) has been deleted."""
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
        Mark this rect widget as deleted.

        Network deletion is intentionally owned by higher-level controller/service
        code (ImageMosaic/AnnotationController). This method only updates local
        state so view objects never perform direct API mutations.

        Args:
            observation: If True, delete the entire observation instead of just the association.

        Returns:
            True if the rect widget was deleted successfully, False otherwise.
        """
        if self.deleted:  # Don't delete twice
            raise ValueError("This rect widget has already been deleted")

        _ = observation
        self.deleted = True

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

    @property
    def has_cached_embedding(self) -> bool:
        """Whether this tile already has a computed embedding."""
        return self._embedding is not None

    @property
    def roi_loaded(self) -> bool:
        """Whether this tile currently has a fetched (non-placeholder) ROI image."""
        return self._roi_loaded

    def invalidate_embedding_cache(self) -> None:
        """Clear any cached embedding so it can be recomputed lazily."""
        self._embedding = None

    def cache_embedding(self, embedding) -> None:
        """Store an externally computed embedding payload for this tile."""
        self._embedding = embedding

    @property
    def roi_batch_generation(self) -> int:
        """Current ROI loading batch generation assigned by the mosaic."""
        return self._roi_batch_generation

    def assign_roi_batch_generation(self, generation: int) -> None:
        """Assign the ROI batch generation used to ignore stale refresh callbacks."""
        self._roi_batch_generation = generation

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

        if not self._roi_loaded or self.roi is None:
            raise RuntimeError("ROI image is not loaded yet; cannot compute embedding")

        self._embedding = self._embedding_model.embed(
            self.roi[:, :, ::-1],
        )

    @staticmethod
    def _embed_roi(embedding_model: Embedding, roi: np.ndarray):
        """Compute embedding from a pre-fetched ROI image."""
        return embedding_model.embed(roi[:, :, ::-1])

    def get_roi(self) -> np.ndarray:
        """
        Get the region of interest for this rect widget.
        """
        if self.is_image:
            # If image, get ROI directly
            response = operations.crop(
                self.source_url,
                round(self.association.x),
                round(self.association.y),
                round(self.association.xf),
                round(self.association.yf),
            )
        else:
            # Else, get ROI from video frame (scaling according to scale factors)
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
        self._roi_loaded = True
        self.pic = self.getpic(self.roi)
        # Invalidate cached embedding; bulk precompute is coordinated by ImageMosaic.
        self.invalidate_embedding_cache()
        self.update()

    def request_roi_refresh(self) -> None:
        """Refresh ROI image asynchronously and apply only the latest result."""
        self._roi_refresh_generation += 1
        generation = self._roi_refresh_generation

        worker = Worker(self._fetch_roi_with_generation, generation)
        worker.signals.result.connect(self._on_async_roi_refresh_result)
        worker.signals.error.connect(
            lambda err: LOGGER.error(
                f"Error refreshing ROI for {self.association.uuid}: {err[1]}"
            )
        )
        QThreadPool.globalInstance().start(worker)

    def _fetch_roi_with_generation(self, generation: int):
        return generation, self.get_roi()

    @QtCore.pyqtSlot(object)
    def _on_async_roi_refresh_result(self, payload) -> None:
        generation, roi = payload
        self._apply_async_roi_refresh(generation, roi)

    def _apply_async_roi_refresh(self, generation: int, roi) -> None:
        if generation != self._roi_refresh_generation:
            return
        self.roi = roi
        self._roi_loaded = True
        self.pic = self.getpic(roi)
        # Invalidate cached embedding; bulk precompute is coordinated by ImageMosaic.
        self.invalidate_embedding_cache()
        self.update()
        self.roiRefreshed.emit(self)

    def request_embedding_refresh(self) -> None:
        """Refresh this tile's embedding asynchronously from the current ROI."""
        if self._embedding_model is None or self.roi is None or not self._roi_loaded:
            return

        self._embedding_refresh_generation += 1
        generation = self._embedding_refresh_generation
        roi_copy = self.roi.copy()

        worker = Worker(
            self._embed_roi_with_generation,
            self._embedding_model,
            roi_copy,
            generation,
        )
        worker.signals.result.connect(self._on_async_embedding_refresh_result)
        worker.signals.error.connect(
            lambda err: LOGGER.error(
                f"Error refreshing embedding for {self.association.uuid}: {err[1]}"
            )
        )
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _embed_roi_with_generation(
        embedding_model: Embedding,
        roi: np.ndarray,
        generation: int,
    ):
        return generation, RectWidget._embed_roi(embedding_model, roi)

    @QtCore.pyqtSlot(object)
    def _on_async_embedding_refresh_result(self, payload) -> None:
        generation, embedding = payload
        self._apply_async_embedding_refresh(generation, embedding)

    def _apply_async_embedding_refresh(self, generation: int, embedding) -> None:
        if generation != self._embedding_refresh_generation:
            return
        self._embedding = embedding

    def embedding_distance(self, other: "RectWidget") -> float:
        """
        Calculate the embedding distance between this rect widget and another.

        Args:
            other: The other rect widget to compare to.

        Returns:
            The embedding distance between the two rect widgets.
        """
        return cosine(self.embedding, other.embedding)

    def update_embedding_model(self, embedding_model: Embedding | None):
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
    def image_width(self) -> int | None:
        image = self.get_image()
        if image is None:
            return None
        return image.shape[1]

    @property
    def image_height(self) -> int | None:
        image = self.get_image()
        if image is None:
            return None
        return image.shape[0]

    def annotation_datetime(self) -> datetime | None:
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

    def update_zoom(self, zoom: float):
        self._zoom = max(float(zoom), 0.01)
        self.boundingRect()
        self.updateGeometry()

    def get_full_image(self) -> np.ndarray | None:
        """Return the full source image rotated 90° CCW, or ``None`` on error."""
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
        max_width = self.pic_width
        max_height = self.pic_height

        # Some backends can return an empty ROI for tiny/degenerate boxes while zooming.
        # Fallback to a blank image so we do not divide by zero when computing scale.
        if roi is None or roi.ndim < 2 or roi.shape[0] <= 0 or roi.shape[1] <= 0:
            roi = np.zeros((max_height, max_width, 3), dtype=np.uint8)

        # Ensure we always hand a 3-channel image to the Qt conversion path.
        if roi.ndim == 2:
            roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        elif roi.ndim == 3 and roi.shape[2] == 4:
            roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)

        roi_height, roi_width = roi.shape[:2]

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

        def color_for_concept_local(concept: str) -> QtGui.QColor:
            return color_for_concept(concept)

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
                color_for_concept_local(self.text_label),
            )
        else:
            painter.fillRect(
                self.border_rect,
                self.background_color,
            )

        # Fill label background
        painter.fillRect(
            self.label_rect,
            color_for_concept_local(self.text_label),
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

        # Add actions for label, verify, mark for training, and verify + mark for training
        label_action = menu.addAction("Label")
        label_action.triggered.connect(lambda: self.label.emit(self))
        verify_action = menu.addAction("Verify")
        verify_action.triggered.connect(lambda: self.verify.emit(self))
        mark_for_training_action = menu.addAction("Mark Training")
        mark_for_training_action.triggered.connect(
            lambda: self.markForTraining.emit(self)
        )
        verify_and_mark_action = menu.addAction("Verify + Mark Training")
        verify_and_mark_action.triggered.connect(
            lambda: (self.verify.emit(self), self.markForTraining.emit(self))
        )

        # Add separator
        menu.addSeparator()

        # Action to find similar
        similarity_sort = menu.addAction("Find similar")
        similarity_sort.triggered.connect(lambda: self.similaritySort.emit(self, False))

        # Action to find similar with same label
        similarity_sort_same_label = menu.addAction("Find similar with same label")
        similarity_sort_same_label.triggered.connect(
            lambda: self.similaritySort.emit(self, True)
        )

        # Disable similarity sort options if no embedding model is available
        no_embedding_model = self._embedding_model is None
        similarity_sort.setDisabled(no_embedding_model)
        similarity_sort_same_label.setDisabled(no_embedding_model)

        menu.exec(event.screenPos())
