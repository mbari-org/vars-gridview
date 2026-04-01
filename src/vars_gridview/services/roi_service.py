"""ROI (region-of-interest) image fetch service.

:class:`RoiService` provides a single method, :meth:`fetch_roi`, that
retrieves a cropped bounding-box image for a given
:class:`~vars_gridview.lib.annotation.association.BoundingBoxAssociation`.  All network
calls happen on the calling thread; callers are expected to dispatch via
:class:`~vars_gridview.lib.runtime.runnables.Worker` or a ``QThread`` to keep the GUI
responsive.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np
import requests
from beholder_client import BeholderClient

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.m3.clients import SkimmerClient

_log = logging.getLogger(__name__)


class RoiService:
    """Fetch cropped ROI images for bounding-box associations.

    Supports two back-ends:

    * **Skimmer** — used when the association has a static image URL (the
      common case for frame grabs).
    * **Beholder** — used when the association is located on a video file and
      needs a frame extracted at a specific elapsed time.

    Args:
        skimmer: Configured :class:`~vars_gridview.lib.m3.clients.SkimmerClient`.
        beholder: Configured :class:`~beholder_client.BeholderClient`.
    """

    def __init__(self, skimmer: SkimmerClient, beholder: BeholderClient) -> None:
        self._skimmer = skimmer
        self._beholder = beholder

    def fetch_roi(
        self,
        assoc: BoundingBoxAssociation,
        image_url: str,
        elapsed_time_millis: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Fetch the cropped ROI for *assoc*.

        Args:
            assoc: Association whose bounding box defines the crop region.
            image_url: URL of the source frame image (or video reference URL
                when *elapsed_time_millis* is provided).
            elapsed_time_millis: If not ``None``, use Beholder to capture the
                frame at this offset before cropping.

        Returns:
            BGR uint8 NumPy array ``(H, W, 3)``, or ``None`` on error.
        """
        x, y, xf, yf = assoc.box
        try:
            if elapsed_time_millis is not None:
                raw_bytes: bytes = self._beholder.capture_raw(
                    image_url, elapsed_time_millis
                )
                full_image = cv2.imdecode(
                    np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR
                )
                if full_image is None:
                    _log.warning(f"Could not decode Beholder frame for {image_url}")
                    return None
                return full_image[y:yf, x:xf]
            else:
                response = self._skimmer.crop(image_url, x, y, xf, yf)
                response.raise_for_status()
                arr = np.frombuffer(response.content, np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except requests.HTTPError as exc:
            _log.error(f"HTTP error fetching ROI for {assoc.uuid}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            _log.error(f"Unexpected error fetching ROI for {assoc.uuid}: {exc}")
            return None

    def fetch_full_image(
        self,
        image_url: str,
        elapsed_time_millis: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Fetch an entire frame image without cropping.

        Args:
            image_url: URL of the source frame (or video reference URL).
            elapsed_time_millis: Optional frame offset for video references.

        Returns:
            BGR uint8 NumPy array ``(H, W, 3)``, or ``None`` on error.
        """
        try:
            if elapsed_time_millis is not None:
                raw_bytes = self._beholder.capture_raw(image_url, elapsed_time_millis)
                arr = np.frombuffer(raw_bytes, np.uint8)
            else:
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                arr = np.frombuffer(response.content, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as exc:  # noqa: BLE001
            _log.error(f"Error fetching full image {image_url}: {exc}")
            return None


__all__ = ["RoiService"]
