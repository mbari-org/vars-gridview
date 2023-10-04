# -*- coding: utf-8 -*-
"""
image_mosaic.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more infomation.

"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

import cv2
import numpy as np
import pyqtgraph as pg
import requests
from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.annotation import VARSLocalization
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3 import operations
from vars_gridview.lib.sort_methods import SortMethod
from vars_gridview.lib.util import get_timestamp, parse_iso
from vars_gridview.lib.widgets import RectWidget
from vars_gridview.lib.constants import IMAGE_TYPE


class ImageMosaic(QtCore.QObject):
    """
    Manager of the image mosaic widget
    """
    
    def __init__(
        self,
        graphics_view: QtWidgets.QGraphicsView,
        query_data: List[List],
        query_headers: List[str],
        rect_clicked_slot: callable,
        verifier: str,
        beholder_url: str,
        beholder_api_key: str,
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

        self.moment_image_data = {}
        self.moment_localizations = {}
        self.moment_video_data = {}
        self.moment_mp4_data = {}
        self.moment_timestamps = {}
        self.observation_data = {}
        self.moment_image_map = {}  # Big
        
        self.video_reference_uuid_to_mp4_video_reference = {}
        self.video_sequences_by_name = {}

        self.moment_localizations = {}
        self.moment_ancillary_data = {}

        self.beholder_url = beholder_url
        self.beholder_api_key = beholder_api_key

        self.n_images = 0
        self.n_localizations = 0

        # Munge query items into corresponding dicts
        seen_associations = set()
        with pg.ProgressDialog('Getting video information...', maximum=len(query_data)) as progress:
            for query_item in (
                dict(zip(query_headers, i)) for i in query_data
            ):  # TODO Make pagination
                for k, v in query_item.items():  # Stringify UUID objects
                    if type(v) == UUID:
                        query_item[k] = str(v)

                # Extract fields
                imaged_moment_uuid = query_item["imaged_moment_uuid"]
                image_reference_uuid = query_item["image_reference_uuid"]
                observation_uuid = query_item["observation_uuid"]
                association_uuid = query_item["association_uuid"]

                image_format = query_item["image_format"]
                image_url = query_item["image_url"]

                concept = query_item["concept"]

                link_name = query_item["link_name"]
                to_concept = query_item["to_concept"]
                link_value = query_item["link_value"]

                # Set up moment data
                if (
                    imaged_moment_uuid not in self.moment_image_data
                    and image_format == IMAGE_TYPE
                ):
                    self.moment_image_data[imaged_moment_uuid] = {
                        "image_reference_uuid": image_reference_uuid,
                        "image_url": image_url,
                    }

                # Tag in ancillary data
                if imaged_moment_uuid not in self.moment_ancillary_data:
                    self.moment_ancillary_data[imaged_moment_uuid] = {
                        k: query_item[k]
                        for k in (  # Ancillary data keys
                            "camera_platform",
                            "dive_number",
                            "depth_meters",
                            "latitude",
                            "longitude",
                            "oxygen_ml_per_l",
                            "pressure_dbar",
                            "salinity",
                            "temperature_celsius",
                            "light_transmission",
                        )
                    }

                # Extract video data
                video_data = {
                    k: query_item[k]
                    for k in (  # Video data keys
                        "index_elapsed_time_millis",
                        "index_timecode",
                        "index_recorded_timestamp",
                        "video_start_timestamp",
                        "video_uri",
                        "video_container",
                        "video_reference_uuid",
                        "video_sequence_name",
                        "video_width",
                        "video_height",
                    )
                }
                
                # Tag in video data
                if video_data.get("video_uri", None) is not None:  # valid video
                    if imaged_moment_uuid not in self.moment_video_data:
                        self.moment_video_data[imaged_moment_uuid] = video_data
                
                # Observation data
                recorded_timestamp = video_data["index_recorded_timestamp"]
                elapsed_time_millis = video_data["index_elapsed_time_millis"]
                timecode = video_data["index_timecode"]
                
                # Video sequence data
                video_sequence_name = video_data["video_sequence_name"]
                
                # Video data
                video_start_timestamp = video_data["video_start_timestamp"]
                
                # Handle string timestamps (convert to datetime)
                # Note: This is only apparently an issue with FreeTDS (what pymssql uses) on Apple Silicon
                if isinstance(recorded_timestamp, str):
                    recorded_timestamp = parse_iso(recorded_timestamp)
                if isinstance(video_start_timestamp, str):
                    video_start_timestamp = parse_iso(video_start_timestamp)
                
                # ------------------
                
                # Skip if the video sequence name is not set
                if video_sequence_name is None:
                    continue
                
                # Get full video sequence data if not already fetched
                if video_sequence_name not in self.video_sequences_by_name:
                    # Try to fetch
                    try:
                        video_sequence_data = operations.get_video_sequence_by_name(
                            video_sequence_name
                        )
                    except Exception as e:
                        LOGGER.error(f"Failed to get video sequence data for {video_sequence_name}: {e}")
                        video_sequence_data = None
                    
                    # Store in dict
                    self.video_sequences_by_name[video_sequence_name] = video_sequence_data
                
                # ------------------

                if imaged_moment_uuid not in self.moment_mp4_data:
                    # Get imaged moment's time index
                    moment_timestamp = get_timestamp(video_start_timestamp, recorded_timestamp, elapsed_time_millis, timecode)
                    self.moment_timestamps[imaged_moment_uuid] = moment_timestamp
                    
                    if moment_timestamp is None:  # No timestamp, can't use
                        continue
                    
                    # Find the corresponding MP4 video reference (in the same video sequence) for this imaged moment, if there is one
                    mp4_video_data = self.find_mp4_video_data(video_sequence_name, moment_timestamp)
                    
                    if mp4_video_data is not None:
                        LOGGER.debug(f"Found MP4 video reference {mp4_video_data['video_reference']['uuid']} for imaged moment {imaged_moment_uuid}")
                    else:
                        LOGGER.warning(f"Could not find MP4 video reference for imaged moment {imaged_moment_uuid}")
                    
                    self.moment_mp4_data[imaged_moment_uuid] = mp4_video_data
                
                # ------------------
                
                # Collect bounding boxes
                if link_name == "bounding box":
                    if association_uuid in seen_associations:
                        continue
                    seen_associations.add(association_uuid)

                    json_loc = link_value
                    localization = VARSLocalization.from_json(json_loc)

                    localization.set_concept(concept, to_concept)

                    localization.imaged_moment_uuid = imaged_moment_uuid
                    localization.observation_uuid = observation_uuid
                    localization.association_uuid = association_uuid

                    if imaged_moment_uuid not in self.moment_localizations:
                        self.moment_localizations[imaged_moment_uuid] = []
                    self.moment_localizations[imaged_moment_uuid].append(localization)
            
                progress += 1

        # Create a worklist (imaged moment UUID -> URL or None)
        worklist = {}
        for imaged_moment_uuid in self.moment_localizations:
            if imaged_moment_uuid in self.moment_image_data:
                worklist[imaged_moment_uuid] = self.moment_image_data[
                    imaged_moment_uuid
                ]["image_url"]
            else:
                worklist[imaged_moment_uuid] = None

        # Download the images
        with pg.ProgressDialog(
            "Downloading images...", 0, len(set(worklist.keys()))
        ) as dlg:
            for imaged_moment_uuid, url in worklist.items():
                dlg += 1
                if dlg.wasCanceled():
                    LOGGER.info("Image loading cancelled by user")
                    break

                if (
                    imaged_moment_uuid in self.moment_image_map
                ):  # Already downloaded, skip
                    LOGGER.debug("Skipping, already downloaded image for moment: {}".format(imaged_moment_uuid))
                    continue

                # Scale factors. Needed if the image is not the same size as the annotation's source image
                scale_x = 1.0
                scale_y = 1.0

                if url is None:  # No image reference, need to use beholder
                    video_data = self.moment_video_data[imaged_moment_uuid]
                    
                    source_width = video_data["video_width"]
                    source_height = video_data["video_height"]
                    
                    # Find the video URI of the MP4 video
                    original_video_reference_uuid = video_data["video_reference_uuid"]
                    if original_video_reference_uuid is None:
                        LOGGER.error(f"Imaged moment {imaged_moment_uuid} has no video reference, skipping")
                        continue
                    
                    mp4_video_data = self.moment_mp4_data.get(imaged_moment_uuid, None)
                    if mp4_video_data is None:
                        LOGGER.warning(f"Imaged moment {imaged_moment_uuid} has no MP4 video reference, skipping")
                        continue
                    
                    # Get the MP4 video data
                    mp4_video_reference_uri = mp4_video_data["video_reference"]["uri"]
                    mp4_width = mp4_video_data["video_reference"]["width"]
                    mp4_height = mp4_video_data["video_reference"]["height"]
                    mp4_video_start_timestamp = parse_iso(mp4_video_data["video"]["start_timestamp"])  # datetime
                    moment_timestamp = self.moment_timestamps[imaged_moment_uuid]
                    
                    # Compute the offset in milliseconds
                    elapsed_time_millis = round((moment_timestamp - mp4_video_start_timestamp).total_seconds() * 1000)

                    # Get the capture from beholder
                    LOGGER.debug(f"Getting capture from beholder for moment: {imaged_moment_uuid} ({mp4_video_reference_uri} @ {elapsed_time_millis} ms)")
                    try:
                        res = requests.post(
                            beholder_url + "/capture",
                            json={
                                "videoUrl": mp4_video_reference_uri,
                                "elapsedTimeMillis": int(elapsed_time_millis),
                            },
                            headers={"X-Api-Key": self.beholder_api_key},
                        )
                        res.raise_for_status()
                    except Exception as e:
                        LOGGER.error(
                            "Error getting capture from beholder for moment: {}, skipping".format(
                                imaged_moment_uuid
                            )
                        )
                        continue
                    
                    scale_x = source_width / mp4_width
                    scale_y = source_height / mp4_height

                else:  # download the image from its URL
                    res = requests.get(url)
                    if res.status_code != 200:
                        LOGGER.warn(
                            "Unable to fetch image (status {}) at url: {}, skipping".format(
                                res.status_code, url
                            )
                        )
                        continue

                img_raw = res.content
                img_arr = np.fromstring(img_raw, np.uint8)
                img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                
                # Rescale the image if needed
                if scale_x != 1.0 or scale_y != 1.0:
                    LOGGER.debug(f"Resizing image for moment {imaged_moment_uuid} by {scale_x}x{scale_y}")
                    
                    if scale_x == 0 or scale_y == 0:
                        LOGGER.warn(f"Invalid scale factors for moment {imaged_moment_uuid}: {scale_x}x{scale_y}, skipping")
                        continue
                    
                    img = cv2.resize(
                        img,
                        None,
                        fx=scale_x,
                        fy=scale_y,
                        interpolation=cv2.INTER_CUBIC,  # see OpenCV docs: https://docs.opencv.org/4.8.0/da/d54/group__imgproc__transform.html#ga47a974309e9102f5f08231edc7e7529d
                    )

                self.moment_image_map[imaged_moment_uuid] = img
                self.n_images += 1

        # Create the rect widgets
        for imaged_moment_uuid, localizations in self.moment_localizations.items():
            # If image not there for one reason or another, skip
            if (
                imaged_moment_uuid not in self.moment_image_map
                or self.moment_image_map[imaged_moment_uuid] is None
            ):
                LOGGER.debug(f"Skipping moment {imaged_moment_uuid} due to missing image")
                continue

            image = self.moment_image_map[imaged_moment_uuid]
            ancillary_data = (
                self.moment_ancillary_data.get(imaged_moment_uuid, None) or {}
            )
            video_data = self.moment_video_data.get(imaged_moment_uuid, None) or {}
            min_x = 0
            min_y = 0
            max_x = image.shape[1]
            max_y = image.shape[0]

            # Filter out invalid boxes
            valid_localizations = []
            for loc in localizations:
                if not (loc.valid_box and loc.in_bounds(min_x, min_y, max_x, max_y)):
                    LOGGER.debug(f"Skipping localization {loc.association_uuid} due to invalid box or out of bounds")
                    continue
                valid_localizations.append(loc)
            localizations = valid_localizations

            # Create the widgets
            for localization in localizations:
                other_locs = list(localizations)
                other_locs.remove(localization)
                rw = RectWidget(
                    other_locs + [localization],
                    image,
                    ancillary_data,
                    video_data,
                    len(other_locs),
                )
                rw.text_label = localization.text_label
                rw.update_zoom(zoom)
                rw.clicked.connect(rect_clicked_slot)
                self._rect_widgets.append(rw)

                localization.rect = rw  # Back reference

                self.n_localizations += 1

    def find_mp4_video_data(self, video_sequence_name: str, timestamp: datetime) -> Optional[dict]:
        """
        Find a video with an MP4 video reference for the given video sequence name and timestamp.
        
        Args:
            video_sequence_name: The video sequence name
            timestamp: The timestamp
        
        Returns:
            The matching video data dict, or None if no match found
        """
        if video_sequence_name not in self.video_sequences_by_name:  # Video sequence not encountered
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
            video_start_timestamp = parse_iso(video_start_timestamp)
            video_end_timestamp = video_start_timestamp + timedelta(milliseconds=video_duration_millis)
            
            if not (video_start_timestamp <= timestamp <= video_end_timestamp):  # Timestamp not in range
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

    def render_mosaic(self):
        """
        Load images + annotations and populate the mosaic
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
            rect.text_label = rect.localization.text_label
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
        self.render_mosaic()
    
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
        self.render_mosaic()
    
    def eventFilter(self, source, event):
        if source is self._graphics_view and event.type() == QtCore.QEvent.Type.Resize:
            self.render_mosaic()  # Re-render when the view is resized
        return super().eventFilter(source, event)
