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
import time
from collections.abc import Callable

import cv2
import httpx
import numpy as np
import requests
from beholder_client import BeholderClient

from vars_gridview.lib.annotation.association import BoundingBoxAssociation
from vars_gridview.lib.m3.clients import SkimmerClient

_log = logging.getLogger(__name__)

# Skimmer and Beholder both return 503 + Retry-After when their respective
# work pools are shedding load rather than queuing indefinitely; a couple of
# short retries lets a tile recover instead of going permanently blank for
# what's usually a brief dip.
_BUSY_MAX_RETRIES = 2
_BUSY_DEFAULT_RETRY_SECONDS = 1.0
_BUSY_MAX_RETRY_SECONDS = 5.0

# Full-image fetches back a single interactive "click to view/edit" request
# rather than one of many tiles competing for the same backend capacity, so
# it's worth retrying much harder than the bulk path -- bounded only by an
# overall deadline (a backend that's actually down, not just busy) and by the
# caller telling us the request is stale (see fetch_full_image's should_cancel).
_INTERACTIVE_MAX_WAIT_SECONDS = 120.0


class _FetchCancelled(Exception):
    """Raised internally when ``should_cancel`` reports the request is stale."""


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
        elapsed_time_millis: int | None = None,
    ) -> np.ndarray | None:
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
                raw_bytes = self._capture_raw_with_busy_retry(
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
                response = self._crop_with_busy_retry(image_url, x, y, xf, yf)
                response.raise_for_status()
                arr = np.frombuffer(response.content, np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except (requests.HTTPError, httpx.HTTPStatusError) as exc:
            _log.error(f"HTTP error fetching ROI for {assoc.uuid}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            _log.error(f"Unexpected error fetching ROI for {assoc.uuid}: {exc}")
            return None

    def _crop_with_busy_retry(
        self, url: str, left: int, top: int, right: int, bottom: int
    ) -> requests.Response:
        """Call :meth:`SkimmerClient.crop`, retrying a 503 (crop pool busy).

        Honors the response's ``Retry-After`` header, capped to a sane
        range. Any other status or error is returned/raised immediately for
        the caller's own handling -- only 503 is retried here.
        """
        response = self._skimmer.crop(url, left, top, right, bottom)
        for _ in range(_BUSY_MAX_RETRIES):
            if response.status_code != 503:
                return response
            wait_seconds = self._retry_after_seconds(response.headers)
            _log.warning(
                f"Skimmer busy (503) for {url}; retrying in {wait_seconds:.1f}s"
            )
            time.sleep(wait_seconds)
            response = self._skimmer.crop(url, left, top, right, bottom)
        return response

    def _capture_raw_with_busy_retry(self, url: str, elapsed_time_millis: int) -> bytes:
        """Call :meth:`BeholderClient.capture_raw`, retrying a 503 (capture pool busy).

        ``beholder_client`` raises ``httpx.HTTPStatusError`` (with the
        response, including headers, attached) rather than returning an
        error response like :class:`SkimmerClient.crop` does. Only 503 is
        retried here; any other status or error propagates immediately.
        """
        for _ in range(_BUSY_MAX_RETRIES):
            try:
                return self._beholder.capture_raw(url, elapsed_time_millis)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 503:
                    raise
                wait_seconds = self._retry_after_seconds(exc.response.headers)
                _log.warning(
                    f"Beholder busy (503) for {url}; retrying in {wait_seconds:.1f}s"
                )
                time.sleep(wait_seconds)
        return self._beholder.capture_raw(url, elapsed_time_millis)

    @staticmethod
    def _retry_after_seconds(headers) -> float:
        header = headers.get("Retry-After")
        if header is None:
            return _BUSY_DEFAULT_RETRY_SECONDS
        try:
            seconds = float(header)
        except ValueError:
            return _BUSY_DEFAULT_RETRY_SECONDS
        return max(0.0, min(seconds, _BUSY_MAX_RETRY_SECONDS))

    def fetch_full_image(
        self,
        image_url: str,
        elapsed_time_millis: int | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> np.ndarray | None:
        """Fetch an entire frame image without cropping.

        Unlike :meth:`fetch_roi`'s bulk tile path, this backs a single
        interactive request with nothing else competing for the same backend
        capacity, so a 503 (pool busy) is retried until *should_cancel* says
        to give up (e.g. the user selected a different tile before this one
        resolved) or ``_INTERACTIVE_MAX_WAIT_SECONDS`` elapses as a safety
        net against a backend that's actually down rather than just busy.

        Args:
            image_url: URL of the source frame (or video reference URL).
            elapsed_time_millis: Optional frame offset for video references.
            should_cancel: Optional callable checked between retries; once it
                returns ``True`` the fetch is abandoned and ``None`` is
                returned.

        Returns:
            BGR uint8 NumPy array ``(H, W, 3)``, or ``None`` on error/cancellation.
        """
        try:
            if elapsed_time_millis is not None:
                raw_bytes = self._capture_raw_with_unbounded_retry(
                    image_url, elapsed_time_millis, should_cancel
                )
            else:
                response = self._get_with_unbounded_retry(image_url, should_cancel)
                response.raise_for_status()
                raw_bytes = response.content
            arr = np.frombuffer(raw_bytes, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except _FetchCancelled:
            return None
        except Exception as exc:  # noqa: BLE001
            _log.error(f"Error fetching full image {image_url}: {exc}")
            return None

    def _capture_raw_with_unbounded_retry(
        self,
        url: str,
        elapsed_time_millis: int,
        should_cancel: Callable[[], bool] | None,
    ) -> bytes:
        """Like :meth:`_capture_raw_with_busy_retry`, but keeps retrying a 503
        past the bulk-load retry budget -- see :meth:`fetch_full_image`."""
        deadline = time.monotonic() + _INTERACTIVE_MAX_WAIT_SECONDS
        while True:
            try:
                return self._beholder.capture_raw(url, elapsed_time_millis)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 503:
                    raise
                if should_cancel is not None and should_cancel():
                    raise _FetchCancelled from None
                if time.monotonic() >= deadline:
                    raise
                wait_seconds = self._retry_after_seconds(exc.response.headers)
                _log.warning(
                    f"Beholder busy (503) for {url}; retrying in {wait_seconds:.1f}s"
                )
                time.sleep(wait_seconds)

    def _get_with_unbounded_retry(
        self, url: str, should_cancel: Callable[[], bool] | None
    ) -> requests.Response:
        """Like :meth:`_crop_with_busy_retry`, but for the interactive
        full-image path -- see :meth:`_capture_raw_with_unbounded_retry`."""
        deadline = time.monotonic() + _INTERACTIVE_MAX_WAIT_SECONDS
        while True:
            response = requests.get(url, timeout=30)
            if response.status_code != 503:
                return response
            if should_cancel is not None and should_cancel():
                raise _FetchCancelled
            if time.monotonic() >= deadline:
                return response
            wait_seconds = self._retry_after_seconds(response.headers)
            _log.warning(
                f"Source busy (503) for {url}; retrying in {wait_seconds:.1f}s"
            )
            time.sleep(wait_seconds)


__all__ = ["RoiService"]
