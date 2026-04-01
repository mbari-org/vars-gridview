"""Image mosaic widget manager.

Manages a grid of :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
tiles, and handles metadata loading, ROI creation, sorting, selection, and
CRUD operations on bounding-box annotations.
"""

from __future__ import annotations

from datetime import datetime
from math import inf
from typing import TYPE_CHECKING, Any, Callable, List, Optional, cast
from uuid import UUID

import numpy as np
from iso8601 import parse_date
from PyQt6 import QtCore, QtGui, QtWidgets
from pydantic import BaseModel

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.config.constants import SETTINGS
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.sorting.sort_methods import SortMethod, SortMethodGroup
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.controllers.selection_model import SelectionModel
from vars_gridview.services.localization_store import LocalizationStore
from vars_gridview.services.roi_loader import RoiLoader
from vars_gridview.ui.dialogs.concept_selection_dialog import ConceptSelectionDialog
from vars_gridview.ui.mosaic.mosaic_view import MosaicView
from vars_gridview.ui.mosaic.rect_widget import RectWidget

if TYPE_CHECKING:
    from vars_gridview.lib.vision.embedding import Embedding
    from vars_gridview.lib.m3.clients import AnnosaurusClient, VampireSquidClient
    from vars_gridview.services.roi_service import RoiService


class Row(BaseModel):
    # Keys
    video_reference_uuid: UUID
    imaged_moment_uuid: UUID
    observation_uuid: UUID
    association_uuid: UUID
    image_reference_uuid: UUID | None

    # Video sequence
    video_sequence_name: str | None
    chief_scientist: str | None
    camera_platform: str | None
    dive_number: str | None  # from cached video reference info

    # Video/video reference
    video_start_timestamp: datetime | None
    video_container: str | None
    video_uri: str | None
    video_width: int | None
    video_height: int | None

    # Imaged moment
    index_elapsed_time_millis: int | None
    index_recorded_timestamp: datetime | None
    index_timecode: str | None

    # Image reference
    image_url: str | None
    image_format: str | None

    # Observation
    observer: str | None
    concept: str | None
    observation_group: str | None

    # Association
    link_name: str | None
    to_concept: str | None
    link_value: str | None

    # Ancillary data
    depth_meters: float | None
    latitude: float | None
    longitude: float | None
    oxygen_ml_per_l: float | None
    pressure_dbar: float | None
    salinity: float | None
    temperature_celsius: float | None
    light_transmission: float | None

    @classmethod
    def parse(cls, headers: list[str], row: list[str]) -> Row:
        """Parse a row of data into a :class:`Row` instance.

        Args:
            headers: Column names from the query result.
            row: Raw string values for one result row.

        Returns:
            Parsed :class:`Row` object.

        Raises:
            pydantic.ValidationError: If any field fails validation.
        """
        # Turn "null" into None
        row = list(map(lambda v: None if v == "null" else v, row))

        # Turn empty fields into None
        row = list(map(lambda v: None if v == "" and v is not None else v, row))

        # Create a dictionary of the row data
        row_dict = dict(zip(headers, row))

        # Parse ISO8601 dates
        if row_dict["index_recorded_timestamp"] is not None:
            row_dict["index_recorded_timestamp"] = parse_date(
                row_dict["index_recorded_timestamp"]
            )
        if row_dict["video_start_timestamp"] is not None:
            row_dict["video_start_timestamp"] = parse_date(
                row_dict["video_start_timestamp"]
            )

        return cls(**row_dict)


class Cancelled(Exception):
    """
    Exception raised when the user cancels an operation.
    """

    pass


