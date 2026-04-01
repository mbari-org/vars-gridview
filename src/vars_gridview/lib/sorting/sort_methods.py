"""Grid sort methods for the image mosaic.

Each :class:`SortMethod` defines a ``key`` static method that derives a
comparable value from a :class:`~vars_gridview.ui.mosaic.rect_widget.RectWidget`.  The
base :meth:`SortMethod.sort` in-place-sorts a list using that key.

:class:`SortMethodGroup` composes multiple methods into a stable multi-key sort.

The :func:`association_data_sort` decorator factory creates sort classes that
look up a value from a
:attr:`~vars_gridview.lib.annotation.association.BoundingBoxAssociation.data` dict.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

import cv2
import numpy as np

from vars_gridview.ui.mosaic.rect_widget import RectWidget


class SortMethod(ABC):
    """Abstract base for all named sort strategies.

    Subclasses must define :attr:`NAME` (a human-readable label shown in the
    sort dialog) and implement :meth:`key`.
    """

    NAME: str | None = None

    @staticmethod
    @abstractmethod
    def key(rect: RectWidget) -> Any:
        """Derive a comparable sort key from *rect*.

        Args:
            rect: The tile widget to inspect.

        Returns:
            A value that supports total ordering (``<``, ``>``, etc.).
        """
        raise NotImplementedError

    @classmethod
    def sort(cls, rect_widgets: list[RectWidget], **kwargs: Any) -> None:
        """In-place sort *rect_widgets* by :meth:`key`.

        Args:
            rect_widgets: List to sort in place.
            **kwargs: Forwarded to :func:`list.sort` (e.g. ``reverse=True``).
        """
        rect_widgets.sort(key=cls.key, **kwargs)


class SortMethodGroup:
    """Composite sort that applies multiple methods in order (multi-key sort).

    Args:
        *methods: Two or more :class:`SortMethod` subclasses to apply in
            left-to-right priority order.
    """

    def __init__(self, *methods: type[SortMethod]) -> None:
        self.methods = methods

    def key(self, rect: RectWidget) -> tuple[Any, ...]:
        """Return a tuple of per-method keys for *rect*.

        Args:
            rect: The tile widget to inspect.

        Returns:
            Tuple of keys; lexicographic comparison gives the composite order.
        """
        return tuple(method.key(rect) for method in self.methods)

    def sort(self, rect_widgets: list[RectWidget], **kwargs: Any) -> None:
        """In-place sort *rect_widgets* using the composite key.

        Args:
            rect_widgets: List to sort in place.
            **kwargs: Forwarded to :func:`list.sort`.
        """
        rect_widgets.sort(key=self.key, **kwargs)


class NoopSort(SortMethod):
    """No-op sort — preserves the original insertion order."""

    NAME = "No-op"

    @staticmethod
    def key(rect: RectWidget) -> None:  # noqa: ARG004
        return None


class RecordedTimestampSort(SortMethod):
    """Sort by the annotation's recorded timestamp (ascending)."""

    NAME = "Recorded timestamp"

    @staticmethod
    def key(rect: RectWidget) -> datetime:
        return rect.annotation_datetime() or datetime.min.replace(tzinfo=UTC)


class AssociationUUIDSort(SortMethod):
    """Sort by the bounding-box association UUID."""

    NAME = "Association UUID"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.association_uuid or ""


class ObservationUUIDSort(SortMethod):
    """Sort by the parent observation UUID."""

    NAME = "Observation UUID"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.observation_uuid or ""


class ImageReferenceUUIDSort(SortMethod):
    """Sort by the image reference UUID."""

    NAME = "Image reference UUID"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.association.image_reference_uuid or ""


class LabelSort(SortMethod):
    """Sort alphabetically by concept label."""

    NAME = "Label"

    @staticmethod
    def key(rect: RectWidget) -> str:
        return rect.text_label


class WidthSort(SortMethod):
    """Sort by bounding-box width in pixels."""

    NAME = "Width"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return rect.association.width


class HeightSort(SortMethod):
    """Sort by bounding-box height in pixels."""

    NAME = "Height"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return rect.association.height


class AreaSort(SortMethod):
    """Sort by bounding-box area (width × height) in pixels²."""

    NAME = "Area"

    @staticmethod
    def key(rect: RectWidget) -> int:
        return WidthSort.key(rect) * HeightSort.key(rect)


class AspectRatioSort(SortMethod):
    """Sort by aspect ratio (width / height).

    Values > 1 are wide/horizontal; values < 1 are tall/narrow.
    Returns ``0.0`` when height is zero to avoid division by zero.
    """

    NAME = "Aspect ratio"

    @staticmethod
    def key(rect: RectWidget) -> float:
        height = HeightSort.key(rect)
        width = WidthSort.key(rect)
        return width / height if height > 0 else 0.0


class IntensityMeanSort(SortMethod):
    """Sort by mean pixel intensity across all channels."""

    NAME = "Intensity mean"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return float(np.mean(rect.roi))


class IntensityVarianceSort(SortMethod):
    """Sort by pixel intensity variance across all channels."""

    NAME = "Intensity variance"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return float(np.var(rect.roi))


