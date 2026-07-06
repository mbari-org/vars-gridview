"""Image mosaic widget manager.

Manages a grid of :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
tiles, and handles metadata loading, ROI creation, sorting, selection, and
CRUD operations on bounding-box annotations.
"""

from __future__ import annotations

from datetime import datetime
from threading import Event
from typing import TYPE_CHECKING, Any, Callable, List, cast
from uuid import UUID

from iso8601 import parse_date
from PyQt6 import QtCore, QtGui, QtWidgets
from pydantic import BaseModel

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.sorting.sort_methods import SortMethod, SortMethodGroup
from vars_gridview.controllers.selection_model import SelectionModel
from vars_gridview.services.localization_store import LocalizationStore
from vars_gridview.services.mosaic_pipeline import MosaicPipeline
from vars_gridview.services.roi_loader import RoiLoadResult, RoiLoader
from vars_gridview.ui.coordinators.mosaic_load_coordinator import MosaicLoadCoordinator
from vars_gridview.ui.coordinators.mosaic_selection_coordinator import (
    MosaicSelectionCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_roi_loading_coordinator import (
    MosaicRoiLoadingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    MosaicSimilarityCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_embedding_coordinator import (
    MosaicEmbeddingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_tile_action_coordinator import (
    MosaicTileActionCoordinator,
)
from vars_gridview.ui.mosaic.mosaic_view import MosaicView, MosaicVisibilityFilters
from vars_gridview.ui.mosaic.rect_widget_factory import RectWidgetFactory
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
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid {key}: {timestamp_raw}") from exc

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
    video_sequence_prepare_progress = QtCore.pyqtSignal(int, int)
    proxy_prepare_progress = QtCore.pyqtSignal(int, int)
    roi_spec_prepare_progress = QtCore.pyqtSignal(int, int)
    localization_prepare_progress = QtCore.pyqtSignal(int, int)

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

        self._rect_widgets: List[RectWidget] = []
        self._n_columns = 0
        self.selection_model = SelectionModel(parent=self)
        self.selection_model.selection_changed.connect(self._on_selection_changed)
        self._selection = MosaicSelectionCoordinator(
            parent=self,
            selection_model=self.selection_model,
            mosaic_view=self._mosaic_view,
            all_widgets_getter=lambda: self._rect_widgets,
        )

        # Display flags
        self.hide_labeled = False
        self.hide_unlabeled = False
        self.hide_training = False
        self.hide_nontraining = False

        # Non-Qt data store backing metadata and association groups.
        self.store = LocalizationStore()
        self._mosaic_pipeline = MosaicPipeline()
        self._roi_loader = RoiLoader()
        self.video_reference_uuid_to_mp4_video_reference = {}

        self.n_images = 0
        self.n_localizations = 0
        self._embedding_generation = 0
        self._load_coordinator = MosaicLoadCoordinator(
            parent=self,
            dialog_parent=self._graphics_view,
        )
        self._roi_loading = MosaicRoiLoadingCoordinator(
            parent=self,
            dialog_parent=self._graphics_view,
            max_concurrency=4,
        )
        self._similarity = MosaicSimilarityCoordinator(
            parent=self,
            dialog_parent=self._dialog_parent,
            rect_widgets_getter=lambda: self._rect_widgets,
            apply_sorted_indices=self._apply_sorted_indices,
            sort_unavailable_callback=self._on_similarity_unavailable,
        )
        self._embedding = MosaicEmbeddingCoordinator(
            parent=self,
            dialog_parent=self._dialog_parent,
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

    def populate(self, query_headers: list[str], query_rows: list[list[str]]) -> None:
        """Populate the mosaic from raw VARS query output.

        Clears any previous state, parses the rows, fetches ancillary
        metadata from M3, and creates a :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`
        for every bounding-box association found.

        Args:
            query_headers: Column names as returned by the query endpoint.
            query_rows: One inner list per result row.
        """
        # Clear existing widgets
        self._roi_loading.cancel_pending()
        self._rect_widgets.clear()
        self.selection_model.clear()

        try:
            # Parse rows and build localization store off the UI thread.
            rows = self._prepare_localization_data(query_headers, query_rows)

            # Fetch video sequence data for the given groups
            self._fetch_video_sequence_data()

            # Derive and map proxy image metadata
            self._map_proxy_data(rows)

            # Create the ROI widgets
            self._create_rois()
        except Cancelled:
            LOGGER.info("Image mosaic loading cancelled by user")
            return

    def _prepare_localization_data(
        self,
        query_headers: list[str],
        query_rows: list[list[str]],
    ) -> list[Row]:
        """Parse rows and build localization state off the UI thread."""
        cached_image_reference_urls = dict(self.store.image_reference_urls)
        cached_video_sequences_by_name = dict(self.store.video_sequences_by_name)

        payload = self._run_cancellable_stage(
            label="Preparing localization data...",
            maximum=max(0, len(query_rows)),
            cancelled_message="Localization preparation cancelled",
            missing_result_message="Localization preparation returned no result",
            worker_factory=lambda cancel_event,
            progress_callback: self._mosaic_pipeline.build_localization_state(
                query_rows=query_rows,
                row_parser=lambda row: Row.parse(query_headers, row),
                cached_image_reference_urls=cached_image_reference_urls,
                cached_video_sequences_by_name=cached_video_sequences_by_name,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                cancelled_message="Localization preparation cancelled",
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

    def _fetch_video_sequence_data(self) -> None:
        if self._vampire_squid_client is None:
            raise RuntimeError(
                "ImageMosaic is missing VampireSquid client; call configure_services() after login"
            )
        self._run_cancellable_stage(
            label="Fetching video sequence data...",
            maximum=0,
            cancelled_message="Video sequence fetch cancelled",
            missing_result_message=None,
            worker_factory=lambda cancel_event,
            progress_callback: self._roi_loader.fetch_video_sequence_data(
                vampire_squid_client=self._vampire_squid_client,
                moment_video_data=self.moment_video_data,
                video_sequences_by_name=self.video_sequences_by_name,
                progress_callback=progress_callback,
                should_cancel=cancel_event.is_set,
            ),
        )

    def _map_proxy_data(self, rows: list[Row]) -> None:
        """Derive proxy video data for each imaged moment in *rows* off-thread."""
        payload = self._run_cancellable_stage(
            label="Preparing proxy mappings...",
            maximum=max(0, len(rows)),
            cancelled_message="Proxy mapping cancelled",
            missing_result_message="Proxy mapping returned no result",
            worker_factory=lambda cancel_event,
            progress_callback: self._mosaic_pipeline.build_proxy_mapping(
                rows=list(rows),
                existing_moment_proxy_data=self.moment_proxy_data,
                existing_moment_timestamps=self.moment_timestamps,
                video_sequences_by_name=self.video_sequences_by_name,
                roi_loader=self._roi_loader,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            ),
        )
        proxy_data, timestamps = cast(
            tuple[dict[UUID, dict | None], dict[UUID, object]],
            payload,
        )
        self.store.moment_proxy_data = proxy_data
        self.store.moment_timestamps = timestamps

    def _create_rois(self) -> None:
        if self._annosaurus_client is None or self._roi_service is None:
            raise RuntimeError(
                "ImageMosaic is missing Annosaurus/ROI services; call configure_services() after login"
            )

        load_result = self._run_cancellable_stage(
            label="Preparing ROI widgets...",
            maximum=0,
            cancelled_message="ROI creation cancelled",
            missing_result_message="ROI spec preparation returned no result",
            worker_factory=lambda cancel_event,
            progress_callback: self._roi_loader.create_widget_specs(
                annosaurus_client=self._annosaurus_client,
                association_groups=self.association_groups,
                moment_video_data=self.moment_video_data,
                moment_proxy_data=self.moment_proxy_data,
                moment_timestamps=self.moment_timestamps,
                image_reference_urls=self.image_reference_urls,
                moment_ancillary_data=self.moment_ancillary_data,
                progress_callback=progress_callback,
                should_cancel=cancel_event.is_set,
            ),
        )
        load_result = cast(RoiLoadResult, load_result)

        rect_widgets, failed_association_uuids = self._build_rect_widgets_from_specs(
            load_result
        )

        self._rect_widgets = rect_widgets
        self.n_images = load_result.n_images
        self.n_localizations = load_result.n_localizations
        self._roi_loading.start_loading(
            rect_widgets=self._rect_widgets,
            on_complete=self._on_all_roi_loaded,
        )

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
        label: str,
        maximum: int,
        cancelled_message: str,
        missing_result_message: str | None,
        worker_factory: Callable[[Event, Callable[[int, int], None]], object],
    ) -> object | None:
        """Run one load stage and normalize cancellation handling."""
        try:
            result = self._load_coordinator.run_stage(
                label=label,
                maximum=maximum,
                cancelled_message=cancelled_message,
                worker_factory=worker_factory,
            )
        except RuntimeError as exc:
            if str(exc) == cancelled_message:
                raise Cancelled from exc
            raise

        if result is None and missing_result_message is not None:
            raise RuntimeError(missing_result_message)
        return result

    def update_embedding_model(self, embedding_model: Embedding | None) -> None:
        """Replace the active embedding model and invalidate cached embeddings."""
        model_changed = self._embedding_model is not embedding_model
        self._embedding_model = embedding_model
        if model_changed:
            self._embedding_generation += 1
        self._embedding.on_model_changed(
            model_changed=model_changed,
            has_model=embedding_model is not None,
        )
        for rect_widget in self._rect_widgets:
            rect_widget.update_embedding_model(embedding_model)
            rect_widget.invalidate_embedding_cache()

    def precompute_embeddings_async(self) -> None:
        """Warm tile embeddings in the background to avoid on-demand UI stalls."""
        self._embedding.request_precompute(
            rect_widgets=self._rect_widgets,
            embedding_model=self._embedding_model,
            generation=self._embedding_generation,
            on_result=self._on_embeddings_precomputed,
            on_unavailable=self._on_embedding_unavailable,
        )

    def _on_all_roi_loaded(self) -> None:
        if self._embedding_model is not None:
            # Compute embeddings in a single worker after all ROI images are ready.
            self.precompute_embeddings_async()

    def _apply_sorted_indices(self, sorted_indices: list[int]) -> None:
        current = list(self._rect_widgets)
        self._rect_widgets = [current[idx] for idx in sorted_indices]
        self.render_mosaic()

    def _on_similarity_unavailable(self, message: str) -> None:
        if self._dialog_parent is None:
            return
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Embedding Model Unavailable",
            message,
        )

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
        rect_widgets_to_render = self._mosaic_view.select_visible_widgets(
            all_widgets=self._rect_widgets,
            filters=MosaicVisibilityFilters(
                hide_labeled=self.hide_labeled,
                hide_unlabeled=self.hide_unlabeled,
                hide_training=self.hide_training,
                hide_nontraining=self.hide_nontraining,
            ),
        )

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