class ImageMosaic(QtCore.QObject):
    """Manager for the image-mosaic grid view.

    Populates a :class:`PyQt6.QtWidgets.QGraphicsView` with a grid of
    :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget` tiles sourced from VARS
    annotation query results.  Handles video-sequence metadata prefetching,
    ROI image loading, selection state, and bulk annotation operations.
    """

    stats_changed = QtCore.pyqtSignal(dict)
    similarity_sort_progress = QtCore.pyqtSignal(int, int)
    embedding_precompute_progress = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        graphics_view: QtWidgets.QGraphicsView,
        rect_clicked_slot: Callable[..., None],
        dialog_parent: QtWidgets.QWidget | None = None,
        embedding_model: Embedding | None = None,
        annosaurus_client: AnnosaurusClient | None = None,
        vampire_squid_client: VampireSquidClient | None = None,
        roi_service: RoiService | None = None,
        concept_provider: Callable[[], list[str]] | None = None,
        part_provider: Callable[[], list[str]] | None = None,
        label_action_callback=None,
        verify_action_callback=None,
        mark_training_action_callback=None,
    ) -> None:
        super().__init__()

        # Initialize the graphics
        self._graphics_view = graphics_view
        self._dialog_parent = dialog_parent
        self._mosaic_view = MosaicView(graphics_view)
        self._graphics_view.installEventFilter(self)

        self._rect_clicked_slot = rect_clicked_slot
        self._label_action_callback = label_action_callback
        self._verify_action_callback = verify_action_callback
        self._mark_training_action_callback = mark_training_action_callback
        self._embedding_model = embedding_model
        self._annosaurus_client = annosaurus_client
        self._vampire_squid_client = vampire_squid_client
        self._roi_service = roi_service
        self._concept_provider = concept_provider
        self._part_provider = part_provider

        self._rect_widgets: List[RectWidget] = []
        self._n_columns = 0
        self.selection_model = SelectionModel(parent=self)
        self.selection_model.selection_changed.connect(self._on_selection_changed)

        # Display flags
        self.hide_labeled = False
        self.hide_unlabeled = False
        self.hide_training = False
        self.hide_nontraining = False

        # Non-Qt data store backing metadata and association groups.
        self.store = LocalizationStore()
        self._roi_loader = RoiLoader()
        self.video_reference_uuid_to_mp4_video_reference = {}

        self.n_images = 0
        self.n_localizations = 0
        self._roi_loading_total = 0
        self._roi_loading_done = 0
        self._roi_loading_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._similarity_sort_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._embedding_precompute_dialog: Optional[QtWidgets.QProgressDialog] = None
        self._embedding_precompute_in_progress = False
        self._embedding_precompute_pending = False
        self._embedding_generation = 0
        self._running_embedding_generation = 0
        self._roi_load_generation = 0
        self._roi_loading_pending: list[RectWidget] = []
        self._roi_loading_inflight = 0
        self._roi_loading_max_concurrency = 4

        SETTINGS.gui_zoom.valueChanged.connect(self.zoom_updated)
        self.similarity_sort_progress.connect(self._on_similarity_sort_progress)
        self.embedding_precompute_progress.connect(
            self._on_embedding_precompute_progress
        )

    def configure_services(
        self,
        *,
        annosaurus_client: AnnosaurusClient,
        vampire_squid_client: VampireSquidClient,
        roi_service: RoiService,
    ) -> None:
        """Attach service/client dependencies required for ROI loading."""
        self._annosaurus_client = annosaurus_client
        self._vampire_squid_client = vampire_squid_client
        self._roi_service = roi_service

    @property
    def image_reference_urls(self) -> dict[UUID | None, str | None]:
        return self.store.image_reference_urls

    @property
    def association_groups(
        self,
    ) -> dict[tuple[UUID, UUID | None], list[BoundingBoxAssociation]]:
        return self.store.association_groups

    @property
    def observations(self) -> dict[UUID, Any]:
        return self.store.observations

    @property
    def moment_video_data(self) -> dict[UUID, dict]:
        return self.store.moment_video_data

    @property
    def moment_proxy_data(self) -> dict[UUID, dict | None]:
        return self.store.moment_proxy_data

    @property
    def moment_timestamps(self) -> dict[UUID, object]:
        return self.store.moment_timestamps

    @property
    def video_sequences_by_name(self) -> dict[str, dict | None]:
        return self.store.video_sequences_by_name

    @property
    def moment_ancillary_data(self) -> dict[UUID, dict]:
        return self.store.moment_ancillary_data

    def populate(self, query_headers: list[str], query_rows: list[list[str]]) -> None:
        """Populate the mosaic from raw VARS query output.

        Clears any previous state, parses the rows, fetches ancillary
        metadata from M3, and creates a :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
        for every bounding-box association found.

        Args:
            query_headers: Column names as returned by the query endpoint.
            query_rows: One inner list per result row.
        """
        # Clear derived query data
        self.store.reset_for_query()

        # Clear existing widgets
        self._cancel_pending_roi_loading()
        self._rect_widgets.clear()
        self.selection_model.clear()

        # Parse rows
        rows = []
        for row in query_rows:
            try:
                rows.append(Row.parse(query_headers, row))
            except Exception as e:
                LOGGER.error(f"Error parsing row {row}: {e}")

        try:
            # Populate metadata from the rows
            self._map_metadata(rows)

            # Extract associations into groups
            self._extract_associations(rows)

            # Fetch video sequence data for the given groups
            self._fetch_video_sequence_data()

            # Derive and map proxy image metadata
            self._map_proxy_data(rows)

            # Create the ROI widgets
            self._create_rois()
        except Cancelled:
            LOGGER.info("Image mosaic loading cancelled by user")
            return

    def _map_metadata(self, rows: list[Row]) -> None:
        """Populate internal lookup tables from *rows*."""
        self.store.map_metadata(list(rows))

    def _extract_associations(self, rows: list[Row]) -> None:
        """Extract bounding-box associations from *rows* into association groups."""
        self.store.extract_associations(list(rows))

    def _fetch_video_sequence_data(self) -> None:
        if self._vampire_squid_client is None:
            raise RuntimeError(
                "ImageMosaic is missing VampireSquid client; call configure_services() after login"
            )
        try:
            self._roi_loader.fetch_video_sequence_data(
                vampire_squid_client=self._vampire_squid_client,
                moment_video_data=self.moment_video_data,
                video_sequences_by_name=self.video_sequences_by_name,
            )
        except RuntimeError as exc:
            if str(exc) == "Video sequence fetch cancelled":
                raise Cancelled from exc
            raise

    def _map_proxy_data(self, rows: list[Row]) -> None:
        """Derive proxy video data for each imaged moment in *rows*."""
        self._roi_loader.map_proxy_data(
            rows=list(rows),
            moment_proxy_data=self.moment_proxy_data,
            moment_timestamps=self.moment_timestamps,
            video_sequences_by_name=self.video_sequences_by_name,
        )

    def _create_rois(self) -> None:
        if self._annosaurus_client is None or self._roi_service is None:
            raise RuntimeError(
                "ImageMosaic is missing Annosaurus/ROI services; call configure_services() after login"
            )
        try:
            load_result = self._roi_loader.create_rect_widgets(
                annosaurus_client=self._annosaurus_client,
                roi_service=self._roi_service,
                association_groups=self.association_groups,
                moment_video_data=self.moment_video_data,
                moment_proxy_data=self.moment_proxy_data,
                moment_timestamps=self.moment_timestamps,
                image_reference_urls=self.image_reference_urls,
                moment_ancillary_data=self.moment_ancillary_data,
                rect_clicked_slot=self._rect_clicked_slot,
                similarity_sort_slot=self._similarity_sort_slot,
                rect_label_slot=self._rect_label_slot,
                rect_verify_slot=self._rect_verify_slot,
                rect_mark_training_slot=self._rect_mark_training_slot,
                embedding_model=self._embedding_model,
            )
        except RuntimeError as exc:
            if str(exc) == "ROI creation cancelled":
                raise Cancelled from exc
            raise

        self._rect_widgets = load_result.rect_widgets
        self.n_images = load_result.n_images
        self.n_localizations = load_result.n_localizations
        self._start_async_roi_loading()

        if load_result.failed_association_uuids:
            error_message = "\n".join(
                [str(uuid) for uuid in load_result.failed_association_uuids]
            )
            QtWidgets.QMessageBox.warning(
                self._graphics_view,
                "Failed to Create ROIs",
                f"The following bounding box associations could not be loaded:\n{error_message}",
            )

    def _similarity_sort_slot(self, clicked_rect: RectWidget, same_class_only: bool):
        if not self._rect_widgets:
            return

        self._similarity_sort_dialog = QtWidgets.QProgressDialog(
            "Computing similarity sort...",
            None,
            0,
            len(self._rect_widgets),
            self._graphics_view,
        )
        self._similarity_sort_dialog.setWindowTitle("Sorting")
        self._similarity_sort_dialog.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self._similarity_sort_dialog.setMinimumDuration(0)
        self._similarity_sort_dialog.setValue(0)
        self._similarity_sort_dialog.show()

        worker = Worker(
            self._compute_similarity_sort_order,
            list(self._rect_widgets),
            clicked_rect,
            same_class_only,
            self.similarity_sort_progress.emit,
        )
        worker.signals.result.connect(self._on_similarity_sort_ready)
        worker.signals.error.connect(self._on_similarity_sort_error)
        worker.signals.finished.connect(self._on_similarity_sort_finished)
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.error("Global thread pool unavailable; cannot run similarity sort")
            self._on_similarity_sort_finished()
            return
        pool.start(worker)

    def _rect_label_slot(self, rect: RectWidget):
        concepts = (
            self._concept_provider() if self._concept_provider is not None else []
        )
        parts = self._part_provider() if self._part_provider is not None else []
        opt = ConceptSelectionDialog.pick_concept_and_part(
            parent=self._dialog_parent,
            concepts=concepts,
            parts=parts,
        )
        if opt is None:
            return
        concept, part = opt
        if self._label_action_callback is not None:
            self._label_action_callback(rect, concept, part)
            return
        LOGGER.error("Label action callback is not configured for tile action")

    def _rect_verify_slot(self, rect: RectWidget):
        if self._verify_action_callback is not None:
            self._verify_action_callback(rect)
            return
        LOGGER.error("Verify action callback is not configured for tile action")

    def _rect_mark_training_slot(self, rect: RectWidget):
        if self._mark_training_action_callback is not None:
            self._mark_training_action_callback(rect)
            return
        LOGGER.error("Mark-training action callback is not configured for tile action")

    def update_embedding_model(self, embedding_model: Embedding | None) -> None:
        """Replace the active embedding model and invalidate cached embeddings."""
        model_changed = self._embedding_model is not embedding_model
        self._embedding_model = embedding_model
        if model_changed:
            self._embedding_generation += 1
            if self._embedding_precompute_in_progress:
                # Recompute with the new model after the current worker finishes.
                self._embedding_precompute_pending = embedding_model is not None
        if embedding_model is None:
            self._embedding_precompute_pending = False
        for rect_widget in self._rect_widgets:
            rect_widget.update_embedding_model(embedding_model)
            rect_widget.invalidate_embedding_cache()

    def precompute_embeddings_async(self) -> None:
        """Warm tile embeddings in the background to avoid on-demand UI stalls."""
        if self._embedding_model is None or not self._rect_widgets:
            return
        if self._embedding_precompute_in_progress:
            self._embedding_precompute_pending = True
            return

        targets = [rw for rw in self._rect_widgets if not rw.has_cached_embedding]
        if not targets:
            return

        self._embedding_precompute_dialog = QtWidgets.QProgressDialog(
            "Precomputing embeddings...",
            None,
            0,
            len(targets),
            self._graphics_view,
        )
        self._embedding_precompute_dialog.setWindowTitle("Embeddings")
        self._embedding_precompute_dialog.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self._embedding_precompute_dialog.setMinimumDuration(0)
        self._embedding_precompute_dialog.setValue(0)
        self._embedding_precompute_dialog.show()
        self._embedding_precompute_in_progress = True
        self._running_embedding_generation = self._embedding_generation

        worker = Worker(
            self._compute_embeddings_payload,
            targets,
            self._embedding_model,
            self._running_embedding_generation,
            self.embedding_precompute_progress.emit,
        )
        worker.signals.result.connect(self._on_embeddings_precomputed)
        worker.signals.error.connect(self._on_embeddings_precompute_error)
        worker.signals.finished.connect(self._on_embeddings_precompute_finished)
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            LOGGER.error("Global thread pool unavailable; cannot precompute embeddings")
            self._on_embeddings_precompute_finished()
            return
        pool.start(worker)

    def _start_async_roi_loading(self) -> None:
        if not self._rect_widgets:
            return

        self._cancel_pending_roi_loading()
        self._roi_load_generation += 1
        current_generation = self._roi_load_generation

        self._roi_loading_total = len(self._rect_widgets)
        self._roi_loading_done = 0
        self._roi_loading_dialog = QtWidgets.QProgressDialog(
            "Loading ROI images...",
            None,
            0,
            self._roi_loading_total,
            self._graphics_view,
        )
        self._roi_loading_dialog.setWindowTitle("Loading")
        self._roi_loading_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._roi_loading_dialog.setMinimumDuration(0)
        self._roi_loading_dialog.setValue(0)
        self._roi_loading_dialog.show()

        self._roi_loading_pending = list(self._rect_widgets)
        self._roi_loading_inflight = 0
        self._pump_async_roi_loading(current_generation)

    def _pump_async_roi_loading(self, generation: int) -> None:
        """Start queued ROI refreshes while respecting the concurrency limit."""
        while (
            generation == self._roi_load_generation
            and self._roi_loading_inflight < self._roi_loading_max_concurrency
            and self._roi_loading_pending
        ):
            rw = self._roi_loading_pending.pop(0)
            rw.assign_roi_batch_generation(generation)
            rw.roiRefreshed.connect(self._on_rect_roi_refreshed)
            self._roi_loading_inflight += 1
            rw.request_roi_refresh()

    @QtCore.pyqtSlot(object)
    def _on_rect_roi_refreshed(self, rect_widget: RectWidget) -> None:
        try:
            rect_widget.roiRefreshed.disconnect(self._on_rect_roi_refreshed)
        except Exception:
            pass

        if rect_widget.roi_batch_generation != self._roi_load_generation:
            try:
                rect_widget.roiRefreshed.disconnect(self._on_rect_roi_refreshed)
            except Exception:
                pass
            return

        self._roi_loading_inflight = max(0, self._roi_loading_inflight - 1)
        self._roi_loading_done += 1
        dialog = self._roi_loading_dialog
        if dialog is not None:
            dialog.setValue(self._roi_loading_done)

        self._pump_async_roi_loading(self._roi_load_generation)

        if self._roi_loading_done >= self._roi_loading_total:
            # Guard against re-entrant teardown paths that may clear the dialog.
            if self._roi_loading_dialog is dialog and dialog is not None:
                dialog.close()
                self._roi_loading_dialog = None
            if self._embedding_model is not None:
                # Compute embeddings in a single worker after all ROI images are ready.
                self.precompute_embeddings_async()

    def _cancel_pending_roi_loading(self) -> None:
        """Invalidate in-flight ROI refreshes and close any active loading dialog."""
        self._roi_load_generation += 1
        self._roi_loading_total = 0
        self._roi_loading_done = 0
        self._roi_loading_pending = []
        self._roi_loading_inflight = 0
        if self._roi_loading_dialog is not None:
            self._roi_loading_dialog.close()
            self._roi_loading_dialog = None

    @staticmethod
    def _compute_similarity_sort_order(
        rect_widgets: list[RectWidget],
        clicked_rect: RectWidget,
        same_class_only: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[int]:
        total = len(rect_widgets)
        if progress_callback is not None:
            progress_callback(0, total)
        scored: list[tuple[float, int]] = []
        for idx, rect_widget in enumerate(rect_widgets, start=1):
            if same_class_only and clicked_rect.text_label != rect_widget.text_label:
                distance = inf
            else:
                try:
                    distance = clicked_rect.embedding_distance(rect_widget)
                except Exception:
                    distance = inf
            scored.append((distance, idx - 1))
            if progress_callback is not None and (idx == total or idx % 32 == 0):
                progress_callback(idx, total)
        scored.sort(key=lambda pair: pair[0])
        return [idx for _distance, idx in scored]

    @QtCore.pyqtSlot(object)
    def _on_similarity_sort_ready(self, sorted_indices: list[int]) -> None:
        current = list(self._rect_widgets)
        self._rect_widgets = [current[idx] for idx in sorted_indices]
        self.render_mosaic()

    @QtCore.pyqtSlot(tuple)
    def _on_similarity_sort_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Similarity sort failed: {message}")
        if "not available" in message.lower() and self._dialog_parent is not None:
            QtWidgets.QMessageBox.critical(
                self._dialog_parent,
                "Embedding Model Unavailable",
                message,
            )

    @QtCore.pyqtSlot(int, int)
    def _on_similarity_sort_progress(self, current: int, total: int) -> None:
        if self._similarity_sort_dialog is None:
            return
        self._similarity_sort_dialog.setMaximum(max(0, total))
        self._similarity_sort_dialog.setValue(max(0, min(current, total)))

    @QtCore.pyqtSlot()
    def _on_similarity_sort_finished(self) -> None:
        if self._similarity_sort_dialog is not None:
            self._similarity_sort_dialog.close()
            self._similarity_sort_dialog = None

    @staticmethod
    def _compute_embeddings_payload(
        rect_widgets: list[RectWidget],
        embedding_model: Embedding,
        generation: int,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[tuple[UUID, object]]]:
        uuids: list[UUID] = []
        roi_images: list[np.ndarray] = []
        for rect_widget in rect_widgets:
            try:
                if not rect_widget.roi_loaded:
                    continue
                roi = rect_widget.roi
                if roi is None:
                    continue
                uuids.append(rect_widget.association_uuid)
                roi_images.append(roi[:, :, ::-1])
            except Exception:
                continue

        if not roi_images:
            return generation, []

        embeddings = embedding_model.embed_many(
            roi_images,
            progress_callback=progress_callback,
        )
        return generation, list(zip(uuids, embeddings))

    @QtCore.pyqtSlot(object)
    def _on_embeddings_precomputed(
        self, payload: tuple[int, list[tuple[UUID, object]]]
    ) -> None:
        generation, rows = payload
        if generation != self._embedding_generation:
            return
        embeddings_by_uuid = {
            association_uuid: embedding for association_uuid, embedding in rows
        }
        for rect_widget in self._rect_widgets:
            embedding = embeddings_by_uuid.get(rect_widget.association_uuid)
            if embedding is not None:
                rect_widget.cache_embedding(embedding)

    @QtCore.pyqtSlot(tuple)
    def _on_embeddings_precompute_error(self, err: tuple) -> None:
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.error(f"Embedding precompute failed: {message}")
        if "not available" in message.lower() and self._dialog_parent is not None:
            QtWidgets.QMessageBox.critical(
                self._dialog_parent,
                "Embedding Model Unavailable",
                message,
            )

    @QtCore.pyqtSlot(int, int)
    def _on_embedding_precompute_progress(self, current: int, total: int) -> None:
        if self._embedding_precompute_dialog is None:
            return
        self._embedding_precompute_dialog.setMaximum(max(0, total))
        self._embedding_precompute_dialog.setValue(max(0, min(current, total)))

    @QtCore.pyqtSlot()
    def _on_embeddings_precompute_finished(self) -> None:
        self._embedding_precompute_in_progress = False
        if self._embedding_precompute_dialog is not None:
            self._embedding_precompute_dialog.close()
            self._embedding_precompute_dialog = None
        if self._embedding_precompute_pending and self._embedding_model is not None:
            self._embedding_precompute_pending = False
            self.precompute_embeddings_async()

    @QtCore.pyqtSlot(object)
    def zoom_updated(self, zoom: float):
        for rect_widget in self._rect_widgets:
            rect_widget.update_zoom(float(zoom))
        self.render_mosaic()

    def sort_rect_widgets(
        self, sort_method: type[SortMethod] | SortMethodGroup
    ) -> None:
        """Sort the mosaic tiles in-place.

        Args:
            sort_method: A :class:`~vars_gridview.lib.sorting.sort_methods.SortMethod`
                class or a :class:`~vars_gridview.lib.sorting.sort_methods.SortMethodGroup`
                instance to apply.
        """
        sort_method.sort(self._rect_widgets)

    def clear_view(self) -> None:
        """
        Clear the graphics view without deleting the underlying RectWidgets.
        Hides all rect widgets and clears the layout.
        """
        self._mosaic_view.clear(self._rect_widgets)

    def render_mosaic(self):
        """
        Load images + annotations and populate the mosaic
        """
        # Get the subset of rect widgets to render based on display flags.
        rect_widgets_to_render = []
        for rw in self._rect_widgets:
            if self.hide_labeled and rw.association.verified:
                continue
            if self.hide_unlabeled and not rw.association.verified:
                continue
            if self.hide_training and rw.association.is_training:
                continue
            if self.hide_nontraining and not rw.association.is_training:
                continue
            rect_widgets_to_render.append(rw)

        render_result = self._mosaic_view.render(
            all_widgets=self._rect_widgets,
            visible_widgets=rect_widgets_to_render,
        )
        self._n_columns = render_result.columns

        # Update the stats
        self.stats_changed.emit(
            {
                "ROIs": f"{render_result.rendered_count} / {self.n_localizations}",
                "Images": str(self.n_images),
            }
        )

    def get_selected(self) -> list[RectWidget]:
        """Return the list of currently selected tiles."""
        return self.selection_model.selected

    def get_all_rect_widgets(self) -> list[RectWidget]:
        """Return all mosaic tiles in current display order."""
        return list(self._rect_widgets)

    def delete_selected(self):
        """
        Remove selected widgets from the mosaic UI.

        Deprecated for data mutation; callers should perform remote delete via
        ``AnnotationController`` then call :meth:`remove_rect_widgets`.
        """
        self.remove_rect_widgets(self.get_selected())

    def remove_rect_widgets(self, rect_widgets: list[RectWidget]) -> None:
        """Remove the given widgets from the mosaic and re-render.

        Args:
            rect_widgets: Widgets to remove from the current mosaic state.
        """
        if not rect_widgets:
            return

        self.clear_selected()
        for rw in rect_widgets:
            if rw in self._rect_widgets:
                rw.hide()
                self._rect_widgets.remove(rw)

        self.n_localizations = len(self._rect_widgets)
        self.render_mosaic()

    def deselect(self, rect_widget: RectWidget):
        """
        Deselect a rect widget.
        """
        if rect_widget not in self._rect_widgets:
            raise ValueError("Widget not in rect widget list")

        self.selection_model.remove(rect_widget)

    def select(self, rect_widget: RectWidget, clear: bool = True):
        """
        Select a rect widget.
        """
        if rect_widget not in self._rect_widgets:
            raise ValueError("Widget not in rect widget list")

        if clear:
            self.selection_model.set_selection([rect_widget])
        else:
            self.selection_model.add(rect_widget)

    def select_range(self, first: RectWidget, last: RectWidget):
        """
        Select a range of rect widgets.
        """
        if first not in self._rect_widgets:
            raise ValueError("First widget not in rect widget list")
        elif last not in self._rect_widgets:
            raise ValueError("Last widget not in rect widget list")

        # Get the indices of the first and last widgets
        first_idx = self._rect_widgets.index(first)
        last_idx = self._rect_widgets.index(last)

        begin_idx = min(first_idx, last_idx)
        end_idx = max(first_idx, last_idx)

        # Select all widgets in the range
        range_selection: list[RectWidget] = []
        for idx in range(begin_idx, end_idx + 1):
            # Only select if it's visible
            if self._rect_widgets[idx].isVisible():
                range_selection.append(self._rect_widgets[idx])
        self.selection_model.set_selection(range_selection)

    def clear_selected(self):
        """
        Clear the selection of rect widgets.
        """
        self.selection_model.clear()

    @QtCore.pyqtSlot(list)
    def _on_selection_changed(self, selected: list[RectWidget]) -> None:
        selected_set = set(selected)
        for rect_widget in self._rect_widgets:
            is_selected = rect_widget in selected_set
            if rect_widget.is_selected != is_selected:
                rect_widget.is_selected = is_selected
                rect_widget.update()

    def _scroll_to_rect_if_needed(self, rect_widget: RectWidget) -> None:
        """Scroll only when *rect_widget* is outside the current viewport."""
        viewport = self._graphics_view.viewport()
        if viewport is None:
            return

        item_rect_scene = rect_widget.sceneBoundingRect()
        item_rect_view = self._graphics_view.mapFromScene(
            item_rect_scene
        ).boundingRect()
        viewport_rect = viewport.rect()
        if viewport_rect.contains(item_rect_view):
            return

        self._graphics_view.ensureVisible(item_rect_scene, 8, 8)

    def select_relative(self, key: QtCore.Qt.Key) -> bool:
        """
        Select a rect widget relative to the currently selected one.

        Args:
            key: The key pressed
        """
        navigable_keys = {
            QtCore.Qt.Key.Key_Left,
            QtCore.Qt.Key.Key_Right,
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
        }
        if key not in navigable_keys:
            return False

        selected = self.get_selected()
        if len(selected) == 0:
            return True

        # Get the first selected widget
        first = selected[0]

        # Get the index of the first selected widget
        first_idx = self._rect_widgets.index(first)

        # Get the index of the next widget
        if key == QtCore.Qt.Key.Key_Left:
            next_idx = first_idx - 1
        elif key == QtCore.Qt.Key.Key_Right:
            next_idx = first_idx + 1
        elif key == QtCore.Qt.Key.Key_Up:
            next_idx = first_idx - self._n_columns
        elif key == QtCore.Qt.Key.Key_Down:
            next_idx = first_idx + self._n_columns
        else:
            return False

        # Select the next widget if it's in bounds
        if 0 <= next_idx < len(self._rect_widgets):
            self.clear_selected()
            next_widget = self._rect_widgets[next_idx]
            self._rect_clicked_slot(next_widget, None)
            self._scroll_to_rect_if_needed(next_widget)

        return True

    def eventFilter(
        self,
        source: QtCore.QObject,
        event: QtCore.QEvent,
    ) -> bool:  # type: ignore[override]
        if source is self._graphics_view and event.type() == QtCore.QEvent.Type.Resize:
            self.render_mosaic()  # Re-render when the view is resized
        if (
            source is self._graphics_view
            and event.type() == QtCore.QEvent.Type.KeyPress
        ):
            key_event = cast(QtGui.QKeyEvent, event)
            if self.select_relative(cast(QtCore.Qt.Key, key_event.key())):
                # Consume handled arrow keys so QGraphicsView doesn't auto-scroll.
                return True
        return super().eventFilter(source, event)
