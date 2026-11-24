"""Single-localization tile widget for the image mosaic grid."""

from __future__ import annotations

import itertools
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import cv2
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets, sip
from PyQt6.QtCore import QThreadPool
from requests import HTTPError
from scipy.spatial.distance import cosine

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.common.time import get_timestamp
from vars_gridview.lib.config.constants import ICONS_DIR, get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.lib.vision.display_adjust import (
    ColourCorrector,
    DisplayAdjustment,
    adjust_source,
    adjust_thumbnail,
)
from vars_gridview.lib.vision.image_utils import color_for_concept
from vars_gridview.services.roi_service import RoiService

if TYPE_CHECKING:
    from vars_gridview.lib.vision.embedding import Embedding


# Crops whose source step (fringes / colour) is kept, so a brightness,
# contrast or sharpen change only redoes the cheap thumbnail step. ~170 KB
# each (240 x 240 BGR): ~90 MB at the cap, a few screenfuls of tiles.
MAX_CACHED_SOURCES = 512
_TILE_IDS = itertools.count()
_TILE_RENDER_POOL: QThreadPool | None = None


def _tile_render_pool() -> QThreadPool:
    """Pool for building adjusted tile pictures, apart from the global pool so
    they don't queue behind image downloads."""
    global _TILE_RENDER_POOL
    if _TILE_RENDER_POOL is None:
        _TILE_RENDER_POOL = QThreadPool()
        _TILE_RENDER_POOL.setMaxThreadCount(
            max(2, QtCore.QThread.idealThreadCount() // 2)
        )
    return _TILE_RENDER_POOL


class DisplayContext:
    """How tiles are drawn, shared by every tile of a mosaic.

    Changing it bumps :attr:`version`; a tile whose pixmap was built for an
    older version rebuilds it the next time it is *painted*. Qt only paints
    tiles that are on screen, so turning on colour correction for a page of
    thousands of tiles costs only the visible ones, and the rest are done as
    they're scrolled to. With any adjustment on, the rebuild runs on a worker
    thread and the tile keeps its old picture until the new one is ready.
    """

    def __init__(self) -> None:
        self.adjustment = DisplayAdjustment()
        self.corrector = ColourCorrector()
        self.version = 0
        # tile id -> SourceEntry; touched only on the GUI thread.
        self._sources: OrderedDict[int, SourceEntry] = OrderedDict()

    def source_key(self, frame_key: object) -> tuple:
        """What the source step's result depends on, besides the crop."""
        a = self.adjustment
        if not a.needs_source_pixels:
            return ()
        return (
            a.fix_fringes,
            a.colour_correct,
            a.local_contrast if a.colour_correct else 0.0,
            a.colour_correct and self.corrector.has_frame(frame_key),
        )

    def cached_source(
        self, tile_id: int, roi: np.ndarray, key: tuple
    ) -> SourceEntry | None:
        entry = self._sources.get(tile_id)
        if entry is None or entry.roi is not roi or entry.key != key:
            return None
        self._sources.move_to_end(tile_id)
        return entry

    def store_source(self, tile_id: int, entry: SourceEntry) -> None:
        self._sources[tile_id] = entry
        self._sources.move_to_end(tile_id)
        while len(self._sources) > MAX_CACHED_SOURCES:
            self._sources.popitem(last=False)

    def forget_source(self, tile_id: int) -> None:
        self._sources.pop(tile_id, None)

    def set_adjustment(self, adjustment: DisplayAdjustment) -> bool:
        """Apply *adjustment*; True if anything changed."""
        if adjustment == self.adjustment:
            return False
        self.adjustment = adjustment
        self.corrector.set_local_contrast(adjustment.local_contrast)
        self.version += 1
        return True

    def invalidate(self) -> None:
        """Rebuild every tile on its next paint (e.g. new frame colour data)."""
        self.version += 1


_DEFAULT_DISPLAY_CONTEXT = DisplayContext()
_BLANK_PIXMAPS: dict[tuple[int, int], QtGui.QPixmap] = {}
_CHECKMARK_PIXMAPS: dict[tuple[int, int], QtGui.QPixmap] = {}


def _blank_pixmap(width: int, height: int) -> QtGui.QPixmap:
    """One shared placeholder per size, instead of building (resize, pad,
    convert) a black image for every tile of a large page."""
    key = (max(1, int(width)), max(1, int(height)))
    pixmap = _BLANK_PIXMAPS.get(key)
    if pixmap is None:
        pixmap = QtGui.QPixmap(*key)
        pixmap.fill(QtGui.QColor(25, 35, 45))
        _BLANK_PIXMAPS[key] = pixmap
    return pixmap


def _checkmark_pixmap(width: int, height: int) -> QtGui.QPixmap:
    """The training checkmark, loaded and scaled once per size rather than on
    every paint of every training tile."""
    key = (max(1, int(width)), max(1, int(height)))
    pixmap = _CHECKMARK_PIXMAPS.get(key)
    if pixmap is None:
        pixmap = QtGui.QPixmap(str(ICONS_DIR / "checkmark.png")).scaled(
            key[0], key[1], QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )
        _CHECKMARK_PIXMAPS[key] = pixmap
    return pixmap


class SourceEntry:
    """A crop after the source step: scaled to fit the tile (or to the tile's
    resolution, for a large crop), with fringes / colour applied."""

    __slots__ = ("key", "roi", "scale", "thumb")

    def __init__(self, roi: np.ndarray, key: tuple, thumb: np.ndarray, scale: float):
        self.roi = roi  # the crop it was made from (compared by identity)
        self.key = key
        self.thumb = thumb
        self.scale = scale


def _normalise_roi(roi: np.ndarray | None, width: int, height: int) -> np.ndarray:
    """A 3-channel BGR image; a black one for an empty or missing crop."""
    # Some backends can return an empty ROI for tiny/degenerate boxes while zooming.
    # Fallback to a blank image so we do not divide by zero when computing scale.
    if roi is None or roi.ndim < 2 or roi.shape[0] <= 0 or roi.shape[1] <= 0:
        return np.zeros((height, width, 3), dtype=np.uint8)
    if roi.ndim == 2:
        return cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
    if roi.ndim == 3 and roi.shape[2] == 4:
        return cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)
    return roi