class HueMeanSort(SortMethod):
    """Sort by mean hue value (HSV colour space)."""

    NAME = "Hue mean"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_hsv = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2HSV)
        return float(np.mean(roi_hsv[:, :, 0].ravel()))


class HueVarianceSort(SortMethod):
    """Sort by hue variance (HSV colour space)."""

    NAME = "Hue variance"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_hsv = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2HSV)
        return float(np.var(roi_hsv[:, :, 0].ravel()))


class HueMeanCenterRegion(SortMethod):
    """Sort by mean hue of the centre third of the bounding box."""

    NAME = "Hue mean (center region)"

    @staticmethod
    def key(rect: RectWidget) -> float:
        h, w = rect.association.height, rect.association.width
        sub_roi = rect.roi[h // 3 : h * 2 // 3, w // 3 : w * 2 // 3]
        roi_hsv = cv2.cvtColor(sub_roi, cv2.COLOR_BGR2HSV)
        return float(np.mean(roi_hsv[:, :, 0].ravel()))


class DepthSort(SortMethod):
    """Sort by ancillary depth in metres (ascending, shallow first)."""

    NAME = "Depth"

    @staticmethod
    def key(rect: RectWidget) -> float:
        return float(rect.ancillary_data.get("depth_meters") or 0.0)


class LaplacianVarianceSort(SortMethod):
    """Sort by sharpness estimated with the Laplacian operator variance."""

    NAME = "Sharpness - Laplacian"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(roi_gray, cv2.CV_64F).var())


class LaplacianOfGaussianSort(SortMethod):
    """Sort by sharpness estimated with Laplacian-of-Gaussian (LoG)."""

    NAME = "Sharpness - Laplacian of Gaussian"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(roi_gray, (5, 5), 0)
        return float(cv2.Laplacian(blurred, cv2.CV_64F).var())


class SobelSort(SortMethod):
    """Sort by sharpness estimated with the Sobel gradient operator."""

    NAME = "Sharpness - Sobel"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(roi_gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(roi_gray, cv2.CV_64F, 0, 1, ksize=3)
        return float((gx**2 + gy**2).var())


class CannySort(SortMethod):
    """Sort by edge density using the Canny edge detector."""

    NAME = "Sharpness - Canny"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        return float(cv2.Canny(roi_gray, 100, 200).var())


class FrequencyDomainSort(SortMethod):
    """Sort by frequency-domain energy (2-D FFT magnitude variance)."""

    NAME = "Sharpness - Frequency Domain"

    @staticmethod
    def key(rect: RectWidget) -> float:
        roi_gray = cv2.cvtColor(rect.roi, cv2.COLOR_BGR2GRAY)
        f = np.fft.fft2(roi_gray)
        fshift = np.fft.fftshift(f)
        # Add epsilon to avoid log(0)
        magnitude = 20 * np.log(np.abs(fshift) + 1e-10)
        return float(magnitude.var())


_SortMethodT = TypeVar("_SortMethodT", bound=type[SortMethod])


def association_data_sort(
    data_key: str, default: Any
) -> Callable[[_SortMethodT], _SortMethodT]:
    """Decorator factory for sort classes that read a value from association data.

    The decorated class's ``NAME`` is preserved; its ``key`` is replaced by a
    function that does ``rect.association.data.get(data_key, default)``.

    Args:
        data_key: Key to look up in
            :attr:`~vars_gridview.lib.annotation.association.BoundingBoxAssociation.data`.
        default: Fallback value used when *data_key* is absent.

    Returns:
        A class decorator that replaces the ``key`` static method.
    """

    def decorator(cls: _SortMethodT) -> _SortMethodT:
        class _AssocDataSort(SortMethod):
            NAME = cls.NAME  # type: ignore[assignment]

            @staticmethod
            def key(rect: RectWidget) -> Any:
                return rect.association.data.get(data_key, default)

        _AssocDataSort.__name__ = cls.__name__
        _AssocDataSort.__qualname__ = cls.__qualname__
        return _AssocDataSort  # type: ignore[return-value]

    return decorator


@association_data_sort("verifier", "")
class VerifierSort(SortMethod):  # type: ignore[misc]
    """Sort by the verifier field in the association data."""

    NAME = "Verifier"


@association_data_sort("confidence", 0.0)
class ConfidenceSort(SortMethod):  # type: ignore[misc]
    """Sort by the confidence score in the association data."""

    NAME = "Confidence"


__all__ = [
    "SortMethod",
    "SortMethodGroup",
    "NoopSort",
    "RecordedTimestampSort",
    "AssociationUUIDSort",
    "ObservationUUIDSort",
    "ImageReferenceUUIDSort",
    "LabelSort",
    "WidthSort",
    "HeightSort",
    "AreaSort",
    "AspectRatioSort",
    "IntensityMeanSort",
    "IntensityVarianceSort",
    "HueMeanSort",
    "HueVarianceSort",
    "HueMeanCenterRegion",
    "DepthSort",
    "LaplacianVarianceSort",
    "LaplacianOfGaussianSort",
    "SobelSort",
    "CannySort",
    "FrequencyDomainSort",
    "VerifierSort",
    "ConfidenceSort",
    "association_data_sort",
]
