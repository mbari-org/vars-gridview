from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List, Tuple

import cv2
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


class SortMethodGroup:
    """
    Composite method for sorting rect widgets by multiple sort methods. Methods are applied in the order they are specified.
    """

    def __init__(self, *methods: SortMethod):
        self.methods = methods

    def key(self, rect: RectWidget) -> Tuple[Any]:
        return tuple(method.key(rect) for method in self.methods)

    def sort(self, rect_widgets: List[RectWidget], **kwargs):
        rect_widgets.sort(key=self.key, **kwargs)


class NoopSort(SortMethod):
    """
    No-op sort method. Keeps the order of the rect widgets as-is.
    """

    NAME = "No-op"

    @staticmethod
    def key(rect: RectWidget) -> None:
        return None


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


class IntensityMeanSort(SortMethod):
    NAME = "Intensity mean"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return np.mean(rect.roi, axis=(0, 1, 2))


class IntensityVarianceSort(SortMethod):
    NAME = "Inteinsity variance"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return np.var(rect.roi, axis=(0, 1, 2))


class HueMeanSort(SortMethod):
    NAME = "Hue mean"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_hsv = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2HSV)
        hue = roi_hsv[:, :, 0]
        return np.mean(hue.ravel())


class HueVarianceSort(SortMethod):
    NAME = "Hue variance"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_hsv = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2HSV)
        hue = roi_hsv[:, :, 0]
        return np.var(hue.ravel())


class HueMeanCenterRegion(SortMethod):
    NAME = "Hue mean (center region)"

    @staticmethod
    def key(rect: RectWidget) -> float:
        sub_roi = rect.roi[
            rect.localization.height // 3 : rect.localization.height * 2 // 3,
            rect.localization.width // 3 : rect.localization.width * 2 // 3,
        ]
        
        roi_hsv = cv2.cvtColor(sub_roi, cv2.COLOR_BGR2HSV)
        hue = roi_hsv[:, :, 0]
        return np.mean(hue.ravel())


class DepthSort(SortMethod):
    NAME = "Depth"

    @staticmethod
    def key(rect: RectWidget) -> float:
        depth = rect.ancillary_data.get("depth_meters", 0.0)

        if depth is None:
            depth = 0.0

        return depth


class LaplacianVarianceSort(SortMethod):
    NAME = "Sharpness"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        return lap_var


def localization_meta_sort(key: str, default: Any) -> SortMethod:
    """
    Decorator factory for creating a sort method that sorts by a localization meta key.
    
    Args:
        key: The localization meta key to sort by.
        default: The default value to use if the key is not present.
    """
    def decorator(cls):
        class LocalizationMetaSort(SortMethod):
            NAME = cls.NAME

            @staticmethod
            def key(rect: RectWidget) -> Any:
                return rect.localization.meta.get(key, default)

        return LocalizationMetaSort
    
    return decorator


@localization_meta_sort("verifier", "")
class VerifierSort(SortMethod):
    NAME = "Verifier"


@localization_meta_sort("confidence", 0.0)
class ConfidenceSort(SortMethod):
    NAME = "Confidence"