def _source_step(
    roi: np.ndarray,
    adjustment: DisplayAdjustment,
    corrector: ColourCorrector | None,
    frame_key: object,
    width: int,
    height: int,
) -> tuple[np.ndarray, float]:
    """Scale *roi* to fit (width, height), applying fringes / colour on the
    way. Returns the scaled crop and the scale factor."""
    roi = _normalise_roi(roi, width, height)
    roi_height, roi_width = roi.shape[:2]
    scale = min(width / roi_width, height / roi_height)
    if adjustment.needs_source_pixels:
        # Colour / fringes work on the crop at no more than the tile's
        # resolution: full detail for a small crop, and a large crop is
        # shrunk first so the work stays per-tile cheap.
        if scale < 1:
            roi = cv2.resize(
                roi, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA
            )
            upscale = 1.0
        else:
            upscale = scale
        roi = adjust_source(np.ascontiguousarray(roi), adjustment, corrector, frame_key)
        if upscale != 1.0:
            roi = cv2.resize(roi, (0, 0), fx=upscale, fy=upscale)
    elif scale < 1:
        roi = cv2.resize(roi, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        roi = cv2.resize(roi, (0, 0), fx=scale, fy=scale)
    return roi, scale


def _finish_step(
    thumb: np.ndarray,
    adjustment: DisplayAdjustment,
    scale: float,
    width: int,
    height: int,
) -> QtGui.QImage:
    """Sharpen / brightness / contrast, pad to (width, height), as a QImage
    (safe to build off the GUI thread; only QPixmap isn't)."""
    if not adjustment.is_neutral:
        thumb = adjust_thumbnail(thumb, adjustment, enlargement=max(scale, 1.0))
    pad_x = (width - thumb.shape[1]) // 2
    pad_y = (height - thumb.shape[0]) // 2
    padded = cv2.copyMakeBorder(
        thumb, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=(45, 35, 25)
    )
    rgb = np.ascontiguousarray(cv2.cvtColor(padded, cv2.COLOR_BGR2RGB))
    rows, cols = rgb.shape[:2]
    return QtGui.QImage(
        rgb.data, cols, rows, 3 * cols, QtGui.QImage.Format.Format_RGB888
    ).copy()  # own the pixels; rgb is freed on return


def render_tile(
    roi: np.ndarray,
    adjustment: DisplayAdjustment,
    corrector: ColourCorrector | None,
    frame_key: object,
    width: int,
    height: int,
    source: SourceEntry | None = None,
    source_key: tuple = (),
) -> tuple[QtGui.QImage, SourceEntry | None]:
    """A tile's picture for *adjustment*. Reuses *source* (the crop after the
    expensive source step) when given; returns the image and, when the source
    step ran with adjustments, its result for caching. Thread-safe."""
    new_source = None
    if source is not None:
        thumb, scale = source.thumb, source.scale
    else:
        thumb, scale = _source_step(
            roi, adjustment, corrector, frame_key, width, height
        )
        if adjustment.needs_source_pixels:
            new_source = SourceEntry(roi, source_key, thumb, scale)
    return _finish_step(thumb, adjustment, scale, width, height), new_source


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.pyqtSignal(object)
    roiRefreshed = QtCore.pyqtSignal(object)  # self

    clicked = QtCore.pyqtSignal(object, object)  # self, event
    similaritySort = QtCore.pyqtSignal(object, bool)  # self, same_class_only
    label = QtCore.pyqtSignal(object)  # self
    verify = QtCore.pyqtSignal(object)  # self
    markForTraining = QtCore.pyqtSignal(object)  # self
    deleteRequested = QtCore.pyqtSignal(object)  # self
    verifyAndMarkTrainingRequested = QtCore.pyqtSignal(object)  # self

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
        roi_service: RoiService | None = None,
        parent=None,
        text_label: str = "rect widget",
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        video_url: str | None = None,
        elapsed_time_millis: int | None = None,
        preload_roi: bool = True,
        settings: AppSettings | None = None,
    ) -> None:
        QtWidgets.QGraphicsWidget.__init__(self, parent)
        self._settings = settings or get_settings()

        self.associations = associations
        self.source_url = source_url
        self.is_image = is_image
        self.video_url = video_url
        self.elapsed_time_millis = elapsed_time_millis
        self.ancillary_data = ancillary_data
        self.video_data = video_data
        self.localization_index = association_index
        self._zoom = self._settings.gui_zoom.value
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
        self._roi_service = roi_service
        self._source_image_width: int | None = None
        self._source_image_height: int | None = None
        self._cache_source_dimensions_from_metadata()

        self.roi = None
        self.pic = None
        self._display = _DEFAULT_DISPLAY_CONTEXT
        self._tile_id = next(_TILE_IDS)
        # Pixmap needs (re)building from self.roi at the next paint; and the
        # display version it was built for.
        self._pic_dirty = False
        self._pic_version = -1
        # Bumped whenever the picture must be rebuilt for a reason other than
        # the display version (new crop, new display context): with the
        # display version it identifies the picture wanted now.
        self._pic_generation = 0
        # The (version, generation) a worker is building, if any.
        self._render_token: tuple[int, int] | None = None
        self._roi_loaded = False
        self._embedding = None
        self._embedding_box: tuple | None = None  # box the embedding was made for
        self._embedding_space: str | None = None  # model that made it
        # Box the current ROI image was cropped from (embeddings computed from
        # the image are only valid for that box), and the box asked for by the
        # refresh in flight, per generation.
        self._roi_box: tuple | None = None
        self._pending_roi_box: tuple[int, tuple | None] | None = None
        self._embedding_refresh_generation = 0
        if preload_roi:
            self.update_roi_pic()
        else:
            # Paint a cheap placeholder immediately, then fetch ROI asynchronously.
            self.roi = np.zeros((self.picdims[1], self.picdims[0], 3), dtype=np.uint8)
            self.pic = _blank_pixmap(self.picdims[0], self.picdims[1])

        self._clicked_slot = clicked_slot
        self._similarity_sort_slot = similarity_sort_slot
        self._label_slot = label_slot
        self._verify_slot = verify_slot
        self._mark_training_slot = mark_training_slot

        self._deleted = False  # Flag to indicate if this rect widget has been deleted. Used to prevent double deletion.
        self._roi_refresh_generation = 0
        self._roi_batch_generation = 0
        self._roi_refresh_timer = QtCore.QTimer(self)
        self._roi_refresh_timer.setSingleShot(True)
        self._roi_refresh_timer.timeout.connect(self._start_roi_refresh_worker)

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

    def get_image(
        self, should_cancel: Callable[[], bool] | None = None
    ) -> np.ndarray | None:
        """Return the full source image for this ROI, or ``None`` on error.

        Args:
            should_cancel: Passed through to
                :meth:`RoiService.fetch_full_image` so a stale request can
                stop retrying once it's no longer wanted.
        """
        if self._roi_service is None:
            LOGGER.error("ROI service is not configured")
            return None
        try:
            image = self._roi_service.fetch_full_image(
                self.source_url,
                self.elapsed_time_millis if not self.is_image else None,
                should_cancel=should_cancel,
            )
            if image is None:
                return None
            self.set_source_image_dimensions(image.shape[1], image.shape[0])
        except HTTPError as e:
            LOGGER.error(f"Failed to load image from {self.source_url}: {e}")
            return None
        except Exception as e:  # noqa: BLE001
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
        if value:
            self._display.forget_source(self._tile_id)

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
        """Whether this tile has an embedding of its *current* box.

        An embedding records the box it was made from; once the box changes
        (edited here, or in the image view through another tile of the same
        frame) the embedding no longer counts, and the tile is ranked last
        until a new one is computed.
        """
        return (
            self._embedding is not None and self._embedding_box == self._current_box()
        )

    @property
    def embedding_space(self) -> str | None:
        """Name of the model that made the cached embedding (None if unknown)."""
        return self._embedding_space

    @property
    def roi_box(self) -> tuple | None:
        """The box the current ROI image was cropped from."""
        return self._roi_box if self._roi_box is not None else self._current_box()

    @property
    def roi_loaded(self) -> bool:
        """Whether this tile currently has a fetched (non-placeholder) ROI image."""
        return self._roi_loaded

    def invalidate_embedding_cache(self) -> None:
        """Clear any cached embedding so it can be recomputed lazily."""
        self._embedding = None
        self._embedding_box = None
        self._embedding_space = None

    def cache_embedding(
        self, embedding, *, box: tuple | None = None, space: str | None = None
    ) -> None:
        """Store an embedding for this tile.

        Args:
            embedding: The vector.
            box: The box it was computed from: the box the image was cropped
                from, or the box sent to the vector database. Defaults to the
                current box. A vector of an older box is then never mistaken
                for one of the current box.
            space: Name of the model that made it.
        """
        self._embedding = embedding
        self._embedding_box = tuple(box) if box is not None else self._current_box()
        self._embedding_space = space

    def _current_box(self) -> tuple | None:
        try:
            return tuple(self.association.box)
        except Exception:  # noqa: BLE001
            return None

    def _invalidate_embedding_if_box_changed(self) -> None:
        """A newly loaded image only makes the embedding stale if the box
        moved: the first load of a tile whose embedding came from the vector
        database (or was computed earlier) must not throw it away."""
        if self._embedding is not None and self._embedding_box == self._current_box():
            return
        self.invalidate_embedding_cache()

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

        box = self.roi_box
        self.cache_embedding(
            self._embedding_model.embed(self.roi[:, :, ::-1]),
            box=box,
            space=getattr(self._embedding_model, "model_name", None),
        )

    @staticmethod
    def _embed_roi(embedding_model: Embedding, roi: np.ndarray):
        """Compute embedding from a pre-fetched ROI image."""
        return embedding_model.embed(roi[:, :, ::-1])

    def get_roi(self) -> np.ndarray:
        """
        Get the region of interest for this rect widget.
        """
        if self._roi_service is None:
            raise RuntimeError("ROI service is not configured")
        image = self._roi_service.fetch_roi(
            self.association,
            self.source_url,
            None if self.is_image else self.elapsed_time_millis,
            scale_x=1.0 if self.is_image else self._scale_x,
            scale_y=1.0 if self.is_image else self._scale_y,
        )
        if image is None:
            raise RuntimeError("Failed to fetch ROI image")
        return image

    def set_display_context(self, context: DisplayContext) -> None:
        """Share *context* (see :class:`DisplayContext`) with this tile."""
        self._display = context
        self._mark_pic_dirty()

    @property
    def frame_key(self) -> tuple:
        """Identifies the frame this tile was cropped from (for per-frame
        colour correction)."""
        return (self.source_url, None if self.is_image else self.elapsed_time_millis)

    def _mark_pic_dirty(self) -> None:
        self._pic_dirty = True
        self._pic_generation += 1
        self.update()

    def update_roi_pic(self):
        self._roi_box = self._current_box()
        self.roi = self.get_roi()
        self._roi_loaded = True
        self._mark_pic_dirty()
        # Bulk precompute is coordinated by ImageMosaic.
        self._invalidate_embedding_if_box_changed()
        self.update()

    def request_roi_refresh(self, *, debounce: bool = True) -> None:
        """Refresh ROI image asynchronously and apply only the latest result.

        Args:
            debounce: If ``True`` (default), coalesce rapid repeated calls
                (e.g. from interactive box editing) behind a short delay.
                Bulk loaders that call this once per tile, with nothing to
                coalesce against, should pass ``False`` to skip it.
        """
        if debounce:
            self.request_roi_refresh_debounced()
        else:
            self._start_roi_refresh_worker()

    def request_roi_refresh_debounced(self, debounce_ms: int = 120) -> None:
        """Schedule an ROI refresh after a short debounce delay."""
        self._roi_refresh_timer.start(max(0, int(debounce_ms)))

    def _start_roi_refresh_worker(self) -> None:
        """Start an async ROI refresh worker for the latest request."""
        self._roi_refresh_generation += 1
        generation = self._roi_refresh_generation
        self._pending_roi_box = (generation, self._current_box())

        worker = Worker(self._fetch_roi_with_generation, generation)
        worker.signals.result.connect(self._on_async_roi_refresh_result)
        worker.signals.error.connect(self._on_async_roi_refresh_error)
        QThreadPool.globalInstance().start(worker)

    def _fetch_roi_with_generation(self, generation: int):
        # Failures come back as a result too, so they carry their generation:
        # a late failure of an older request must not replace a newer image.
        try:
            return generation, self.get_roi(), None
        except Exception as exc:  # noqa: BLE001
            return generation, None, exc

    @QtCore.pyqtSlot(object)
    def _on_async_roi_refresh_result(self, payload) -> None:
        generation, roi, error = payload
        if error is not None:
            if generation == self._roi_refresh_generation:
                self._on_async_roi_refresh_error((type(error), error, ""))
            return
        self._apply_async_roi_refresh(generation, roi)

    def _apply_async_roi_refresh(self, generation: int, roi) -> None:
        if generation != self._roi_refresh_generation:
            return
        pending = self._pending_roi_box
        self._roi_box = (
            pending[1]
            if pending is not None and pending[0] == generation
            else self._current_box()
        )
        self.roi = roi
        self._roi_loaded = True
        # Built at the next paint: tiles that load off screen cost nothing
        # until they're scrolled to.
        self._mark_pic_dirty()
        # Bulk precompute is coordinated by ImageMosaic.
        self._invalidate_embedding_if_box_changed()
        self.roiRefreshed.emit(self)

    @QtCore.pyqtSlot(tuple)
    def _on_async_roi_refresh_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Error refreshing ROI for {self.association.uuid}: {message}")

        # Keep tile UI stable and allow mosaic loading progress to continue.
        placeholder = self._make_placeholder_roi()
        self.roi = placeholder
        self._roi_loaded = False
        self._pic_dirty = False
        self._pic_generation += 1  # drop any adjusted picture still being built
        self._display.forget_source(self._tile_id)
        self.pic = self.getpic(placeholder, adjust=False)
        # A stored (vector database) embedding doesn't need the image; keep it.
        self._invalidate_embedding_if_box_changed()
        self.update()
        self.roiRefreshed.emit(self)

    def request_embedding_refresh(self) -> None:
        """Refresh this tile's embedding asynchronously from the current ROI."""
        if self._embedding_model is None or self.roi is None or not self._roi_loaded:
            return

        self._embedding_refresh_generation += 1
        generation = self._embedding_refresh_generation
        roi_copy = self.roi.copy()
        self._embedding_refresh_stamp = (
            self.roi_box,
            getattr(self._embedding_model, "model_name", None),
        )

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
        box, space = self._embedding_refresh_stamp
        self.cache_embedding(embedding, box=box, space=space)

    def embedding_distance(self, other: RectWidget) -> float:
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
        return self._source_image_width

    @property
    def image_height(self) -> int | None:
        return self._source_image_height

    def set_source_image_dimensions(
        self, width: int | None, height: int | None
    ) -> None:
        """Cache source-frame dimensions for non-blocking bound checks."""
        if width is None or height is None:
            return
        if width <= 0 or height <= 0:
            return
        self._source_image_width = width
        self._source_image_height = height

    def _cache_source_dimensions_from_metadata(self) -> None:
        """Initialize source-frame dimensions from query metadata when available."""
        width = self.video_data.get("video_width")
        height = self.video_data.get("video_height")
        if isinstance(width, int) and isinstance(height, int):
            self.set_source_image_dimensions(width, height)

    def annotation_datetime(self) -> datetime | None:
        video_start_datetime = self.video_data["video_start_timestamp"]

        elapsed_time_millis = self.video_data.get("index_elapsed_time_millis", None)
        timecode = self.video_data.get("index_timecode", None)
        recorded_timestamp = self.video_data.get("index_recorded_timestamp", None)

        # Get annotation video time index
        return get_timestamp(
            video_start_datetime, recorded_timestamp, elapsed_time_millis, timecode
        )

    def update_zoom(self, zoom: float):
        self._zoom = max(float(zoom), 0.01)
        self.boundingRect()
        self.updateGeometry()

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

    def sizeHint(self, which, constraint=None):
        return self.boundingRect().size()

    def getpic(self, roi: np.ndarray, *, adjust: bool = True) -> QtGui.QPixmap:
        """
        Get the scaled and padded pixmap for the given ROI.

        Fits the ROI into a square of size picdims, scaling it up or down as necessary.
        Then, pads the ROI with a border to fit the square. With *adjust*, the
        display adjustments (colour correction, fringes, sharpen,
        brightness/contrast -- see :class:`DisplayContext`) are applied on the
        way; the ROI itself is never modified.

        Args:
            roi: The ROI to get the pixmap for.
            adjust: Apply the current display adjustments.

        Returns:
            The scaled and padded pixmap.
        """
        adjustment = self._display.adjustment if adjust else DisplayAdjustment()
        image, _source = render_tile(
            roi,
            adjustment,
            self._display.corrector,
            self.frame_key,
            self.pic_width,
            self.pic_height,
        )
        return QtGui.QPixmap.fromImage(image)

    def _refresh_pic(self) -> None:
        """Bring :attr:`pic` up to date with the crop and display settings.

        With no adjustments it's a resize and pad, done right here. Otherwise
        the work (up to ~25 ms a tile with fringes) runs on a worker and the
        tile shows its old picture until the new one arrives; the result of
        the expensive source step is cached, so a brightness / contrast /
        sharpen change only redoes the cheap last step.
        """
        adjustment = self._display.adjustment
        token = (self._display.version, self._pic_generation)
        if adjustment.is_neutral:
            try:
                self.pic = self.getpic(self.roi)
            except Exception as exc:  # noqa: BLE001 -- never fail a paint
                LOGGER.error(f"Could not render tile {self.association.uuid}: {exc}")
                self.pic = _blank_pixmap(self.pic_width, self.pic_height)
            self._pic_dirty = False
            self._pic_version = token[0]
            self._render_token = None
            return
        if self._render_token == token:
            return  # already being built
        self._render_token = token
        source_key = self._display.source_key(self.frame_key)
        worker = Worker(
            self._render_with_token,
            token,
            self.roi,
            adjustment,
            self._display.corrector,
            self.frame_key,
            self.pic_width,
            self.pic_height,
            self._display.cached_source(self._tile_id, self.roi, source_key),
            source_key,
        )
        worker.signals.result.connect(self._on_render_result)
        _tile_render_pool().start(worker)

    @staticmethod
    def _render_with_token(token: tuple[int, int], roi: np.ndarray, *args):
        # Failures come back as a result too, so they carry their token.
        try:
            image, source = render_tile(roi, *args)
            return token, roi, image, source, None
        except Exception as exc:  # noqa: BLE001
            return token, roi, None, None, exc

    @QtCore.pyqtSlot(object)
    def _on_render_result(self, payload) -> None:
        if sip.isdeleted(self) or self._deleted:
            return
        token, roi, image, source, error = payload
        if self._render_token == token:
            self._render_token = None
        if source is not None and roi is self.roi:
            self._display.store_source(self._tile_id, source)
        if token != (self._display.version, self._pic_generation):
            self.update()  # superseded; the next paint asks for the current one
            return
        if error is not None:
            LOGGER.error(f"Could not render tile {self.association.uuid}: {error}")
            try:
                self.pic = self.getpic(self.roi, adjust=False)
            except Exception:  # noqa: BLE001
                self.pic = _blank_pixmap(self.pic_width, self.pic_height)
        else:
            self.pic = QtGui.QPixmap.fromImage(image)
        self._pic_dirty = False
        self._pic_version = token[0]
        self.update()

    def _make_placeholder_roi(self) -> np.ndarray:
        """Build a fallback ROI image when loading fails."""
        width = max(1, int(self.picdims[0]))
        height = max(1, int(self.picdims[1]))
        placeholder = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            placeholder,
            "ROI unavailable",
            (10, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (180, 180, 180),
            1,
            cv2.LINE_AA,
        )
        return placeholder

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
                QtGui.QColor.fromString(self._settings.selection_highlight_color.value),
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

        # (Re)build the pixmap if the ROI or the display settings changed
        # since it was made -- only ever for tiles actually being painted.
        if self._roi_loaded and (
            self._pic_dirty or self._pic_version != self._display.version
        ):
            self._refresh_pic()

        # Draw image
        painter.setBackgroundMode(QtCore.Qt.BGMode.TransparentMode)
        painter.drawPixmap(
            self.pic_rect,
            self.pic,
            self.pic.rect(),
        )

        # Draw green check mark if marked for training
        if self.is_training:
            check_rect = self.checkmark_rect
            painter.drawPixmap(
                check_rect, _checkmark_pixmap(check_rect.width(), check_rect.height())
            )

        # Set font
        font = QtGui.QFont(
            "Arial",
            self._settings.label_font_size.value,
            QtGui.QFont.Weight.Bold,
            False,
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
            lambda: self.verifyAndMarkTrainingRequested.emit(self)
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

        # Available when this tile has an embedding (e.g. from the VARS
        # vector database) or one can be computed: the embedding service is
        # connected and the image has loaded.
        can_find_similar = self.has_cached_embedding or (
            self._embedding_model is not None and self._roi_loaded
        )
        similarity_sort.setEnabled(can_find_similar)
        similarity_sort_same_label.setEnabled(can_find_similar)
        if not can_find_similar:
            similarity_sort.setToolTip(
                "This tile has no embedding: it isn't in the VARS vector "
                "database and the embedding service isn't on."
            )

        # Delete: the whole selection if this tile is part of it (as in a
        # file browser), otherwise just this tile. Asks before deleting.
        menu.addSeparator()
        delete_action = menu.addAction("Delete...")
        delete_action.triggered.connect(lambda: self.deleteRequested.emit(self))

        menu.setToolTipsVisible(True)
        menu.exec(event.screenPos())
