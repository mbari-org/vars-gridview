# -*- coding: utf-8 -*-
"""
image_mosaic.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more infomation.

"""

from uuid import UUID

import cv2
import numpy as np
import pyqtgraph as pg
import requests
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from libs.annotation import VARSLocalization
from libs.logger import LOG
from libs.widgets import RectWidget

IMAGE_TYPE = 'image/png'


class ImageMosaic:
    def __init__(self, graphicsView, query_data, query_headers, rect_slot, verifier, zoom=1.0):
        self.graphicsView = graphicsView
        self.layout = None
        self.scene = None
        self.panel = None
        self.thumbs = []
        self.roi_map = {}
        self.sort_key = 'Image'
        self.hide_labeled = True
        self.hide_discarded = True
        self.hide_to_review = True
        self.layouts = []
        # The scene and view for image mosaic
        self.scene = QtGui.QGraphicsScene()
        self.graphicsView.setScene(self.scene)
        self.panel = QtGui.QGraphicsWidget()
        self.scene.addItem(self.panel)

        self.verifier = verifier

        self.moment_image_data = {}
        self.moment_localizations = {}
        self.observation_data = {}
        self.iruuid_image_map = {}  # Big

        self.iruuid_localizations = {}

        self.n_images = 0
        self.n_localizations = 0

        # Munge query items into corresponding dicts
        seen_associations = set()
        for query_item in (dict(zip(query_headers, i)) for i in query_data):  # TODO Make pagination
            for k, v in query_item.items():  # Stringify UUID objects
                if type(v) == UUID:
                    query_item[k] = str(v)

            # Set up moment data
            imaged_moment_uuid = query_item['imaged_moment_uuid']
            if imaged_moment_uuid not in self.moment_image_data:
                self.moment_image_data[imaged_moment_uuid] = {}

            image_reference_uuid = query_item['image_reference_uuid']
            if image_reference_uuid not in self.moment_image_data[imaged_moment_uuid]:
                self.moment_image_data[imaged_moment_uuid][image_reference_uuid] = {
                    'format': query_item['image_format'],
                    'image_url': query_item['image_url']
                }

            # Collect bounding boxes
            link_name = query_item['link_name']
            if link_name == 'bounding box':
                association_uuid = query_item['association_uuid']
                if association_uuid in seen_associations:
                    continue
                seen_associations.add(association_uuid)

                json_loc = query_item['link_value']
                localization = VARSLocalization.from_json(json_loc)

                if localization.image_reference_uuid is None:
                    LOG.warn('Association {} has no image_reference_uuid tag, skipping'.format(association_uuid))
                    continue
                json_iruuid = localization.image_reference_uuid

                localization.set_concept(query_item['concept'], query_item['to_concept'])
                localization.observation_uuid = query_item['observation_uuid']
                localization.association_uuid = query_item['association_uuid']

                if json_iruuid not in self.iruuid_localizations:
                    self.iruuid_localizations[json_iruuid] = []
                self.iruuid_localizations[json_iruuid].append(localization)

        # Make a flat map of image_reference_uuid -> image info
        flat_map = {}
        for image_data_dict in self.moment_image_data.values():
            flat_map.update(image_data_dict)

        # Set up aliases map (image_reference_uuid -> image_reference_uuid of IMAGE_TYPE)
        alias = {}
        for imaged_moment_uuid, image_data_dict in self.moment_image_data.items():
            chosen_uuid = None
            for image_reference_uuid, image_data in image_data_dict.items():
                if image_data['format'] == IMAGE_TYPE:
                    chosen_uuid = image_reference_uuid
                    break
            else:
                LOG.warn('Missing {} image for imaged moment: '.format(IMAGE_TYPE) + imaged_moment_uuid)
                continue

            for image_reference_uuid in image_data_dict:
                alias[image_reference_uuid] = chosen_uuid

        # Create a worklist
        worklist = {
            uuid: flat_map[alias[uuid]]['image_url']
            for uuid in self.iruuid_localizations
            if uuid in alias
        }

        # Download the images
        already_downloaded = set()
        with pg.ProgressDialog("Downloading images...", 0, len(set(worklist.values()))) as dlg:
            for image_reference_uuid, url in worklist.items():
                if dlg.wasCanceled():
                    raise Exception("Image loading cancelled by user")

                if url in already_downloaded:
                    continue

                res = requests.get(url)
                if res.status_code != 200:
                    LOG.warn('Unable to fetch image (status {}) at url: {}, skipping'.format(res.status_code, url))
                    continue
                already_downloaded.add(url)

                img_raw = res.content
                img_arr = np.fromstring(img_raw, np.uint8)
                img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

                self.iruuid_image_map[image_reference_uuid] = img
                self.n_images += 1

                dlg += 1

        with pg.ProgressDialog('Creating widgets...', 0, self.n_localizations) as roi_pd:
            for image_reference_uuid, localizations in self.iruuid_localizations.items():
                # If image not there for one reason or another, skip
                if image_reference_uuid not in self.iruuid_image_map or self.iruuid_image_map[image_reference_uuid] is None:
                    continue

                image = self.iruuid_image_map[image_reference_uuid]
                min_x = 0
                min_y = 0
                max_x = image.shape[1]
                max_y = image.shape[0]

                # Filter out invalid boxes
                localizations = [loc for loc in localizations
                                 if loc.valid_box and loc.in_bounds(min_x, min_y, max_x, max_y)]

                # create the widgets
                for idx, localization in enumerate(localizations):
                    other_locs = list(localizations)
                    other_locs.remove(localization)
                    rw = RectWidget(other_locs + [localization], image, len(other_locs))
                    rw.text_label = localization.text_label
                    rw.update_zoom(zoom)
                    rw.rectHover.connect(rect_slot)
                    self.thumbs.append(rw)

                    localization.rect = rw  # Back reference

                    self.n_localizations += 1

                    # update progress bar
                    roi_pd += 1

    def render_mosaic(self, sort_key='Image'):
        add_thumbs = False
        if self.layout is None:
            add_thumbs = True
            self.panel.setLayout(None)
            self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)
            self.layout.setContentsMargins(50, 100, 50, 50)
            self.panel.setLayout(self.layout)

        if sort_key != self.sort_key:
            add_thumbs = True

        if add_thumbs:
            for ind, l in enumerate(self.layouts):
                while l.count():
                    l.removeItem(l.itemAt(0))
                self.layout.removeItem(l)

        self.layouts = []

        if sort_key == 'Image':
            self.thumbs.sort(key=lambda x: x.localization.image_reference_uuid, reverse=False)
        if sort_key == 'Class Name':
            self.thumbs.sort(key=lambda x: x.text_label.lower().strip(' '), reverse=False)
        if sort_key == 'Timestamp':
            self.thumbs.sort(key=lambda x: x.annotation_path, reverse=False)
        if sort_key == 'Height':
            self.thumbs.sort(key=lambda x: x.rectHeight, reverse=True)

        self.sort_key = sort_key

        columns = 8
        rows = int(len(self.thumbs) / columns)

        i = 0
        while i < len(self.thumbs):
            row_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Horizontal)
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
        for rect in self.thumbs:
            if rect.isSelected:
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

        self.render_mosaic(sort_key=self.sort_key)

    def delete_selected(self):
        selected = [rect for rect in self.thumbs if rect.isSelected]

        for rect in selected:
            rect.localization.delete()
            rect.deleted = True

        self.clear_selected()

        self.render_mosaic(sort_key=self.sort_key)

    def clear_selected(self):
        for ind in range(0, len(self.thumbs)):
            self.thumbs[ind].isSelected = False
            self.thumbs[ind].update()
        # self.render_mosaic(sort_key=self.sort_key)

    def update_zoom(self, zoom):
        for rect in self.thumbs:
            rect.update_zoom(zoom)
