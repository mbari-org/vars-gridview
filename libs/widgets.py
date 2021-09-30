# -*- coding: utf-8 -*-
"""
widgets.py -- A set of classes to extend widgets from pyqtgraph and pyqt for annotation purposes
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

from typing import List

import cv2
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from config import settings
from libs.annotation import VARSLocalization


class RectWidget(QtWidgets.QGraphicsWidget):
    rectHover = QtCore.Signal(object)

    def __init__(self,
                 localizations: List[VARSLocalization],
                 image: np.ndarray, index: int,
                 parent=None, text_label='rect widget'):
        QtWidgets.QGraphicsWidget.__init__(self, parent)

        self.localizations = localizations  # Dumb, but it works
        self.image = image
        self.index = index

        self.labelheight = 30
        self.bordersize = 4
        self.picdims = [240, 240]
        self.zoom = .5
        self.text_label = text_label
        self._boundingRect = QtCore.QRect()
        self.setAcceptHoverEvents(True)
        self.bgColor = QtCore.Qt.darkGray
        self.hoverColor = QtCore.Qt.lightGray
        self.isLastSelected = False
        self.isSelected = False
        self.forReview = False
        self.toDiscard = False

        self.roi = None
        self.pic = None
        self.update_roi_pic()

        self.deleted = False

    def update_roi_pic(self):
        self.roi = self.localization.get_roi(self.image)
        self.pic = self.getpic(self.roi)
        self.update()

    @property
    def isAnnotated(self) -> bool:
        return self.localizations[self.index].verified

    @property
    def localization(self):
        return self.localizations[self.index]

    @property
    def image_width(self):
        return self.image.shape[1]

    @property
    def image_height(self):
        return self.image.shape[0]

    def toqimage(self, img):
        height, width, bytesPerComponent = img.shape
        bytesPerLine = bytesPerComponent * width
        cv2.cvtColor(img, cv2.COLOR_BGR2RGB, img)
        qimg = QtGui.QImage(img.copy(), width, height, bytesPerLine, QtGui.QImage.Format_RGB888)

        return qimg

    def update_zoom(self, zoom):
        self.zoom = zoom
        self.boundingRect()
        self.updateGeometry()

    def getFullImage(self):
        return np.rot90(self.image, 3, (0, 1))

    def boundingRect(self):
        # scale and zoom
        width = self.zoom * (self.picdims[0] + self.bordersize * 2)
        height = self.zoom * (self.picdims[1] + self.labelheight + self.bordersize * 2)

        thumb_widget_rect = QtCore.QRectF(0.0, 0.0, width, height)
        self._boundingRect = thumb_widget_rect

        return thumb_widget_rect

    def sizeHint(self, which, constraint=QtCore.QSizeF()):
        return self._boundingRect.size()

    def getpic(self, roi):
        height, width, channels = roi.shape
        if height >= width:
            scale = self.picdims[0] / height
        else:
            scale = self.picdims[0] / width
        new_width = int(width * scale) - 2 * self.bordersize
        new_height = int(height * scale) - 2 * self.bordersize
        roi = cv2.resize(roi, (new_width, new_height))

        # center roi on dims
        w_pad = int((self.picdims[0] - new_width) / 2)
        h_pad = int((self.picdims[1] - new_height) / 2)

        roi = cv2.copyMakeBorder(
            roi,
            h_pad,
            h_pad,
            w_pad,
            w_pad,
            cv2.BORDER_CONSTANT,
            value=settings.BG_COLOR
        )

        qimg = self.toqimage(roi)
        orpixmap = QtGui.QPixmap.fromImage(qimg)
        return orpixmap

    def paint(self, painter, option, widget):
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setBrush(QtCore.Qt.black)
        painter.setPen(pen)

        # very simple selection and annotation logic
        if self.isSelected:
            fill_color = QtCore.Qt.green
        elif self.isAnnotated:
            fill_color = QtCore.Qt.yellow
        else:
            fill_color = QtCore.Qt.darkGray

        # fill behind image
        if self.isLastSelected:
            painter.fillRect(QtCore.QRect(0,
                                          0,
                                          self.zoom * (self.pic.rect().width() + 2 * self.bordersize),
                                          self.zoom * (
                                                  self.pic.rect().height() + self.labelheight + 2 * self.bordersize)),
                             QtGui.QColor(61, 174, 233, 255))

        # Fill label
        painter.fillRect(QtCore.QRect(self.zoom * self.bordersize,
                                      self.zoom * (self.bordersize + self.pic.rect().height()),
                                      self.zoom * self.pic.rect().width(),
                                      self.zoom * self.labelheight),
                         fill_color)

        # Draw image
        painter.drawPixmap(QtCore.QRect(self.zoom * self.bordersize,
                                        self.zoom * self.bordersize,
                                        self.zoom * self.pic.rect().width(),
                                        self.zoom * self.pic.rect().height()),
                           self.pic,
                           self.pic.rect())

        # Draw text
        text_rect = QtCore.QRect(0,
                                 self.zoom * (self.pic.rect().y() + self.pic.rect().height()),
                                 self.zoom * self.pic.rect().width(),
                                 self.zoom * self.labelheight)

        painter.drawText(text_rect, QtCore.Qt.AlignCenter, self.text_label)

        if self.toDiscard:
            painter.fillRect(QtCore.QRect(self.zoom * self.bordersize,
                                          self.zoom * (self.bordersize),
                                          self.zoom * self.pic.rect().width(),
                                          self.zoom * self.labelheight),
                             QtCore.Qt.gray)
            text_rect = QtCore.QRect(0,
                                     self.zoom * (self.pic.rect().y()),
                                     self.zoom * self.pic.rect().width(),
                                     self.zoom * self.labelheight)
            painter.setPen(QtCore.Qt.red)
            painter.drawText(text_rect, QtCore.Qt.AlignCenter, "To Remove")

        if self.forReview:
            painter.fillRect(QtCore.QRect(self.zoom * self.bordersize,
                                          self.zoom * (self.bordersize),
                                          self.zoom * self.pic.rect().width(),
                                          self.zoom * self.labelheight),
                             QtCore.Qt.gray)
            text_rect = QtCore.QRect(0,
                                     self.zoom * (self.pic.rect().y()),
                                     self.zoom * self.pic.rect().width(),
                                     self.zoom * self.labelheight)
            painter.setPen(QtCore.Qt.blue)
            painter.drawText(text_rect, QtCore.Qt.AlignCenter, "For Review")

    def mousePressEvent(self, event):
        self.isSelected = not self.isSelected
        self.update()
        self.rectHover.emit(self)

    def mouseReleaseEvent(self, event):
        pass

    def hoverEnterEvent(self, event):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.ControlModifier:
            self.isSelected = not self.isSelected
            self.update()
            self.rectHover.emit(self)
