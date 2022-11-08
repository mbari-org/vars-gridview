# -*- coding: utf-8 -*-
"""
image_mosaic.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more infomation.

"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import cv2
import numpy as np
import pyqtgraph as pg
import requests
from PyQt6 import QtWidgets, QtCore

from vars_gridview.lib.annotation import VARSLocalization
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.sort_methods import SortMethod
from vars_gridview.lib.widgets import RectWidget

IMAGE_TYPE = 'image/png'


class ImageMosaic:
    def __init__(
        self, graphicsView, query_data, query_headers, rect_slot, verifier, beholder_url, beholder_api_key, zoom=1.0
    ):
        self.graphicsView = graphicsView
        self.layout = None
        self.scene = None
        self.panel = None
        self.thumbs = []
        self.roi_map = {}
        self.hide_labeled = True
        self.hide_discarded = True
        self.hide_to_review = True
        self.layouts = []
        # The scene and view for image mosaic
        self.scene = QtWidgets.QGraphicsScene()
        self.graphicsView.setScene(self.scene)
        self.panel = QtWidgets.QGraphicsWidget()
        self.scene.addItem(self.panel)

        self.verifier = verifier

        self.moment_image_data = {}
        self.moment_localizations = {}
        self.moment_video_data = {}
        self.moment_mp4_data = {}
        self.observation_data = {}
        self.moment_image_map = {}  # Big

        self.moment_localizations = {}
        self.moment_ancillary_data = {}
        
        self.beholder_url = beholder_url
        self.beholder_api_key = beholder_api_key

        self.n_images = 0
        self.n_localizations = 0

        # Munge query items into corresponding dicts
        seen_associations = set()
        for query_item in (
            dict(zip(query_headers, i)) for i in query_data
        ):  # TODO Make pagination
            for k, v in query_item.items():  # Stringify UUID objects
                if type(v) == UUID:
                    query_item[k] = str(v)

            # Extract fields
            imaged_moment_uuid = query_item['imaged_moment_uuid']
            image_reference_uuid = query_item['image_reference_uuid']
            observation_uuid = query_item['observation_uuid']
            association_uuid = query_item['association_uuid']
            
            image_format = query_item['image_format']
            image_url = query_item['image_url']
            
            concept = query_item['concept']
            
            link_name = query_item['link_name']
            to_concept = query_item['to_concept']
            link_value = query_item['link_value']
            
            # Set up moment data
            if imaged_moment_uuid not in self.moment_image_data and image_format == IMAGE_TYPE:
                self.moment_image_data[imaged_moment_uuid] = {
                    'image_reference_uuid': image_reference_uuid,
                    'image_url': image_url,
                }

            # Tag in ancillary data
            if imaged_moment_uuid not in self.moment_ancillary_data:
                self.moment_ancillary_data[imaged_moment_uuid] = {
                    k: query_item[k]
                    for k in (  # Ancillary data keys
                        'camera_platform',
                        'dive_number',
                        'depth_meters',
                        'latitude',
                        'longitude',
                        'oxygen_ml_per_l',
                        'pressure_dbar',
                        'salinity',
                        'temperature_celsius',
                        'light_transmission',
                    )
                }
            
            # Extract video data
            video_data = {
                k: query_item[k]
                for k in (  # Video data keys
                    'index_elapsed_time_millis',
                    'index_timecode',
                    'index_recorded_timestamp',
                    'video_start_timestamp',
                    'video_uri',
                    'video_container'
                )
            }
            
            # Tag in video data where appropriate
            if video_data['video_uri'] is not None:  # valid video
                if imaged_moment_uuid not in self.moment_video_data:
                    self.moment_video_data[imaged_moment_uuid] = video_data
                    
                # For beholder
                if imaged_moment_uuid not in self.moment_mp4_data and video_data['video_container'] == 'video/mp4':
                    self.moment_mp4_data[imaged_moment_uuid] = video_data

            # Collect bounding boxes
            if link_name == 'bounding box':
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

        # Create a worklist (imaged moment UUID -> URL or None)
        worklist = {}
        for imaged_moment_uuid in self.moment_localizations:
            if imaged_moment_uuid in self.moment_image_data:
                worklist[imaged_moment_uuid] = self.moment_image_data[imaged_moment_uuid]['image_url']
            else:
                worklist[imaged_moment_uuid] = None

        # Download the images
        with pg.ProgressDialog(
            "Downloading images...", 0, len(set(worklist.keys()))
        ) as dlg:
            for imaged_moment_uuid, url in worklist.items():
                if dlg.wasCanceled():
                    raise Exception("Image loading cancelled by user")
                
                if imaged_moment_uuid in self.moment_image_map:  # already downloaded, skip
                    continue

                if url is None:  # no image reference, need to use beholder
                    elapsed_time_millis = None
                    mp4_data = self.moment_mp4_data.get(imaged_moment_uuid, None)
                    if mp4_data is None:
                        LOGGER.warn('No web video available for capture for moment: {}, skipping'.format(imaged_moment_uuid))
                        continue
                    
                    video_start_datetime = mp4_data['video_start_timestamp']
        
                    elapsed_time_millis = mp4_data.get('index_elapsed_time_millis', None)
                    timecode = mp4_data.get('index_timecode', None)
                    recorded_timestamp = mp4_data.get('index_recorded_timestamp', None)
                    
                    # Get annotation video time index
                    annotation_datetime = None
                    if recorded_timestamp is not None:
                        annotation_datetime = recorded_timestamp
                    elif elapsed_time_millis is not None:
                        annotation_datetime = video_start_datetime + datetime.timedelta(milliseconds=int(elapsed_time_millis))
                    elif timecode is not None:
                        hours, minutes, seconds, frames = map(int, timecode.split(':'))
                        annotation_datetime = video_start_datetime + datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
                    else:
                        LOGGER.error('No time index available for moment: {}, skipping'.format(imaged_moment_uuid))
                        continue
                    
                    # Compute the elapsed time in milliseconds
                    elapsed_time_millis = round((annotation_datetime - video_start_datetime).total_seconds() * 1000)
                    res = requests.post(
                        beholder_url + '/capture', 
                        json={
                            'videoUrl': mp4_data['video_uri'],
                            'elapsedTimeMillis': int(elapsed_time_millis),
                        },
                        headers={
                            'X-Api-Key': self.beholder_api_key
                        }
                    )  # TODO REMOVE
                    if res.status_code != 200:
                        LOGGER.error('Error getting capture from beholder for moment: {}, skipping'.format(imaged_moment_uuid))
                        continue
                    
                else:  # download the image from its URL
                    res = requests.get(url)
                    if res.status_code != 200:
                        LOGGER.warn(
                            'Unable to fetch image (status {}) at url: {}, skipping'.format(
                                res.status_code, url
                            )
                        )
                        continue

                img_raw = res.content
                img_arr = np.fromstring(img_raw, np.uint8)
                img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

                self.moment_image_map[imaged_moment_uuid] = img
                self.n_images += 1

                dlg += 1

        with pg.ProgressDialog(
            'Creating widgets...', 0, self.n_localizations
        ) as roi_pd:
            for (
                imaged_moment_uuid,
                localizations,
            ) in self.moment_localizations.items():
                # If image not there for one reason or another, skip
                if (
                    imaged_moment_uuid not in self.moment_image_map
                    or self.moment_image_map[imaged_moment_uuid] is None
                ):
                    continue

                image = self.moment_image_map[imaged_moment_uuid]
                ancillary_data = (
                    self.moment_ancillary_data.get(imaged_moment_uuid, None) or {}
                )
                video_data = (
                    self.moment_video_data.get(imaged_moment_uuid, None) or {}
                )
                min_x = 0
                min_y = 0
                max_x = image.shape[1]
                max_y = image.shape[0]

                # Filter out invalid boxes
                localizations = [
                    loc
                    for loc in localizations
                    if loc.valid_box and loc.in_bounds(min_x, min_y, max_x, max_y)
                ]

                # create the widgets
                for idx, localization in enumerate(localizations):
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
                    rw.rectHover.connect(rect_slot)
                    self.thumbs.append(rw)

                    localization.rect = rw  # Back reference

                    self.n_localizations += 1

                    # update progress bar
                    roi_pd += 1

    def render_mosaic(self, sort_method: Optional[SortMethod] = None):
        """
        Load images + annotations and populate the mosaic
        """
        add_thumbs = False
        if self.layout is None:
            add_thumbs = True
            self.panel.setLayout(None)
            self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Orientation.Vertical)
            self.layout.setContentsMargins(50, 100, 50, 50)
            self.panel.setLayout(self.layout)

        if sort_method is not None:
            # Sort the thumbnails
            sort_method.sort(self.thumbs)
            add_thumbs = True

        if add_thumbs:
            # Clear the layouts
            for l in self.layouts:
                while l.count():
                    l.removeItem(l.itemAt(0))
                self.layout.removeItem(l)
            self.layouts = []

        columns = 8
        rows = int(len(self.thumbs) / columns)

        i = 0
        while i < len(self.thumbs):
            row_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Orientation.Horizontal)
            j = 0
            while j < columns and i < len(self.thumbs):
                hide_thumb = False
                if self.hide_to_review:
                    hide_thumb = hide_thumb | self.thumbs[i].forReview
                if self.hide_discarded:
                    hide_thumb = hide_thumb | self.thumbs[i].toDiscard
                if self.hide_labeled:
                    hide_thumb = hide_thumb | self.thumbs[i].isAnnotated

                hide_thumb |= self.thumbs[i].deleted

                if hide_thumb:
                    self.thumbs[i].hide()
                else:
                    self.thumbs[i].show()

                if add_thumbs:
                    row_layout.addItem(self.thumbs[i])
                    self.thumbs[i].show()
                    j += 1

                i += 1
            if add_thumbs:
                self.layout.addItem(row_layout)
                self.layouts.append(row_layout)

    def apply_label(self, concept, part):
        """
        Apply a label to the selected thumbnails.
        """
        for rect in self.get_selected():
            # Handle empty concept/part
            if concept.strip() == '':  # No concept specified? Verify as-is
                concept = rect.localization.concept
            if part.strip() == '':  # No part specified? ditto
                part = rect.localization.part

            # Set the new concept and immediately push to VARS
            rect.localization.set_verified_concept(concept, part, self.verifier)
            rect.localization.push_changes(self.verifier)

            # Update the widget's text label and deselect it
            rect.text_label = rect.localization.text_label
            rect.isSelected = False

            # Propagate visual changes
            rect.update()

        self.render_mosaic()

    def get_selected(self) -> List[RectWidget]:
        """
        Get selected thumbs (list of RectWidget).
        """
        return [rect for rect in self.thumbs if rect.isSelected]

    def delete_selected(self):
        """
        Delete all selected thumbs and re-render.
        """
        for rect in self.get_selected():
            rect.localization.delete()
            rect.deleted = True

        self.clear_selected()

        self.render_mosaic()

    def clear_selected(self):
        """
        Clear the selection of thumbs.
        """
        for ind in range(0, len(self.thumbs)):
            self.thumbs[ind].isSelected = False
            self.thumbs[ind].update()
        # self.render_mosaic()

    def update_zoom(self, zoom):
        for rect in self.thumbs:
            rect.update_zoom(zoom)
