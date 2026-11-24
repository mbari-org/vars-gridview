"""Image mosaic widget manager.

Manages a grid of :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
tiles, and handles metadata loading, ROI creation, sorting, selection, and
CRUD operations on bounding-box annotations.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Event
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from iso8601 import parse_date
from pydantic import BaseModel
from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.controllers.selection_model import SelectionModel
from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.lib.sorting.sort_methods import SortMethod, SortMethodGroup
from vars_gridview.services.localization_store import LocalizationStore
from vars_gridview.services.mosaic_pipeline import MosaicPipeline
from vars_gridview.services.roi_loader import RoiLoader, RoiLoadResult
from vars_gridview.ui.coordinators.mosaic_embedding_coordinator import (
    MosaicEmbeddingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_load_coordinator import MosaicLoadCoordinator
from vars_gridview.ui.coordinators.mosaic_roi_loading_coordinator import (
    MosaicRoiLoadingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_rubber_band import MosaicRubberBandSelector
from vars_gridview.ui.coordinators.mosaic_selection_coordinator import (
    MosaicSelectionCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    MosaicSimilarityCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_tile_action_coordinator import (
    MosaicTileActionCoordinator,
)
from vars_gridview.ui.mosaic.mosaic_view import MosaicView, MosaicVisibilityFilters
from vars_gridview.ui.mosaic.rect_widget import DisplayContext, RectWidget
from vars_gridview.ui.mosaic.rect_widget_factory import RectWidgetFactory

if TYPE_CHECKING:
    import numpy as np

    from vars_gridview.lib.m3.clients import AnnosaurusClient, VampireSquidClient
    from vars_gridview.lib.vision.display_adjust import DisplayAdjustment
    from vars_gridview.lib.vision.embedding import Embedding
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
        if len(headers) != len(row):
            raise ValueError(
                f"Header/row length mismatch: {len(headers)} headers, {len(row)} values"
            )

        # Normalize null/blank tokens while preserving non-string values.
        def _normalize_cell(value: object) -> object:
            if not isinstance(value, str):
                return value
            trimmed = value.strip()
            if trimmed == "":
                return None
            if trimmed.lower() == "null":
                return None
            return trimmed

        row = list(map(_normalize_cell, row))

        # Create a dictionary of the row data
        row_dict = dict(zip(headers, row))

        # Parse ISO8601 dates
        for key in ("index_recorded_timestamp", "video_start_timestamp"):
            timestamp_raw = row_dict.get(key)
            if timestamp_raw is None:
                continue
            try:
                row_dict[key] = parse_date(str(timestamp_raw))
            except Exception as exc:
                raise ValueError(f"Invalid {key}: {timestamp_raw}") from exc

        return cls(**row_dict)


class Cancelled(Exception):
    """
    Exception raised when the user cancels an operation.
    """


class ImageMosaic(QtCore.QObject):
    """Manager for the image-mosaic grid view.

    Populates a :class:`PyQt6.QtWidgets.QGraphicsView` with a grid of
    :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget` tiles sourced from VARS
    annotation query results.  Handles video-sequence metadata prefetching,
    ROI image loading, selection state, and bulk annotation operations.
    """

    stats_changed = QtCore.pyqtSignal(dict)
    mosaic_stage_started = QtCore.pyqtSignal(
        str, int
    )  # stage key, maximum (0 = indeterminate)
    mosaic_stage_progress = QtCore.pyqtSignal(
        str, int, int
    )  # stage key, current, maximum
    rect_widgets_removed = QtCore.pyqtSignal(list)  # widgets removed from the mosaic
    # shown, total, {label: tiles hidden by the confidence range}
    filter_status_changed = QtCore.pyqtSignal(int, int, dict)
    tile_delete_requested = QtCore.pyqtSignal(object)  # RectWidget (right-click)
    tile_verify_and_mark_training_requested = QtCore.pyqtSignal(object)  # RectWidget

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
        settings: AppSettings | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()

        # Initialize the graphics
        self._graphics_view = graphics_view
        self._dialog_parent = dialog_parent
        self._mosaic_view = MosaicView(graphics_view)
        self._graphics_view.installEventFilter(self)

        self._rect_clicked_slot = rect_clicked_slot
        self._embedding_model = embedding_model
        self._annosaurus_client = annosaurus_client
        self._vampire_squid_client = vampire_squid_client
        self._roi_service = roi_service
        self._concept_provider = concept_provider
        self._part_provider = part_provider

        self._rect_widgets: list[RectWidget] = []
        self._visible_widgets: list[RectWidget] = []  # as last laid out
        self._n_columns = 0
        self.selection_model = SelectionModel(parent=self)
        self.selection_model.selection_changed.connect(self._on_selection_changed)
        self._selection = MosaicSelectionCoordinator(
            parent=self,
            selection_model=self.selection_model,
            mosaic_view=self._mosaic_view,
            all_widgets_getter=lambda: self._rect_widgets,
            visible_widgets_getter=lambda: self._visible_widgets,
        )

        # Display flags
        self.hide_labeled = False
        self.hide_unlabeled = False
        self.hide_training = False
        self.hide_nontraining = False
        # Filter bar: show only this label (None = all) / confidence range.
        self.label_filter: str | None = None
        self.min_confidence = 0.0
        self.max_confidence = 1.0

        # How tiles are drawn (colour correction etc.), shared by all tiles.
        self._display_context = DisplayContext()

        # Drag a rectangle to select / deselect tiles.
        self._rubber_band = MosaicRubberBandSelector(
            parent=self,
            graphics_view=graphics_view,
            selection_model=self.selection_model,
            visible_widgets_getter=lambda: self._visible_widgets,
        )

        # Several settings (and a model change) each ask for stored vectors;
        # one fetch serves them all, and none starts while the same one runs.
        self._stored_fetch_timer = QtCore.QTimer(self)
        self._stored_fetch_timer.setSingleShot(True)
        self._stored_fetch_timer.setInterval(50)
        self._stored_fetch_timer.timeout.connect(self._fetch_stored_embeddings_now)
        # (generations, model, url, collection) of the fetch running, if any.
        self._stored_fetch_running: tuple | None = None

        # Embeddings of tiles whose box was edited: recomputed in one batch.
        self._recompute_timer = QtCore.QTimer(self)
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(500)
        self._recompute_timer.timeout.connect(self.precompute_embeddings_async)

        # Load on-screen tiles first: re-prioritise shortly after scrolling.
        self._prioritize_timer = QtCore.QTimer(self)
        self._prioritize_timer.setSingleShot(True)
        self._prioritize_timer.setInterval(100)
        self._prioritize_timer.timeout.connect(self._prioritize_visible_loading)
        scroll_bar = graphics_view.verticalScrollBar()
        if scroll_bar is not None:
            # A slot of this object, not a lambda: Qt drops the connection when
            # the mosaic is destroyed. The scroll bar belongs to the window and
            # can outlive it at quit, and a lambda then hit the deleted timer
            # ("wrapped C/C++ object of type QTimer has been deleted").
            scroll_bar.valueChanged.connect(self._on_scrolled)

        # Non-Qt data store backing metadata and association groups.
        self.store = LocalizationStore()
        self._mosaic_pipeline = MosaicPipeline()
        self._roi_loader = RoiLoader()
        self.video_reference_uuid_to_mp4_video_reference = {}

        self.n_images = 0
        self.n_localizations = 0
        self._embedding_generation = 0
        # Which model's vectors the tiles hold (a vector-database vector name
        # == embedding-service model name). Embeddings are cleared only when
        # this changes, not each time the service connection is re-made.
        self._embedding_space: str | None = None
        self._results_generation = 0  # bumped per populate()
        self._all_rois_loaded = False
        self._vector_store = None
        self._vector_store_config: tuple[str, str] | None = None
        self._current_build_stage_key: str | None = None
        self._load_coordinator = MosaicLoadCoordinator(parent=self)
        self._load_coordinator.stage_progress.connect(self._on_load_stage_progress)
        # Was 4, which combined with the per-tile debounce created a hard
        # ~20-30 tiles/s ceiling regardless of backend speed. Higher than
        # ~20 stops helping on typical hardware -- gridview's worker threads
        # share one process/GIL, so more of them mostly adds contention.
        self._roi_loading = MosaicRoiLoadingCoordinator(
            parent=self,
            max_concurrency=16,
        )
        self._roi_loading.progress.connect(self._on_roi_loading_progress)
        self._similarity = MosaicSimilarityCoordinator(
            parent=self,
            dialog_parent=self._dialog_parent,
            rect_widgets_getter=lambda: self._rect_widgets,
            apply_order=self._apply_order,
            space_getter=lambda: self._embedding_space,
            sort_unavailable_callback=self._on_similarity_unavailable,
            status_callback=lambda text: self.stats_changed.emit({"Status": text}),
        )
        self._embedding = MosaicEmbeddingCoordinator(parent=self)
        self._embedding_precompute_total = 0
        self._embedding.precompute_started.connect(
            self._on_embedding_precompute_started
        )
        self._embedding.precompute_progress.connect(
            self._on_embedding_precompute_progress
        )
        self._embedding.precompute_finished.connect(
            self._on_embedding_precompute_finished
        )
        self._tile_actions = MosaicTileActionCoordinator(
            parent=self,
            dialog_parent=self._dialog_parent,
            concept_provider=self._concept_provider,
            part_provider=self._part_provider,
            label_action_callback=label_action_callback,
            verify_action_callback=verify_action_callback,
            mark_training_action_callback=mark_training_action_callback,
        )
        self._rect_widget_factory = RectWidgetFactory(
            rect_clicked_slot=self._rect_clicked_slot,
            similarity_sort_slot=self._similarity.start,
            rect_label_slot=self._tile_actions.handle_label_action,
            rect_verify_slot=self._tile_actions.handle_verify_action,
            rect_mark_training_slot=self._tile_actions.handle_mark_training_action,
            settings=self._settings,
        )

        self._settings.gui_zoom.valueChanged.connect(self.zoom_updated)

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

    def populate(
        self,
        query_headers: list[str],
        query_rows: list[list[str]],
        *,
        cancel_event: Event,
    ) -> None:
        """Populate the mosaic from raw VARS query output.

        Clears any previous state, parses the rows, fetches ancillary
        metadata from M3, and creates a :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
        for every bounding-box association found.

        Args:
            query_headers: Column names as returned by the query endpoint.
            query_rows: One inner list per result row.
            cancel_event: Shared cancellation token checked cooperatively at each
                build stage; also passed on to ROI image loading.
        """
        # Clear existing widgets
        self._results_generation += 1
        self._all_rois_loaded = False
        self._roi_loading.cancel_pending()
        self._selection.reset()
        old_widgets = list(self._rect_widgets)
        self._rect_widgets.clear()
        self._visible_widgets = []
        self._mosaic_view.dispose(old_widgets)

        try:
            # Parse rows and build localization store off the UI thread.
            rows = self._prepare_localization_data(
                query_headers, query_rows, cancel_event=cancel_event
            )

            # Fetch video sequence data for the given groups
            self._fetch_video_sequence_data(cancel_event=cancel_event)

            # Derive and map proxy image metadata
            self._map_proxy_data(rows, cancel_event=cancel_event)

            # Create the ROI widgets
            self._create_rois(cancel_event=cancel_event)
        except Cancelled:
            LOGGER.info("Image mosaic loading cancelled by user")
            return

    def _prepare_localization_data(
        self,
        query_headers: list[str],
        query_rows: list[list[str]],
        *,
        cancel_event: Event,
    ) -> list[Row]:
        """Parse rows and build localization state off the UI thread."""
        cached_image_reference_urls = dict(self.store.image_reference_urls)
        cached_video_sequences_by_name = dict(self.store.video_sequences_by_name)

        self._begin_build_stage("localization", maximum=max(0, len(query_rows)))
        payload = self._run_cancellable_stage(
            cancelled_message="Localization preparation cancelled",
            missing_result_message="Localization preparation returned no result",
            cancel_event=cancel_event,
            worker_factory=lambda cancel_event, progress_callback: (
                self._mosaic_pipeline.build_localization_state(
                    query_rows=query_rows,
                    row_parser=lambda row: Row.parse(query_headers, row),
                    cached_image_reference_urls=cached_image_reference_urls,
                    cached_video_sequences_by_name=cached_video_sequences_by_name,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                    cancelled_message="Localization preparation cancelled",
                )
            ),
        )
        rows, store = cast(tuple[list[object], LocalizationStore], payload)
        self.store = store
        return cast(list[Row], rows)

    def _map_metadata(self, rows: list[Row]) -> None:
        """Populate internal lookup tables from *rows*."""
        self.store.map_metadata(list(rows))

    def _extract_associations(self, rows: list[Row]) -> None:
        """Extract bounding-box associations from *rows* into association groups."""
        self.store.extract_associations(list(rows))

    def _fetch_video_sequence_data(self, *, cancel_event: Event) -> None:
        if self._vampire_squid_client is None:
            raise RuntimeError(
                "ImageMosaic is missing VampireSquid client; call configure_services() after login"
            )
        self._begin_build_stage("video_sequence", maximum=0)
        self._run_cancellable_stage(
            cancelled_message="Video sequence fetch cancelled",
            missing_result_message=None,
            cancel_event=cancel_event,
            worker_factory=lambda cancel_event, progress_callback: (
                self._roi_loader.fetch_video_sequence_data(
                    vampire_squid_client=self._vampire_squid_client,
                    moment_video_data=self.moment_video_data,
                    video_sequences_by_name=self.video_sequences_by_name,
                    progress_callback=progress_callback,
                    should_cancel=cancel_event.is_set,
                )
            ),
        )

    def _map_proxy_data(self, rows: list[Row], *, cancel_event: Event) -> None:
        """Derive proxy video data for each imaged moment in *rows* off-thread."""
        self._begin_build_stage("proxy_mapping", maximum=max(0, len(rows)))
        payload = self._run_cancellable_stage(
            cancelled_message="Proxy mapping cancelled",
            missing_result_message="Proxy mapping returned no result",
            cancel_event=cancel_event,
            worker_factory=lambda cancel_event, progress_callback: (
                self._mosaic_pipeline.build_proxy_mapping(
                    rows=list(rows),
                    existing_moment_proxy_data=self.moment_proxy_data,
                    existing_moment_timestamps=self.moment_timestamps,
                    video_sequences_by_name=self.video_sequences_by_name,
                    roi_loader=self._roi_loader,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
            ),
        )
        proxy_data, timestamps = cast(
            tuple[dict[UUID, dict | None], dict[UUID, object]],
            payload,
        )
        self.store.moment_proxy_data = proxy_data
        self.store.moment_timestamps = timestamps

    def _create_rois(self, *, cancel_event: Event) -> None:
        if self._annosaurus_client is None or self._roi_service is None:
            raise RuntimeError(
                "ImageMosaic is missing Annosaurus/ROI services; call configure_services() after login"
            )

        self._begin_build_stage("roi_widgets", maximum=0)
        load_result = self._run_cancellable_stage(
            cancelled_message="ROI creation cancelled",
            missing_result_message="ROI spec preparation returned no result",
            cancel_event=cancel_event,
            worker_factory=lambda cancel_event, progress_callback: (
                self._roi_loader.create_widget_specs(
                    annosaurus_client=self._annosaurus_client,
                    association_groups=self.association_groups,
                    moment_video_data=self.moment_video_data,
                    moment_proxy_data=self.moment_proxy_data,
                    moment_timestamps=self.moment_timestamps,
                    image_reference_urls=self.image_reference_urls,
                    moment_ancillary_data=self.moment_ancillary_data,
                    progress_callback=progress_callback,
                    should_cancel=cancel_event.is_set,
                )
            ),
        )
        load_result = cast(RoiLoadResult, load_result)

        rect_widgets, failed_association_uuids = self._build_rect_widgets_from_specs(
            load_result
        )

        self._rect_widgets = rect_widgets
        self.n_images = load_result.n_images
        self.n_localizations = load_result.n_localizations
        self._begin_build_stage("roi_images", maximum=len(self._rect_widgets))
        self._roi_loading.start_loading(
            rect_widgets=self._rect_widgets,
            on_complete=self._on_all_roi_loaded,
            cancel_event=cancel_event,
        )
        # Stored embeddings need no images: fetch them while tiles load.
        self.fetch_stored_embeddings()

        self._show_roi_creation_failures(failed_association_uuids)

    def _build_rect_widgets_from_specs(
        self,
        load_result: RoiLoadResult,
    ) -> tuple[list[RectWidget], list[UUID]]:
        """Materialize `RectWidget` instances from service-provided specs."""
        rect_widgets: list[RectWidget] = []
        failed_association_uuids = list(load_result.failed_association_uuids)
        for spec in load_result.widget_specs:
            try:
                rw = self._rect_widget_factory.create(
                    spec,
                    embedding_model=self._embedding_model,
                    roi_service=self._roi_service,
                )
                rw.set_display_context(self._display_context)
                rw.deleteRequested.connect(self.tile_delete_requested)
                rw.roiRefreshed.connect(self._on_tile_image_refreshed)
                rw.verifyAndMarkTrainingRequested.connect(
                    self.tile_verify_and_mark_training_requested
                )
                rect_widgets.append(rw)
            except Exception as exc:  # noqa: BLE001
                assoc = spec.associations[spec.association_index]
                LOGGER.error(f"Error creating rect widget {assoc.uuid}: {exc}")
                failed_association_uuids.append(assoc.uuid)
        return rect_widgets, failed_association_uuids

    def _show_roi_creation_failures(self, failed_association_uuids: list[UUID]) -> None:
        """Show a warning dialog listing associations that could not be materialized."""
        if not failed_association_uuids:
            return
        error_message = "\n".join([str(uuid) for uuid in failed_association_uuids])
        QtWidgets.QMessageBox.warning(
            self._graphics_view,
            "Failed to Create ROIs",
            f"The following bounding box associations could not be loaded:\n{error_message}",
        )

    def _run_cancellable_stage(
        self,
        *,
        cancelled_message: str,
        missing_result_message: str | None,
        cancel_event: Event,
        worker_factory: Callable[[Event, Callable[[int, int], None]], object],
    ) -> object | None:
        """Run one load stage and normalize cancellation handling."""
        try:
            result = self._load_coordinator.run_stage(
                cancelled_message=cancelled_message,
                cancel_event=cancel_event,
                worker_factory=worker_factory,
            )
        except RuntimeError as exc:
            if str(exc) == cancelled_message:
                raise Cancelled from exc
            raise

        if result is None and missing_result_message is not None:
            raise RuntimeError(missing_result_message)
        return result

    def _begin_build_stage(self, key: str, *, maximum: int) -> None:
        """Record the active build stage and announce it to listeners."""
        self._current_build_stage_key = key
        self.mosaic_stage_started.emit(key, maximum)

    @QtCore.pyqtSlot(int, int)
    def _on_load_stage_progress(self, current: int, total: int) -> None:
        if self._current_build_stage_key is None:
            return
        self.mosaic_stage_progress.emit(self._current_build_stage_key, current, total)

    @QtCore.pyqtSlot(int, int)
    def _on_roi_loading_progress(self, current: int, total: int) -> None:
        self.mosaic_stage_progress.emit("roi_images", current, total)

    @QtCore.pyqtSlot(int)
    def _on_embedding_precompute_started(self, total: int) -> None:
        self._embedding_precompute_total = total
        self._begin_build_stage("embeddings", maximum=total)

    @QtCore.pyqtSlot(int, int)
    def _on_embedding_precompute_progress(self, current: int, total: int) -> None:
        self.mosaic_stage_progress.emit("embeddings", current, total)

    @QtCore.pyqtSlot()
    def _on_embedding_precompute_finished(self) -> None:
        # Force the indicator closed even if progress stalled short of total
        # (e.g. an error occurred mid-batch).
        total = self._embedding_precompute_total
        self.mosaic_stage_progress.emit("embeddings", total, total)

    def update_embedding_model(self, embedding_model: Embedding | None) -> None:
        """Replace the active embedding model. Cached embeddings are cleared
        only if the model *name* changed: reconnecting to the same model (or
        the service going away) keeps them, including ones from the VARS
        vector database."""
        model_changed = self._embedding_model is not embedding_model
        self._embedding_model = embedding_model
        self._embedding.on_model_changed(
            model_changed=model_changed,
            has_model=embedding_model is not None,
        )
        for rect_widget in self._rect_widgets:
            rect_widget.update_embedding_model(embedding_model)
        name = getattr(embedding_model, "model_name", None)
        if name is not None:
            self._set_embedding_space(name)

    def _set_embedding_space(self, name: str) -> None:
        if name == self._embedding_space:
            return
        if self._embedding_space is not None:
            for rect_widget in self._rect_widgets:
                rect_widget.invalidate_embedding_cache()
        self._embedding_space = name
        self._embedding_generation += 1

    def _vector_store_for(self, url: str, collection: str):
        from vars_gridview.lib.vision.vector_store import VarsVectorStore

        if self._vector_store is None or self._vector_store_config != (url, collection):
            self._vector_store = VarsVectorStore(url, collection)
            self._vector_store_config = (url, collection)
        return self._vector_store

    def fetch_stored_embeddings(self) -> None:
        """Give tiles the embeddings the VARS vector database already holds
        for them (see :mod:`vars_gridview.lib.vision.vector_store`); the rest
        are computed by the embedding service as before.

        Calls made close together are served by one fetch (see
        :meth:`_fetch_stored_embeddings_now`), and computing embeddings waits
        for it (see :meth:`precompute_embeddings_async`)."""
        self._stored_fetch_timer.start()

    @property
    def _stored_fetch_pending(self) -> bool:
        return self._stored_fetch_timer.isActive() or (
            self._stored_fetch_running is not None
        )

    def _fetch_stored_embeddings_now(self) -> None:
        if not self._start_stored_fetch():
            # Nothing to wait for: compute whatever is still missing.
            self._precompute_if_ready()

    def _start_stored_fetch(self) -> bool:
        """Start fetching stored vectors; True if one is (now) running."""
        from vars_gridview.lib.vision.vector_store import BoxQuery

        settings = self._settings
        # Independent of "embeddings enabled", which only controls computing
        # embeddings with the embedding service: stored ones need no service,
        # so they're used whenever the vector database option is on.
        if not settings.vector_db_enabled.value:
            return False
        name = settings.embedding_model_name.value.strip()
        url = settings.vector_db_url.value.strip()
        collection = settings.vector_db_collection.value.strip()
        if not (name and url and collection):
            return False
        self._set_embedding_space(name)
        key = (
            self._embedding_generation,
            self._results_generation,
            name,
            url,
            collection,
        )
        if key == self._stored_fetch_running:
            return True  # the same fetch is already running
        queries = []
        boxes: dict[UUID, tuple] = {}
        for rect_widget in self._rect_widgets:
            if rect_widget.has_cached_embedding:
                continue
            association = rect_widget.association
            boxes[rect_widget.association_uuid] = tuple(association.box)
            queries.append(
                BoxQuery(
                    rect_widget.association_uuid,
                    association.x,
                    association.y,
                    association.width,
                    association.height,
                )
            )
        if not queries:
            return False
        store = self._vector_store_for(url, collection)
        asked = len(queries)
        self._stored_fetch_running = key
        worker = Worker(store.fetch, queries, name)  # plain data only
        worker.signals.result.connect(
            lambda result, key=key, asked=asked: self._on_stored_embeddings(
                result, key, asked, store.description, boxes, name
            )
        )
        worker.signals.error.connect(
            lambda err, key=key, where=store.description: (
                self._on_stored_embeddings_failed(err, where, key)
            )
        )
        QtCore.QThreadPool.globalInstance().start(worker)
        return True

    def _stored_fetch_finished(self, key: tuple) -> bool:
        """Note that the fetch for *key* ended; True if it's the latest."""
        if key != self._stored_fetch_running:
            return False  # superseded; the newer fetch reports
        self._stored_fetch_running = None
        return True

    def _on_stored_embeddings(
        self,
        result: tuple,
        key: tuple,
        asked: int,
        where: str,
        boxes: dict[UUID, tuple] | None = None,
        name: str | None = None,
    ) -> None:
        if not self._stored_fetch_finished(key):
            return
        if key[:2] != (self._embedding_generation, self._results_generation):
            self._precompute_if_ready()  # another page or model since
            return
        vectors, stale = result
        used = 0
        for rect_widget in self._rect_widgets:
            vector = vectors.get(rect_widget.association_uuid)
            if vector is not None and not rect_widget.has_cached_embedding:
                # The box the database was asked about (and matched): a box
                # edited while the request ran doesn't get this vector.
                box = (boxes or {}).get(rect_widget.association_uuid)
                rect_widget.cache_embedding(vector, box=box, space=name)
                used += 1
        LOGGER.info(
            f"Embeddings from the VARS vector database {where}: {used:,} of {asked:,} "
            f"tiles ({stale:,} skipped: box edited since it was stored)"
        )
        self.stats_changed.emit({"Stored embeddings": f"{used:,} / {asked:,}"})
        self._precompute_if_ready()  # only the ones still missing

    def _on_stored_embeddings_failed(
        self, err: tuple, where: str, key: tuple | None = None
    ) -> None:
        if key is not None and not self._stored_fetch_finished(key):
            return
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        LOGGER.warning(f"VARS vector database {where} unavailable: {message}")
        self.stats_changed.emit({"Stored embeddings": "unavailable"})
        self._precompute_if_ready()  # the service computes them all instead

    def _precompute_if_ready(self) -> None:
        if self._all_rois_loaded and self._embedding_model is not None:
            self.precompute_embeddings_async()

    def precompute_embeddings_async(self) -> None:
        """Warm tile embeddings in the background to avoid on-demand UI stalls.

        Waits while stored vectors are being fetched: the fetch's end starts
        it, for only the tiles the vector database didn't have. Otherwise the
        service would be asked for every tile, and a running precompute can't
        be stopped when the stored vectors arrive."""
        if self._stored_fetch_pending:
            return
        self._embedding.request_precompute(
            # A getter: delete replaces the list, and a queued restart must
            # not embed tiles deleted since.
            rect_widgets=lambda: self._rect_widgets,
            embedding_model=self._embedding_model,
            generation=self._embedding_generation,
            on_result=self._on_embeddings_precomputed,
            on_unavailable=self._on_embedding_unavailable,
        )

    def _on_all_roi_loaded(self) -> None:
        self._all_rois_loaded = True
        if self._embedding_model is not None:
            # Compute embeddings in a single worker after all ROI images are ready.
            self.precompute_embeddings_async()

    def _apply_order(self, ordered: list[RectWidget]) -> None:
        """Reorder tiles to *ordered*, onto whatever the grid holds now: tiles
        gone since are dropped, any not in *ordered* keep their place after."""
        present = {id(rw) for rw in self._rect_widgets}
        head = [rw for rw in ordered if id(rw) in present]
        seen = {id(rw) for rw in head}
        self._rect_widgets = head + [
            rw for rw in self._rect_widgets if id(rw) not in seen
        ]
        self.render_mosaic()
        # The best matches are at the top: show them. The view used to stay
        # where the user had scrolled to right-click, i.e. on middling ones.
        scroll_bar = self._graphics_view.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.setValue(scroll_bar.minimum())

    def _on_similarity_unavailable(self, message: str) -> None:
        if self._dialog_parent is None:
            return
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Embedding Model Unavailable",
            message,
        )

    @QtCore.pyqtSlot(object)
    def _on_embeddings_precomputed(self, payload: tuple) -> None:
        generation, model_name, rows = payload
        if generation != self._embedding_generation:
            return
        if self._embedding_space is not None and model_name != self._embedding_space:
            # Made by a model replaced since (the old one can still be
            # running when the model setting changes): another space.
            return
        by_uuid = {
            association_uuid: (vector, box) for association_uuid, vector, box in rows
        }
        for rect_widget in self._rect_widgets:
            found = by_uuid.get(rect_widget.association_uuid)
            if found is not None:
                vector, box = found
                # Recorded against the box the image was cropped from: if the
                # box has been edited since, the tile still counts as having
                # no embedding and is computed again.
                rect_widget.cache_embedding(vector, box=box, space=model_name)

    def _on_embedding_unavailable(self, message: str) -> None:
        if self._dialog_parent is None:
            return
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Embedding Model Unavailable",
            message,
        )

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
        filtered = self._mosaic_view.apply_filters(
            all_widgets=self._rect_widgets,
            filters=MosaicVisibilityFilters(
                hide_labeled=self.hide_labeled,
                hide_unlabeled=self.hide_unlabeled,
                hide_training=self.hide_training,
                hide_nontraining=self.hide_nontraining,
                label=self.label_filter,
                min_confidence=self.min_confidence,
                max_confidence=self.max_confidence,
            ),
        )
        rect_widgets_to_render = filtered.visible
        # A tile that is filtered out can't stay selected: the next action
        # would change it unseen.
        if self.selection_model.count:
            shown = {id(w) for w in rect_widgets_to_render}
            kept = [w for w in self.selection_model.selected if id(w) in shown]
            if len(kept) != self.selection_model.count:
                self.selection_model.set_selection(kept)

        self._visible_widgets = rect_widgets_to_render
        render_result = self._mosaic_view.render(
            all_widgets=self._rect_widgets,
            visible_widgets=rect_widgets_to_render,
        )
        self._n_columns = render_result.columns

        self.filter_status_changed.emit(
            len(rect_widgets_to_render),
            len(self._rect_widgets),
            filtered.hidden_by_confidence,
        )
        self._prioritize_timer.start()

        # Update the stats
        self.stats_changed.emit(
            {
                "ROIs": f"{render_result.rendered_count} / {self.n_localizations}",
                "Images": str(self.n_images),
            }
        )

    # -- filter bar / view adjustments ----------------------------------------

    def set_filters(
        self, label: str | None, min_confidence: float, max_confidence: float
    ) -> None:
        """Show only tiles with *label* (None = all) whose confidence is in
        [min_confidence, max_confidence]; nothing is re-queried."""
        self.label_filter = label
        self.min_confidence = float(min_confidence)
        self.max_confidence = float(max_confidence)
        self.render_mosaic()

    def label_counts(self) -> dict[str, int]:
        """Tiles per label in the loaded results."""
        counts: dict[str, int] = {}
        for rect_widget in self._rect_widgets:
            label = rect_widget.association.text_label
            counts[label] = counts.get(label, 0) + 1
        return counts

    @property
    def display_context(self) -> DisplayContext:
        return self._display_context

    def set_display_adjustment(self, adjustment: DisplayAdjustment) -> None:
        """Redraw tiles with *adjustment*; only on-screen tiles are redone now,
        the rest as they're scrolled to (see DisplayContext)."""
        if self._display_context.set_adjustment(adjustment):
            viewport = self._graphics_view.viewport()
            if viewport is not None:
                viewport.update()

    def remember_frame_colour(
        self, rect_widget: RectWidget, frame_params: np.ndarray
    ) -> None:
        """Keep a whole frame's colour measurement (made by the image view's
        loader, off the GUI thread) and redraw every tile cropped from it
        with that."""
        key = rect_widget.frame_key
        if self._display_context.corrector.has_frame(key):
            return
        self._display_context.corrector.store_frame(key, frame_params)
        if self._display_context.adjustment.colour_correct:
            for other in self._rect_widgets:
                if other.frame_key == key:
                    other.set_display_context(self._display_context)

    @QtCore.pyqtSlot(object)
    def _on_tile_image_refreshed(self, rect_widget: RectWidget) -> None:
        """A tile's image changed after the page loaded (its box was edited):
        compute its embedding again, batched with any others edited."""
        if (
            self._all_rois_loaded
            and self._embedding_model is not None
            and rect_widget.roi_loaded
            and not rect_widget.has_cached_embedding
        ):
            self._recompute_timer.start()

    def refresh_tiles_for_association(self, association: object) -> bool:
        """Reload the image of every tile showing *association*'s box (the
        image view shows all boxes of a frame, and the one dragged may belong
        to another tile than the one clicked). Returns whether any did."""
        found = False
        for rect_widget in self._rect_widgets:
            if rect_widget.association is association:
                rect_widget.request_roi_refresh()
                found = True
        return found

    @QtCore.pyqtSlot(int)
    def _on_scrolled(self, _value: int) -> None:
        self._prioritize_timer.start()

    def _prioritize_visible_loading(self) -> None:
        if not self._roi_loading.has_pending:
            return  # all loaded or loading: don't scan the grid after every scroll
        near = self._mosaic_view.widgets_near_viewport(self._visible_widgets, 1.0)
        self._roi_loading.prioritize(near)

    def get_selected(self) -> list[RectWidget]:
        """Return the list of currently selected tiles."""
        return cast(list[RectWidget], self._selection.get_selected())

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
        to_remove = {id(rw) for rw in rect_widgets}
        removed = [rw for rw in self._rect_widgets if id(rw) in to_remove]
        self._rect_widgets = [
            rw for rw in self._rect_widgets if id(rw) not in to_remove
        ]

        self.n_localizations = len(self._rect_widgets)
        # Before they're deleted: a retry sweep or the load queue must not
        # touch them afterwards.
        self._roi_loading.forget(removed)
        self.render_mosaic()
        # After the listeners below have dropped their references.
        QtCore.QTimer.singleShot(0, lambda: self._mosaic_view.dispose(removed))

        if removed:
            self.rect_widgets_removed.emit(removed)

    def deselect(self, rect_widget: RectWidget):
        """
        Deselect a rect widget.
        """
        self._selection.deselect(rect_widget)

    def select(self, rect_widget: RectWidget, clear: bool = True):
        """
        Select a rect widget.
        """
        self._selection.select(rect_widget, clear=clear)

    @property
    def selection_anchor(self) -> RectWidget | None:
        """The anchor widget for Shift-based range selection."""
        return cast("RectWidget | None", self._selection.anchor)

    def select_range(self, first: RectWidget, last: RectWidget, add: bool = False):
        """
        Select a range of rect widgets.
        """
        self._selection.select_range(first, last, add=add)

    def select_all(self) -> None:
        """Select every tile currently shown (filters respected)."""
        self._selection.select_all()

    def clear_selected(self):
        """
        Clear the selection of rect widgets.
        """
        self._selection.clear_selected()

    @QtCore.pyqtSlot(list)
    def _on_selection_changed(self, selected: list[RectWidget]) -> None:
        self._selection.update_widget_selection_flags(selected)

    def select_relative(self, key: QtCore.Qt.Key, *, shift: bool = False) -> bool:
        """
        Select a rect widget relative to the currently selected one.

        Args:
            key: The key pressed.
            shift: When ``True``, extend the current selection instead of replacing it.
        """
        return self._selection.select_relative(
            key=key,
            columns=self._n_columns,
            activate_callback=lambda widget: self._rect_clicked_slot(widget, None),
            shift=shift,
        )

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
            shift = bool(
                key_event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
            )
            if self.select_relative(cast(QtCore.Qt.Key, key_event.key()), shift=shift):
                # Consume handled arrow keys so QGraphicsView doesn't auto-scroll.
                return True
        return super().eventFilter(source, event)
