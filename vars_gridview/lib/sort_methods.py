from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List

import numpy as np

from vars_gridview.lib.widgets import RectWidget


class SortMethod(ABC):
    """
    Abstract class for named sorting methods of RectWidgets.
    """

    NAME = None

    @staticmethod
    @abstractmethod
    def key(rect: RectWidget) -> Any:
        """
        Returns the key used for sorting.
        """
        raise NotImplementedError

    @classmethod
    def sort(cls, rect_widgets: List[RectWidget], **kwargs):
        """
        Sort a list of RectWidgets.
        """
        rect_widgets.sort(key=cls.key, **kwargs)


class RecordedTimestampSort(SortMethod):
    NAME = "Recorded timestamp"
    
    @staticmethod
    def key(rect: RectWidget) -> datetime:
        return rect.annotation_datetime() or datetime.min


class AssociationUUIDSort(SortMethod):
    NAME = "Association UUID"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.association_uuid or ""


class ObservationUUIDSort(SortMethod):
    NAME = "Observation UUID"
    
    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.observation_uuid or ""


class ImageReferenceUUIDSort(SortMethod):
    NAME = "Image reference UUID"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.localization.image_reference_uuid or ""


class LabelSort(SortMethod):
    NAME = "Label"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.text_label


class WidthSort(SortMethod):
    NAME = "Width"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return rect.localization.width


class HeightSort(SortMethod):
    NAME = "Height"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return rect.localization.height


class AreaSort(SortMethod):
    NAME = "Area"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return WidthSort.key(rect) * HeightSort.key(rect)


class MeanIntensitySort(SortMethod):
    NAME = "Mean intensity"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return np.mean(rect.roi, axis=(0, 1, 2))


class MeanHueSort(SortMethod):
    NAME = "Mean hue"

    @staticmethod
    def key(rect: RectWidget) -> float:
        # RGB -> Hue from https://stackoverflow.com/a/23094494
        means = np.mean(rect.roi, axis=(0, 1))
        means = means / 255
        r, g, b = means
        min_idx, min_val = min(enumerate(means), key=lambda x: x[1])
        max_val = max(means)

        if min_idx == 0:
            return (g - b) / (max_val - min_val)
        elif min_idx == 1:
            return 2 + (b - r) / (max_val - min_val)
        else:
            return 4 + (r - g) / (max_val - min_val)


class RegionMeanHueSort(SortMethod):
    NAME = "Region mean hue (center 1/3)"

    @staticmethod
    def key(rect: RectWidget) -> float:
        sub_roi = rect.roi[
            rect.localization.height // 3 : rect.localization.height * 2 // 3,
            rect.localization.width // 3 : rect.localization.width * 2 // 3,
        ]

        # RGB -> Hue from https://stackoverflow.com/a/23094494
        means = np.mean(sub_roi, axis=(0, 1))
        means = means / 255
        r, g, b = means
        min_idx, min_val = min(enumerate(means), key=lambda x: x[1])
        max_val = max(means)

        if min_idx == 0:
            return (g - b) / (max_val - min_val)
        elif min_idx == 1:
            return 2 + (b - r) / (max_val - min_val)
        else:
            return 4 + (r - g) / (max_val - min_val)


class DepthSort(SortMethod):
    NAME = "Depth"

    @staticmethod
    def key(rect: RectWidget) -> float:
        depth = rect.ancillary_data.get("depth_meters", 0.0)

        if depth is None:
            depth = 0.0

        return depth
