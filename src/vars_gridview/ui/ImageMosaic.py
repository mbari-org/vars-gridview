"""
Image mosaic widget manager.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from json import loads
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

import pyqtgraph as pg
from iso8601 import parse_date
from PyQt6 import QtCore, QtWidgets
from pydantic import BaseModel, ValidationError

from vars_gridview.lib.association import BoundingBoxAssociation
from vars_gridview.lib.constants import SETTINGS
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.observation import Observation
from vars_gridview.lib.sort_methods import SortMethod
from vars_gridview.lib.utils import get_timestamp
from vars_gridview.ui.RectWidget import RectWidget

if TYPE_CHECKING:
    from vars_gridview.lib.embedding import Embedding


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
    def parse(cls, headers: List[str], row: List[str]) -> "Row":
        """
        Parse a row of data into a Row object.

        Args:
            headers (List[str]): The headers of the data.
            row (List[str]): The row of data.

        Returns:
            Row: The parsed row.

        Raises:
            pydantic.ValidationError: If the row is invalid.
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
    """
    Manager of the image mosaic widget
    """

    def __init__(
        self,
        graphics_view: QtWidgets.QGraphicsView,
        rect_clicked_slot: callable,
        embedding_model: Optional["Embedding"] = None,
    ):
        super().__init__()

        # Initialize the graphics
        self._graphics_view = graphics_view
        self._graphics_scene = QtWidgets.QGraphicsScene()
        self._graphics_widget = QtWidgets.QGraphicsWidget()
        self._init_graphics()

        self._rect_clicked_slot = rect_clicked_slot
        self._embedding_model = embedding_model

        self._rect_widgets: List[RectWidget] = []
        self._n_columns = 0

        # Display flags
        self.hide_labeled = False
        self.hide_unlabeled = False
        self.hide_training = False
        self.hide_nontraining = False

        # Metadata caches
        self.image_reference_urls = {}
        self.association_groups: Dict[UUID, List[BoundingBoxAssociation]] = {}
        self.observations: Dict[UUID, Observation] = {}
        self.moment_video_data = {}
        self.moment_mp4_data = {}
        self.moment_timestamps = {}
        self.video_reference_uuid_to_mp4_video_reference = {}
        self.video_sequences_by_name = {}
        self.moment_ancillary_data = {}

        self.n_images = 0
        self.n_localizations = 0

        SETTINGS.gui_zoom.valueChanged.connect(self.zoom_updated)

    def populate(self, query_headers: List[str], query_rows: List[List[str]]) -> None:
        """
        Populate the image mosaic with query data. Update internal metadata caches by fetching needed info from M3.

        Args:
            query_headers (List[str]): The headers of the query results.
            query_rows (List[List[str]]): The rows of the query results.
        """
        # Clear derived association groups
        self.association_groups.clear()

        # Clear existing widgets
        self._rect_widgets.clear()

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

            # Derive and map MP4 image metadata
            self._map_mp4_data(rows)

            # Create the ROI widgets
            self._create_rois()
        except Cancelled:
            LOGGER.info("Image mosaic loading cancelled by user")
            return

    def _map_metadata(self, rows: List[Row]) -> None:
        """
        Map the given rows to populate internal lookup tables.

        Args:
            rows (List[Row]): The rows of data.
        """
        for row in rows:
            # Map image_reference_uuid -> image_url
            if row.image_reference_uuid not in self.image_reference_urls:
                self.image_reference_urls[row.image_reference_uuid] = row.image_url

            # Map observation_uuid -> observation
            if row.observation_uuid not in self.observations:
                try:
                    observation = Observation(
                        uuid=row.observation_uuid,
                        concept=row.concept,
                        observer=row.observer,
                        group=row.observation_group,
                        imaged_moment_uuid=row.imaged_moment_uuid,
                    )
                except ValidationError as e:
                    LOGGER.error(
                        f"Error creating observation {row.observation_uuid} due to missing/invalid field: {e}"
                    )
                    continue
                self.observations[row.observation_uuid] = observation

            # Map imaged_moment_uuid -> ancillary data
            # Note: this assumes a single imaged moment UUID will not have multiple ancillary data entries. This is a safe assumption for now but is not strictly necessary
            if row.imaged_moment_uuid not in self.moment_ancillary_data:
                ancillary = {
                    "camera_platform": row.camera_platform,
                    "video_sequence_name": row.video_sequence_name,
                    "depth_meters": row.depth_meters,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "oxygen_ml_per_l": row.oxygen_ml_per_l,
                    "pressure_dbar": row.pressure_dbar,
                    "salinity": row.salinity,
                    "temperature_celsius": row.temperature_celsius,
                    "light_transmission": row.light_transmission,
                }
                ancillary = {k: v for k, v in ancillary.items() if v is not None}
                self.moment_ancillary_data[row.imaged_moment_uuid] = ancillary

            # Map imaged_moment_uuid -> video data
            if (
                row.video_uri is not None
                and row.imaged_moment_uuid not in self.moment_video_data
            ):
                video_data = {
                    "index_elapsed_time_millis": row.index_elapsed_time_millis,
                    "index_timecode": row.index_timecode,
                    "index_recorded_timestamp": row.index_recorded_timestamp,
                    "video_start_timestamp": row.video_start_timestamp,
                    "video_uri": row.video_uri,
                    "video_container": row.video_container,
                    "video_reference_uuid": row.video_reference_uuid,
                    "video_sequence_name": row.video_sequence_name,
                    "video_width": row.video_width,
                    "video_height": row.video_height,
                }
                video_data = {k: v for k, v in video_data.items() if v is not None}
                self.moment_video_data[row.imaged_moment_uuid] = video_data

    def _extract_associations(self, rows: List[Row]):
        """
        Extract bounding box associations from the given rows.

        Args:
            rows (List[Row]): The rows of data.
        """
        seen_associations = set()
        for row in rows:
            # Skip if the row is something other than a bounding box association
            if row.link_name != "bounding box":
                continue

            # Skip if we've already seen this association
            if row.association_uuid in seen_associations:
                continue
            seen_associations.add(row.association_uuid)

            # Skip if the video start timestamp is not set
            if row.video_start_timestamp is None:
                LOGGER.warning(
                    f"Imaged moment {row.imaged_moment_uuid} has no video start timestamp, skipping"
                )
                continue

            # Skip if the video sequence name is not set
            if row.video_sequence_name is None:
                LOGGER.warning(
                    f"Imaged moment {row.imaged_moment_uuid} has no video sequence name, skipping"
                )
                continue

            # Parse the bounding box association
            observation = self.observations.get(row.observation_uuid, None)
            if observation is None:
                LOGGER.warning(
                    f"Association {row.association_uuid} has invalid observation {row.observation_uuid}, skipping"
                )
                continue
            try:
                box_data = loads(row.link_value)
            except Exception as e:
                LOGGER.error(
                    f"Error parsing JSON for bounding box association {row.association_uuid}: {e}"
                )
                continue
            try:
                association = BoundingBoxAssociation(
                    row.association_uuid,
                    box_data,
                    observation,
                    row.to_concept,
                )
            except (KeyError, ValueError) as e:
                LOGGER.error(
                    f"Invalid bounding box for association {row.association_uuid}: {e}"
                )
                continue
            except Exception as e:
                LOGGER.error(
                    f"Unexpected error while creating bounding box association {row.association_uuid}: {e}",
                    exc_info=True,
                )
                continue

            # Each group corresponds to an image to be downloaded.
            # The key is the imaged moment UUID + image reference UUID.
            # This is done to support when a bounding box association is tied to an image reference that is not under its annotation's imaged moment.
            # Under this model (so as not to break anything) localizations for the same image reference but different imaged moments will be grouped SEPARATELY. This is not ideal but is the best we can do for now.
            group_key = (row.imaged_moment_uuid, association.image_reference_uuid)

            if group_key not in self.association_groups:
                self.association_groups[group_key] = []
            self.association_groups[group_key].append(association)

    def _fetch_video_sequence_data(self) -> None:
        # Identify the set of video sequence names we need to fetch
        video_sequence_names = set(
            video_data["video_sequence_name"]
            for video_data in self.moment_video_data.values()
            if video_data.get("video_sequence_name", None) is not None
        )

        # Remove any video sequence names we've already fetched
        video_sequence_names -= set(self.video_sequences_by_name.keys())

        # Fetch video sequence data
        with (
            pg.ProgressDialog(
                "Fetching video sequence data...", maximum=len(video_sequence_names)
            ) as progress,
            ThreadPoolExecutor(max_workers=10) as executor,
        ):
            vs_futures = []

            # Submit video sequence lookup tasks
            for video_sequence_name in video_sequence_names:
                vs_future = executor.submit(
                    operations.get_video_sequence_by_name, video_sequence_name
                )
                vs_futures.append(vs_future)

            # Wait for all video sequence lookups to complete
            for vs_future in as_completed(vs_futures):
                if progress.wasCanceled():
                    for future in vs_futures:
                        future.cancel()
                    executor.shutdown(wait=False)
                    raise Cancelled
                try:
                    video_sequence_data = vs_future.result()
                except Exception as e:
                    LOGGER.error(
                        f"Failed to get video sequence data for {video_sequence_name}: {e}"
                    )
                    video_sequence_data = None

                # Store in dict
                self.video_sequences_by_name[video_sequence_data["name"]] = (
                    video_sequence_data
                )

                progress += 1

    def _map_mp4_data(self, rows: List[Row]) -> None:
        for row in rows:
            if row.imaged_moment_uuid not in self.moment_mp4_data:
                # Get imaged moment's time index
                moment_timestamp = get_timestamp(
                    row.video_start_timestamp,
                    row.index_recorded_timestamp,
                    row.index_elapsed_time_millis,
                    row.index_timecode,
                )
                self.moment_timestamps[row.imaged_moment_uuid] = moment_timestamp

                if moment_timestamp is None:  # No timestamp, can't use
                    continue

                # Find the corresponding MP4 video reference (in the same video sequence) for this imaged moment, if there is one
                mp4_video_data = self.find_mp4_video_data(
                    row.video_sequence_name, moment_timestamp
                )

                if mp4_video_data is not None:
                    LOGGER.debug(
                        f"Found MP4 video reference {mp4_video_data['video_reference']['uuid']} for imaged moment {row.imaged_moment_uuid}"
                    )
                else:
                    LOGGER.warning(
                        f"Could not find MP4 video reference for imaged moment {row.imaged_moment_uuid}"
                    )

                self.moment_mp4_data[row.imaged_moment_uuid] = mp4_video_data

    def _create_rois(self) -> None:
        # Create the ROIs
        self.n_images = 0
        self.n_localizations = 0
        failed_rects = []  # List to keep track of failed rect widgets
        with (
            pg.ProgressDialog(
                "Creating ROIs...",
                0,
                sum(len(group) for group in self.association_groups.values()),
            ) as dlg,
            ThreadPoolExecutor(max_workers=10) as executor,
        ):
            rw_futures = []
            for group_key, associations in self.association_groups.items():
                imaged_moment_uuid, image_reference_uuid = group_key

                # Scale factors. Needed if the image is not the same size as the annotation's source image
                scale_x = 1.0
                scale_y = 1.0

                source_url = None
                elapsed_time_millis = None
                if image_reference_uuid is None:
                    # No image reference, need to use beholder
                    video_data = self.moment_video_data[imaged_moment_uuid]

                    source_width = video_data["video_width"]
                    source_height = video_data["video_height"]

                    # Find the video URI of the MP4 video
                    original_video_reference_uuid = video_data["video_reference_uuid"]
                    if original_video_reference_uuid is None:
                        LOGGER.error(
                            f"Imaged moment {imaged_moment_uuid} has no video reference, skipping"
                        )
                        continue

                    mp4_video_data = self.moment_mp4_data.get(imaged_moment_uuid, None)
                    if mp4_video_data is None:
                        LOGGER.warning(
                            f"Imaged moment {imaged_moment_uuid} has no MP4 video reference, skipping"
                        )
                        continue

                    # Get the MP4 video data
                    mp4_video_reference_uri = mp4_video_data["video_reference"]["uri"]
                    mp4_width = mp4_video_data["video_reference"]["width"]
                    mp4_height = mp4_video_data["video_reference"]["height"]
                    mp4_video_start_timestamp = parse_date(
                        mp4_video_data["video"]["start_timestamp"]
                    )  # datetime
                    moment_timestamp = self.moment_timestamps[imaged_moment_uuid]

                    # Compute the offset in milliseconds
                    elapsed_time_millis = round(
                        (moment_timestamp - mp4_video_start_timestamp).total_seconds()
                        * 1000
                    )

                    scale_x = source_width / mp4_width
                    scale_y = source_height / mp4_height

                    source_url = mp4_video_reference_uri

                else:
                    # We have an image reference UUID, so we can get the image directly
                    # Get the URL for the image reference, if we have it
                    url = self.image_reference_urls.get(image_reference_uuid, None)

                    # If we don't have the image reference URL (wasn't fetched during query), try to fetch it and update the URL
                    if url is None:
                        LOGGER.debug(
                            f"Fetching image reference {image_reference_uuid} from M3"
                        )
                        try:
                            image_reference = operations.get_image_reference(
                                image_reference_uuid
                            )
                        except Exception as e:
                            LOGGER.error(
                                f"Error getting image reference {image_reference_uuid}: {e}"
                            )
                            continue

                        # Update the URL
                        url = image_reference.get("url", None)

                        # Skip if missing URL
                        if url is None:
                            LOGGER.error(
                                f"Image reference {image_reference_uuid} has no URL, skipping"
                            )
                            continue

                    source_url = url

                self.n_images += 1

                ancillary_data = (
                    self.moment_ancillary_data.get(imaged_moment_uuid, None) or {}
                )
                video_data = self.moment_video_data.get(imaged_moment_uuid, None) or {}

                # Create the widgets
                for association in associations:
                    other_locs = list(associations)
                    other_locs.remove(association)
                    rw_future = executor.submit(
                        RectWidget,
                        other_locs + [association],
                        source_url,
                        ancillary_data,
                        video_data,
                        len(other_locs),
                        self._rect_clicked_slot,
                        self._similarity_sort_slot,
                        text_label=association.text_label,
                        embedding_model=self._embedding_model,
                        scale_x=scale_x,
                        scale_y=scale_y,
                        elapsed_time_millis=elapsed_time_millis,
                    )
                    rw_future.association_uuid = association.uuid
                    rw_futures.append(rw_future)

            for rw_future in as_completed(rw_futures):
                if dlg.wasCanceled():
                    for future in rw_futures:
                        future.cancel()
                    executor.shutdown(wait=False)
                    raise Cancelled
                try:
                    rw = rw_future.result()
                    self._rect_widgets.append(rw)
                except Exception as e:
                    LOGGER.error(f"Error creating rect widget: {e}")
                    failed_rects.append(
                        rw_future.association_uuid
                    )  # Add the bounding box association UUID to the list of failed rects
                self.n_localizations += 1
                dlg += 1

        # Show a dialog summarizing any rect widgets that could not be loaded
        if failed_rects:
            error_message = "\n".join(list(map(str, failed_rects)))
            QtWidgets.QMessageBox.warning(
                self._graphics_view,
                "Failed to Create ROIs",
                f"The following bounding box associations could not be loaded:\n{error_message}",
            )

    def _similarity_sort_slot(self, clicked_rect: RectWidget, same_class_only: bool):
        def key(rect_widget: RectWidget) -> float:
            if same_class_only and clicked_rect.text_label != rect_widget.text_label:
                return float("inf")
            return clicked_rect.embedding_distance(rect_widget)

        # Sort the rects by distance
        self._rect_widgets.sort(key=key)

        # Re-render the mosaic
        self.render_mosaic()

    def update_embedding_model(self, embedding_model: "Embedding"):
        self._embedding_model = embedding_model
        for rect_widget in self._rect_widgets:
            rect_widget.update_embedding_model(embedding_model)
            rect_widget.update_embedding()

    @QtCore.pyqtSlot(object)
    def zoom_updated(self, zoom: float):
        for rect_widget in self._rect_widgets:
            rect_widget.update_zoom(zoom)
        self.render_mosaic()

    def find_mp4_video_data(
        self, video_sequence_name: str, timestamp: datetime
    ) -> Optional[dict]:
        """
        Find a video with an MP4 video reference for the given video sequence name and timestamp.

        Args:
            video_sequence_name: The video sequence name
            timestamp: The timestamp

        Returns:
            The matching video data dict, or None if no match found
        """
        if (
            video_sequence_name not in self.video_sequences_by_name
        ):  # Video sequence not encountered
            return None

        video_sequence = self.video_sequences_by_name[video_sequence_name]

        if video_sequence is None:  # No info about this video sequence
            return None

        videos = video_sequence.get("videos", [])
        for video in videos:
            video_duration_millis = video.get("duration_millis", None)
            if video_duration_millis is None:  # No duration
                continue

            video_start_timestamp = video.get("start_timestamp", None)
            if video_start_timestamp is None:  # No start timestamp
                continue

            # Compute datetime start-end range
            video_start_timestamp = parse_date(video_start_timestamp)
            video_end_timestamp = video_start_timestamp + timedelta(
                milliseconds=video_duration_millis
            )

            if not (
                video_start_timestamp <= timestamp <= video_end_timestamp
            ):  # Timestamp not in range
                continue

            video_references = video.get("video_references", [])
            for video_reference in video_references:
                container = video_reference.get("container", None)
                if container is None:  # No container
                    continue

                if container != "video/mp4":  # Unsupported container
                    continue

                return {
                    "video": video,
                    "video_reference": video_reference,
                }

    def sort_rect_widgets(self, sort_method: SortMethod):
        """
        Sort the rect widgets

        Args:
            sort_method: The sort method to use
        """
        sort_method.sort(self._rect_widgets)

    def _init_graphics(self):
        """
        Initialize the graphics scene, widget, and layout
        """
        # Assign the graphics scene to the view
        self._graphics_view.setScene(self._graphics_scene)

        # Add the single graphics widget to the scene
        self._graphics_scene.addItem(self._graphics_widget)

        # Create the QGraphicsLayout
        layout = QtWidgets.QGraphicsGridLayout()

        # Set layout properties
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(0)

        self._graphics_view.installEventFilter(self)

        # Assign the layout to the widget
        self._graphics_widget.setLayout(layout)

    def _clear_graphics_layout(self):
        """
        Remove all widgets from the layout
        """
        while self._graphics_widget.layout().count() > 0:
            self._graphics_widget.layout().removeAt(0)

    def clear_view(self) -> None:
        """
        Clear the graphics view without deleting the underlying RectWidgets.
        Hides all rect widgets and clears the layout.
        """
        # Hide all rect widgets
        for rect_widget in self._rect_widgets:
            rect_widget.hide()

        # Clear the graphics layout (removes widgets from layout but doesn't delete them)
        self._clear_graphics_layout()

        # Update the scene rect to be minimal
        self._graphics_scene.setSceneRect(QtCore.QRectF())

    def render_mosaic(self):
        """
        Load images + annotations and populate the mosaic
        """
        if self._graphics_scene is None:
            raise ValueError("Graphics not initialized; call _init_graphics() first")

        # Get the viewport width (without margins) and compute the number of columns
        left, top, right, bottom = self._graphics_widget.layout().getContentsMargins()
        width = self._graphics_view.viewport().width() - left - right
        if self._rect_widgets:
            rect_widget_width = self._rect_widgets[0].boundingRect().width()
            rect_widget_height = self._rect_widgets[0].boundingRect().height()
            columns = max(int(width / rect_widget_width), 1)
        else:
            rect_widget_width = 0
            rect_widget_height = 0
            columns = 1  # No widgets, so just one column

        # Clear the graphics
        self._clear_graphics_layout()

        # Get the subset of rect widgets to render based on display flags
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

        # Hide all rect widgets that we aren't rendering
        rect_widgets_to_hide = [
            rw for rw in self._rect_widgets if rw not in rect_widgets_to_render
        ]
        for rw in rect_widgets_to_hide:
            rw.hide()

        # Add the rect widgets to the layout
        for idx, rect_widget in enumerate(rect_widgets_to_render):
            row = int(idx / columns)
            col = idx % columns
            self._graphics_widget.layout().addItem(rect_widget, row, col)
            rect_widget.show()  # Make sure it's visible

        # Resize the widget to fit the rect widget grid
        self._graphics_widget.resize(
            columns * rect_widget_width, rect_widget_height * len(self._rect_widgets)
        )
        self._graphics_scene.setSceneRect(self._graphics_widget.boundingRect())

        self._n_columns = columns

    def label_selected(self, concept: Optional[str], part: Optional[str]):
        """
        Apply a label to the selected rect widgets.

        Args:
            concept: The concept to apply. If None, the existing concept will be used.
            part: The part to apply. If None, the existing part will be used.
        """
        for rect in self.get_selected():
            # Set the new concept and immediately push to VARS
            rect.association.set_verified_concept(
                concept if concept is not None else rect.association.concept,
                part if part is not None else rect.association.part,
                SETTINGS.username.value,
            )

            try:
                rect.association.push_changes()
            except Exception as e:
                LOGGER.error(
                    f"Error pushing changes for localization {rect.association.uuid}: {e}"
                )
                QtWidgets.QMessageBox.critical(
                    self._graphics_view,
                    "Error",
                    f"An error occurred while pushing changes for localization {rect.association.uuid}.",
                )

            # Update the widget's text label and deselect it
            rect.text_label = rect.association.text_label
            rect.is_selected = False

            # Propagate visual changes
            rect.update()

        self.render_mosaic()

    def verify_selected(self):
        """
        Verify the selected rect widgets.
        """
        self.label_selected(None, None)  # Use existing concept and part

    def unverify_selected(self):
        """
        Unverify the selected rect widgets.
        """
        for rect in self.get_selected():
            # Unverify the localization and immediately push to VARS
            rect.association.unverify()

            try:
                rect.association.push_changes()
            except Exception as e:
                LOGGER.error(
                    f"Error pushing changes for localization {rect.association.uuid}: {e}"
                )
                QtWidgets.QMessageBox.critical(
                    self._graphics_view,
                    "Error",
                    f"An error occurred while pushing changes for localization {rect.association.uuid}.",
                )

            # Update the widget's text label and deselect it
            rect.text_label = rect.association.text_label
            rect.is_selected = False

            # Propagate visual changes
            rect.update()

    def mark_training_selected(self) -> None:
        """
        Mark the selected rect widgets for training.
        """
        for rect in self.get_selected():
            # Mark the localization for training and immediately push to VARS
            rect.association.mark_for_training()

            try:
                rect.association.push_changes()
            except Exception as e:
                LOGGER.error(
                    f"Error pushing changes for localization {rect.association.uuid}: {e}"
                )
                QtWidgets.QMessageBox.critical(
                    self._graphics_view,
                    "Error",
                    f"An error occurred while pushing changes for localization {rect.association.uuid}.",
                )

            # Update the widget's text label and deselect it
            rect.text_label = rect.association.text_label
            rect.is_selected = False

            # Propagate visual changes
            rect.update()

        self.render_mosaic()

    def unmark_training_selected(self) -> None:
        """
        Unmark the selected rect widgets for training.
        """
        for rect in self.get_selected():
            # Unmark the localization for training and immediately push to VARS
            rect.association.unmark_for_training()

            try:
                rect.association.push_changes()
            except Exception as e:
                LOGGER.error(
                    f"Error pushing changes for localization {rect.association.uuid}: {e}"
                )
                QtWidgets.QMessageBox.critical(
                    self._graphics_view,
                    "Error",
                    f"An error occurred while pushing changes for localization {rect.association.uuid}.",
                )

            # Update the widget's text label and deselect it
            rect.text_label = rect.association.text_label
            rect.is_selected = False

            # Propagate visual changes
            rect.update()

        self.render_mosaic()

    def get_selected(self) -> List[RectWidget]:
        """
        Get a list of the selected rect widgets

        Returns:
            List of selected widgets
        """
        return [rw for rw in self._rect_widgets if rw.is_selected]

    def delete_selected(self):
        """
        Delete all selected rect widgets and re-render.

        The logic for handling the association/observation is handled here.
        1. If the selected localizations are the only localizations for an observation, add the observation to a list
        2. Show a dialog to the user asking if they want to also delete the observations
        3. If the user says yes, delete the observations
        4. If no, delete the bounding box associations only
        """
        selected = self.get_selected()

        bounding_box_association_uuids_to_delete = [
            rw.association.uuid for rw in selected
        ]

        observation_uuids = [rw.association.observation.uuid for rw in selected]

        # Get the UUIDs of the bounding box associations tied to the observations
        bounding_box_association_uuids_by_observation_uuid = dict()
        with pg.ProgressDialog(
            "Checking parent observations...",
            0,
            len(observation_uuids),
            parent=self._graphics_view,
        ) as obs_pd:
            for observation_uuid in set(observation_uuids):
                if observation_uuid not in bounding_box_association_uuids_to_delete:
                    bounding_box_association_uuids_by_observation_uuid[
                        observation_uuid
                    ] = []

                try:
                    observation = operations.get_observation(
                        observation_uuid
                    )  # Get the observation data from VARS
                    for association in observation.get("associations"):
                        if association.get("link_name") == "bounding box":
                            association_uuid = UUID(association.get("uuid"))

                            # Add the association UUID to the list for this observation UUID
                            bounding_box_association_uuids_by_observation_uuid[
                                observation_uuid
                            ].append(association_uuid)
                except Exception as e:
                    LOGGER.error(f"Error getting observation {observation_uuid}: {e}")

                obs_pd += 1

        # Select the subset of observations that will have no more bounding box associations after deleting the selected ones
        dangling_observations_uuids_to_delete = [
            observation_uuid
            for observation_uuid in observation_uuids
            if len(
                set(
                    bounding_box_association_uuids_by_observation_uuid[observation_uuid]
                )
                - set(bounding_box_association_uuids_to_delete)
            )
            == 0
        ]

        if len(dangling_observations_uuids_to_delete) > 0:
            # Show a dialog to the user asking if they want to delete observations too
            confirm = QtWidgets.QMessageBox.question(
                self._graphics_view,
                "Delete dangling observations?",
                f"This operation would leave {len(dangling_observations_uuids_to_delete)} observations with no bounding box associations. Would you like to delete these dangling observations too?",
            )

            if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
                delete_observations = True
            else:
                delete_observations = False
        else:  # No dangling observations, so just delete the localizations
            delete_observations = False

        # De-select the deleted widgets
        self.clear_selected()

        # Delete the observations/associations for the selected widgets and hide them
        with pg.ProgressDialog(
            f"Deleting localizations{' and dangling observations' if delete_observations else ''}...",
            0,
            len(selected),
            parent=self._graphics_view,
        ) as pd:
            for rw in selected:
                delete_observation = (
                    delete_observations
                    and rw.association.observation.uuid
                    in dangling_observations_uuids_to_delete
                )  # Only delete the observation if it's in the list of dangling observations
                rw.delete(observation=delete_observation)
                rw.hide()
                self._rect_widgets.remove(rw)
                pd += 1

        scroll_bar = self._graphics_view.verticalScrollBar()
        scroll_position = scroll_bar.value()

        # Re-render to ensure the deleted widgets are removed from the view
        self.clear_view()
        self.render_mosaic()

        QtCore.QTimer.singleShot(50, lambda: scroll_bar.setValue(scroll_position))

    def deselect(self, rect_widget: RectWidget):
        """
        Deselect a rect widget.
        """
        if rect_widget not in self._rect_widgets:
            raise ValueError("Widget not in rect widget list")

        # Deselect the widget
        rect_widget.is_selected = False
        rect_widget.update()

    def select(self, rect_widget: RectWidget, clear: bool = True):
        """
        Select a rect widget.
        """
        if rect_widget not in self._rect_widgets:
            raise ValueError("Widget not in rect widget list")

        # Clear the selection if requested
        if clear:
            self.clear_selected()

        # Select the widget
        rect_widget.is_selected = True
        rect_widget.update()

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
        self.clear_selected()
        for idx in range(begin_idx, end_idx + 1):
            # Only select if it's visible
            if self._rect_widgets[idx].isVisible():
                self._rect_widgets[idx].is_selected = True
                self._rect_widgets[idx].update()

    def clear_selected(self):
        """
        Clear the selection of rect widgets.
        """
        for ind in range(0, len(self._rect_widgets)):
            self._rect_widgets[ind].is_selected = False
            self._rect_widgets[ind].update()

    def select_relative(self, key: QtCore.Qt.Key):
        """
        Select a rect widget relative to the currently selected one.

        Args:
            key: The key pressed
        """
        selected = self.get_selected()
        if len(selected) == 0:
            return

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
            return

        # Select the next widget if it's in bounds
        if 0 <= next_idx < len(self._rect_widgets):
            self.clear_selected()
            self._rect_clicked_slot(self._rect_widgets[next_idx], None)
            self.render_mosaic()

    def eventFilter(self, source, event):
        if source is self._graphics_view and event.type() == QtCore.QEvent.Type.Resize:
            self.render_mosaic()  # Re-render when the view is resized
        if (
            source is self._graphics_view
            and event.type() == QtCore.QEvent.Type.KeyPress
        ):
            self.select_relative(event.key())
        return super().eventFilter(source, event)
