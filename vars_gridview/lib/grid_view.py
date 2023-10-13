from collections import namedtuple
from typing import Dict, Iterable, List, Tuple
from uuid import UUID

import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.entities import Association, ImageReference, ImagedMoment, Observation, Video, VideoReference, VideoSequence
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import BEHOLDER_CLIENT, operations
from vars_gridview.lib.models import BeholderImageSource, BoundingBox, ImageReferenceImageSource
from vars_gridview.lib.sort_methods import SortMethod
from vars_gridview.lib.sql import query_video_data
from vars_gridview.lib.util import parse_timestamp
from vars_gridview.lib.widgets import RectWidget
from vars_gridview.lib.constants import IMAGE_TYPE


class GridViewController(QtCore.QObject):
    """
    Controller for the grid view.
    """
    
    def __init__(
        self,
        graphics_view: QtWidgets.QGraphicsView,
        query_data: List[List],
        query_headers: List[str],
        rect_clicked_slot: callable,
        verifier: str,
        zoom: float = 1.0,
    ):
        super().__init__()
        
        self._rect_widgets: List[RectWidget] = []
        self.roi_map = {}
        self._hide_labeled = True
        self.hide_discarded = True
        self.hide_to_review = True
        self.layouts = []
        
        # Initialize the graphics
        self._graphics_view: QtWidgets.QGraphicsView = graphics_view
        self._graphics_scene: QtWidgets.QGraphicsScene = None
        self._graphics_widget: QtWidgets.QGraphicsWidget = None
        self._init_graphics()

        self.verifier = verifier

        self.n_images = 0
        self.n_localizations = 0
        
        # Extract the object graph from the query data
        (
            self._video_references_by_uuid,
            self._imaged_moments_by_uuid, 
            self._observations_by_uuid, 
            self._associations_by_uuid, 
            self._image_references_by_uuid
        ) = self._extract_object_graph(query_data, query_headers)
        
        # Get video data
        with pg.ProgressDialog("Querying video data...", cancelText=None, parent=self._graphics_view) as pd:
            (
                self._video_sequences_by_uuid,
                self._videos_by_uuid,
                self._video_references_by_uuid
            ) = self._add_video_data()
        
        # Populate the rect widgets
        with pg.ProgressDialog("Populating rect widgets...", cancelText=None, parent=self._graphics_view) as pd:
            self._bounding_boxes_by_image_source, self._rect_widgets = self._populate_rect_widgets(rect_clicked_slot)

    def _extract_object_graph(self, query_data: List[tuple], query_headers: List[str]) -> Tuple[Dict[UUID, VideoReference], Dict[UUID, ImagedMoment], Dict[UUID, Observation], Dict[UUID, Association], Dict[UUID, ImageReference]]:
        """
        Extract an object graph from the available query data.
        
        Args:
            query_data: List of query data tuples (database rows)
            query_headers: List of query headers (column names)
        
        Returns:
            A tuple of dicts (video references, imaged moments, observations, associations, image references) that are each indexed by UUID.
        """
        Row = namedtuple("Row", query_headers)
        rows = [Row(*i) for i in query_data]
        
        # Extract the underlying entities (object graph) from the query data
        
        # Video references
        video_references_by_uuid = {}
        for row in rows:
            uuid = row.video_reference_uuid
            if uuid is None:
                continue
            
            if uuid in video_references_by_uuid:
                continue
            
            video_reference = VideoReference(
                uuid=uuid,
            )
            
            video_references_by_uuid[uuid] = video_reference
        
        # Image moments
        imaged_moments_by_uuid = {}
        for row in rows:
            uuid = row.imaged_moment_uuid
            if uuid is None:
                continue
            
            if uuid in imaged_moments_by_uuid:
                continue
            
            imaged_moment = ImagedMoment(
                uuid=uuid,
                elapsed_time_millis=row.index_elapsed_time_millis,
                recorded_timestamp=parse_timestamp(row.index_recorded_timestamp),
                timecode=row.index_timecode,
            )
            
            imaged_moments_by_uuid[uuid] = imaged_moment
            
            # Add to video reference
            video_reference_uuid = row.video_reference_uuid
            if video_reference_uuid is not None:
                video_reference = video_references_by_uuid.get(video_reference_uuid, None)
                if video_reference is not None:
                    video_reference.add_imaged_moment(imaged_moment)
        
        # Observations
        observations_by_uuid = {}
        for row in rows:
            uuid = row.observation_uuid
            if uuid is None:
                continue
            
            if uuid in observations_by_uuid:
                continue
            
            observation = Observation(
                uuid=uuid,
                concept=row.concept,
                observer=row.observer,
            )
            
            observations_by_uuid[uuid] = observation
            
            # Add to imaged moment
            imaged_moment_uuid = row.imaged_moment_uuid
            if imaged_moment_uuid is not None:
                imaged_moment = imaged_moments_by_uuid.get(imaged_moment_uuid, None)
                if imaged_moment is not None:
                    imaged_moment.add_observation(observation)
            
        # Associations
        associations_by_uuid = {}
        for row in rows:
            uuid = row.association_uuid
            if uuid is None:
                continue
            
            if uuid in observations_by_uuid:
                continue
            
            association = Association(
                uuid=uuid,
                link_name=row.link_name,
                to_concept=row.to_concept,
                link_value=row.link_value,
            )
            
            associations_by_uuid[uuid] = association
            
            # Add to observation
            observation_uuid = row.observation_uuid
            if observation_uuid is not None:
                observation = observations_by_uuid.get(observation_uuid, None)
                if observation is not None:
                    observation.add_association(association)
        
        # Image references
        image_references_by_uuid = {}
        for row in rows:
            uuid = row.image_reference_uuid
            if uuid is None:
                continue
            
            if uuid in image_references_by_uuid:
                continue
            
            image_reference = ImageReference(
                uuid=uuid,
                format=row.image_format,
                url=row.image_url,
            )
            
            image_references_by_uuid[uuid] = image_reference
            
            # Add to imaged moment
            imaged_moment_uuid = row.imaged_moment_uuid
            if imaged_moment_uuid is not None:
                imaged_moment = imaged_moments_by_uuid.get(imaged_moment_uuid, None)
                if imaged_moment is not None:
                    imaged_moment.add_image_reference(image_reference)
        
        return video_references_by_uuid, imaged_moments_by_uuid, observations_by_uuid, associations_by_uuid, image_references_by_uuid

    def _add_video_data(self) -> Tuple[Dict[UUID, VideoSequence], Dict[UUID, Video], Dict[UUID, VideoReference]]:
        """
        Get video data for according to the video references in the extracted imaged moments.
        
        Returns:
            A tuple of dicts (video sequences, videos, video references) that are each indexed by UUID.
        """
        # Execute the query
        video_reference_uuid_strs = [str(uuid) for uuid in set(imaged_moment.video_reference.uuid for imaged_moment in self._imaged_moments_by_uuid.values())]
        query_data, query_headers = query_video_data(video_reference_uuid_strs)
        
        Row = namedtuple("Row", query_headers)
        rows = [Row(*i) for i in query_data]
        
        # Video sequences
        video_sequences_by_uuid = {}
        for row in rows:
            uuid = row.video_sequence_uuid
            if uuid is None:
                continue
            
            if uuid in video_sequences_by_uuid:
                continue
            
            video_sequence = VideoSequence(
                uuid=uuid,
                name=row.video_sequence_name,
            )
            
            video_sequences_by_uuid[uuid] = video_sequence
        
        # Videos
        videos_by_uuid = {}
        for row in rows:
            uuid = row.video_uuid
            if uuid is None:
                continue
            
            if uuid in videos_by_uuid:
                continue
            
            video = Video(
                uuid=uuid,
                start_time=parse_timestamp(row.video_start_time),
                duration_millis=row.video_duration_millis,
            )
            
            videos_by_uuid[uuid] = video
            
            # Add to video sequence
            video_sequence_uuid = row.video_sequence_uuid
            if video_sequence_uuid is not None:
                video_sequence = video_sequences_by_uuid.get(video_sequence_uuid, None)
                if video_sequence is not None:
                    video_sequence.add_video(video)
        
        # Video references
        video_references_by_uuid = {}
        for row in rows:
            uuid = row.video_reference_uuid
            if uuid is None:
                continue
            
            # Some video references are created during the annotation object graph creation; don't overwrite those, just update their data
            if uuid in self._video_references_by_uuid:
                video_reference = self._video_references_by_uuid[uuid]
                video_reference.uri = row.video_reference_uri
                video_reference.width = row.video_reference_width
                video_reference.height = row.video_reference_height
                video_references_by_uuid[uuid] = video_reference
            else:
                video_reference = VideoReference(
                    uuid=uuid,
                    uri=row.video_reference_uri,
                    width=row.video_reference_width,
                    height=row.video_reference_height,
                )
            
            # Add to video
            video_uuid = row.video_uuid
            if video_uuid is not None:
                video = videos_by_uuid.get(video_uuid, None)
                if video is not None:
                    video.add_video_reference(video_reference)
        
        return video_sequences_by_uuid, videos_by_uuid, video_references_by_uuid

    def _populate_rect_widgets(self, rect_clicked_slot: callable):
        """
        Populate the rect widgets in the grid view.
        
        Args:
            rect_clicked_slot: Slot to connect to the rect widgets' clicked signal
        """
        # Collect and parse bounding box associations
        bounding_boxes: List[BoundingBox] = []
        for association_uuid, association in self._associations_by_uuid.items():
            if association.link_name != "bounding box":
                continue
            
            # Parse the bounding box
            try:
                bounding_box = BoundingBox.from_association(association)
            except BoundingBox.MalformedBoundingBoxError as e:
                LOGGER.error(f"Malformed bounding box for association {association_uuid}: {e}")
                continue
            
            bounding_boxes.append(bounding_box)
        
        # Link the bounding boxes to images
        bounding_boxes_by_image_source = {}
        for bounding_box in bounding_boxes:
            image_source = None
            
            # Check if bounding box has a preferred image reference
            preferred_image_reference_uuid = bounding_box.metadata.get("image_reference_uuid", None)
            if preferred_image_reference_uuid is not None:
                # Get the image reference, if we have it
                image_reference = self._image_references_by_uuid.get(preferred_image_reference_uuid, None)
                
                # If not, fetch it via M3 and cache it
                if image_reference is None:
                    try:
                        image_reference_dict = operations.get_image_reference(preferred_image_reference_uuid)
                        image_reference = ImageReference.from_m3_dict(image_reference_dict)
                    except Exception as e:
                        LOGGER.error(f"Failed to get bounding box preferred image reference {preferred_image_reference_uuid}: {e}")
                        continue
                
                # We got the image reference; use it as the image source
                if image_reference is not None:
                    image_source = ImageReferenceImageSource(image_reference)
                
            else:  # We need to use Beholder
                imaged_moment = bounding_box.association.observation.imaged_moment
                mp4_video_references = self.find_mp4_video_references(imaged_moment)
                if not mp4_video_references:  # No matches
                    LOGGER.warning(f"Could not find MP4 video reference for imaged moment {imaged_moment.uuid}")
                    continue
                elif len(mp4_video_references) > 1:  # Multiple candidates
                    LOGGER.warning(f"Could not resolve MP4 video reference for imaged moment {imaged_moment.uuid}: multiple candidates")
                    continue
                
                mp4_video_reference = mp4_video_references[0]
                
                # Get the image source
                image_source = BeholderImageSource(BEHOLDER_CLIENT, mp4_video_reference, imaged_moment)
            
            if image_source in bounding_boxes_by_image_source:
                bounding_boxes_by_image_source[image_source].append(bounding_box)
            else:
                bounding_boxes_by_image_source[image_source] = [bounding_box]
        
        # Create the rect widgets
        rect_widgets = []
        self.n_images = 0
        self.n_localizations = 0
        for image_source, bounding_boxes in bounding_boxes_by_image_source.items():
            self.n_images += 1
            for bounding_box in bounding_boxes:
                self.n_localizations += 1
                rect_widget = RectWidget(image_source, bounding_box, rect_clicked_slot)
                rect_widgets.append(rect_widget)
        
        return bounding_boxes_by_image_source, rect_widgets

    def find_mp4_video_references(self, imaged_moment: ImagedMoment) -> Iterable[VideoReference]:
        """
        Find all matching MP4 video references for the given imaged moment.
        
        Matches if the video reference URI ends with `.mp4` and the imaged moment is within the video reference's start-end range.
        
        Args:
            bounding_box: The bounding box
        
        Returns:
            The matching MP4 video references.
        """
        video_sequence_videos = imaged_moment.video_reference.video.video_sequence.videos
        video_references = [video_reference for video in video_sequence_videos for video_reference in video.video_references]  # Flattened list of video references for all videos in the video sequence
        
        def match(video_reference: VideoReference) -> bool:
            """
            Predicate to check if the given video reference matches the imaged moment.
            """
            ends_with_mp4 = video_reference.uri.lower().endswith(".mp4")
            
            video = video_reference.video
            
            try:  # Get timestamps
                start_timestamp = video.get_start_timestamp()
                imaged_moment_timestamp = imaged_moment.get_timestamp()
                end_timestamp = video.get_end_timestamp()
            except ValueError:
                return False
            
            if start_timestamp is None or imaged_moment_timestamp is None or end_timestamp is None:
                return False
            
            in_range = start_timestamp <= imaged_moment_timestamp <= end_timestamp
            
            return ends_with_mp4 and in_range
        
        return filter(match, video_references)

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
        if self._graphics_view is None:
            raise ValueError("Graphics view must be set before calling this method")
        elif self._graphics_scene is not None:
            raise ValueError("Graphics already initialized")
        
        # Create and assign the QGraphicsScene
        self._graphics_scene = QtWidgets.QGraphicsScene()
        self._graphics_view.setScene(self._graphics_scene)
        
        # Create the single QGraphicsWidget and add it to the scene
        self._graphics_widget = QtWidgets.QGraphicsWidget()
        self._graphics_scene.addItem(self._graphics_widget)
        
        # Create the QGraphicsLayout
        layout = QtWidgets.QGraphicsGridLayout()
        
        # Set layout properties
        layout.setContentsMargins(50, 50, 50, 50)
        
        self._graphics_view.installEventFilter(self)
        
        # Assign the layout to the widget
        self._graphics_widget.setLayout(layout)
        
    def _clear_graphics_layout(self):
        """
        Remove all widgets from the layout
        """
        while self._graphics_widget.layout().count() > 0:
            self._graphics_widget.layout().removeAt(0)

    def render(self):
        """
        Load images + annotations and populate the view
        """
        if self._graphics_scene is None:
            raise ValueError("Graphics not initialized; call _init_graphics() first")
        
        # Get the viewport width (without margins) and compute the number of columns
        left, top, right, bottom = self._graphics_widget.layout().getContentsMargins()
        width = self._graphics_view.viewport().width() - left - right - 50
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

        # Get the subset of rect widgets to render
        rect_widgets_to_render = [
            rw for rw in self._rect_widgets
            if not (self._hide_labeled and rw.is_verified)
        ]
        
        # Hide all rect widgets that we aren't rendering
        rect_widgets_to_hide = [
            rw for rw in self._rect_widgets
            if rw not in rect_widgets_to_render
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

    def apply_label(self, concept, part):
        """
        Apply a label to the selected rect widgets.
        """
        for rect in self.get_selected():
            # Handle empty concept/part
            if concept.strip() == "":  # No concept specified? Verify as-is
                concept = rect.localization.concept
            if part.strip() == "":  # No part specified? ditto
                part = rect.localization.part

            # Set the new concept and immediately push to VARS
            rect.localization.set_verified_concept(concept, part, self.verifier)
            rect.localization.push_changes(self.verifier)

            # Update the widget's text label and deselect it
            rect.label = rect.localization.text_label
            rect.is_selected = False

            # Propagate visual changes
            rect.update()

        self.render()

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
            rw.localization.association_uuid
            for rw in selected
        ]
        
        observation_uuids = [
            rw.localization.observation_uuid
            for rw in selected
        ]
        
        # Get the UUIDs of the bounding box associations tied to the observations
        bounding_box_association_uuids_by_observation_uuid = dict()
        with pg.ProgressDialog("Checking parent observations...", 0, len(observation_uuids), parent=self._graphics_view) as obs_pd:
            for observation_uuid in set(observation_uuids):
                if observation_uuid not in bounding_box_association_uuids_to_delete:
                    bounding_box_association_uuids_by_observation_uuid[observation_uuid] = []
                
                try:
                    observation = operations.get_observation(observation_uuid)  # Get the observation data from VARS
                    for association in observation.get('associations'):
                        if association.get('link_name') == 'bounding box':
                            association_uuid = association.get('uuid')
                            
                            # Add the association UUID to the list for this observation UUID
                            bounding_box_association_uuids_by_observation_uuid[observation_uuid].append(association_uuid)
                except Exception as e:
                    LOGGER.error(f"Error getting observation {observation_uuid}: {e}")
                
                obs_pd += 1
        
        # Select the subset of observations that will have no more bounding box associations after deleting the selected ones
        dangling_observations_uuids_to_delete = [
            observation_uuid for observation_uuid in observation_uuids
            if len(set(bounding_box_association_uuids_by_observation_uuid[observation_uuid]) - set(bounding_box_association_uuids_to_delete)) == 0
        ]
        
        if len(dangling_observations_uuids_to_delete) > 0:
            # Show a dialog to the user asking if they want to delete observations too
            confirm = QtWidgets.QMessageBox.question(
                self._graphics_view, "Delete dangling observations?",
                f"This operation would leave {len(dangling_observations_uuids_to_delete)} observations with no bounding box associations. Would you like to delete these dangling observations too?"
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
        with pg.ProgressDialog(f"Deleting localizations{' and dangling observations' if delete_observations else ''}...", 0, len(selected), parent=self._graphics_view) as pd:
            for rw in selected:
                delete_observation = delete_observations and rw.localization.observation_uuid in dangling_observations_uuids_to_delete  # Only delete the observation if it's in the list of dangling observations
                rw.delete(observation=delete_observation)
                rw.hide()
                self._rect_widgets.remove(rw)
                pd += 1

        # Re-render to ensure the deleted widgets are removed from the view
        self.render()
    
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

    def update_zoom(self, zoom):
        for rect in self._rect_widgets:
            rect.update_zoom(zoom)
        self.render()
    
    def eventFilter(self, source, event):
        if source is self._graphics_view and event.type() == QtCore.QEvent.Type.Resize:
            self.render()  # Re-render when the view is resized
        return super().eventFilter(source, event)
