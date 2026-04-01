"""Coordinate opening ROI videos via VLC/browser or Sharktopoda."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from time import sleep
from typing import TYPE_CHECKING
from uuid import uuid4

from PyQt6 import QtCore, QtWidgets
from sharktopoda_client.dto import Localization

from vars_gridview.lib.config.constants import SHARKTOPODA_APP_NAME
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.lib.vision.image_utils import color_for_concept

if TYPE_CHECKING:
    from sharktopoda_client.client import SharktopodaClient
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class VideoNavigationCoordinator:
    """Encapsulate video launch and Sharktopoda localization overlay logic."""

    SHARKTOPODA_ASPECT_RATIO_TOLERANCE = 0.01
    SHARKTOPODA_SHOW_DELAY_SECONDS = 0.5
    SHARKTOPODA_LOCALIZATION_CHUNK_SIZE = 20
    SHARKTOPODA_LOCALIZATION_DURATION_MILLIS = 1000
    BROWSER_SEEK_EPSILON_SECONDS = 1e-3

    def open_video(
        self,
        *,
        parent: QtWidgets.QWidget,
        selected_rect: RectWidget | None,
        all_rect_widgets: list[RectWidget],
        sharktopoda_connected: bool,
        sharktopoda_client: SharktopodaClient | None,
    ) -> None:
        """Open video for ``selected_rect`` in VLC/browser or Sharktopoda."""
        if not selected_rect:
            QtWidgets.QMessageBox.warning(parent, "No ROI Selected", "No ROI selected.")
            return

        rect = selected_rect

        if rect.video_url is None or rect.elapsed_time_millis is None:
            QtWidgets.QMessageBox.warning(
                parent,
                "No Video Data",
                "The selected ROI does not have the required video data.",
            )
            return

        if not sharktopoda_connected:
            self._open_via_vlc_or_browser(rect)
            return

        if sharktopoda_client is None:
            QtWidgets.QMessageBox.warning(
                parent,
                "Sharktopoda Unavailable",
                "Sharktopoda is marked connected, but no client is available.",
            )
            return

        self._open_via_sharktopoda_async(
            parent,
            rect,
            all_rect_widgets,
            sharktopoda_client,
        )

    def _open_via_vlc_or_browser(self, rect: RectWidget) -> None:
        if rect.video_url is None or rect.elapsed_time_millis is None:
            LOGGER.warning("Missing video URL or timestamp; cannot open video")
            return
        video_url = rect.video_url
        elapsed_time_millis = rect.elapsed_time_millis
        elapsed_time_seconds = elapsed_time_millis / 1000.0

        vlc_opened = False
        vlc_commands = []

        if sys.platform == "darwin":
            vlc_commands = [
                "/Applications/VLC.app/Contents/MacOS/VLC",
                "vlc",
            ]
        elif sys.platform == "win32":
            vlc_commands = [
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                "vlc",
            ]
        else:
            vlc_commands = ["vlc"]

        for vlc_cmd in vlc_commands:
            try:
                # Remove Qt plugin vars to avoid conflicts with external VLC process.
                env = os.environ.copy()
                env.pop("QT_PLUGIN_PATH", None)
                env.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

                subprocess.Popen(
                    [
                        vlc_cmd,
                        video_url,
                        f"--start-time={elapsed_time_seconds}",
                        "--start-paused",
                    ],
                    env=env,
                )
                vlc_opened = True
                LOGGER.info(f"Opened video in VLC: {video_url}")
                break
            except (FileNotFoundError, OSError):
                continue

        if not vlc_opened:
            url = video_url + "#t={},{}".format(
                elapsed_time_seconds - self.BROWSER_SEEK_EPSILON_SECONDS,
                elapsed_time_seconds,
            )
            webbrowser.open(url)
            LOGGER.info(f"Opened video in web browser: {url}")

    def _open_via_sharktopoda_async(
        self,
        parent: QtWidgets.QWidget,
        rect: RectWidget,
        all_rect_widgets: list[RectWidget],
        sharktopoda_client: SharktopodaClient,
    ) -> None:
        if rect.video_url is None or rect.elapsed_time_millis is None:
            LOGGER.warning("Missing video URL or timestamp; cannot open in Sharktopoda")
            return
        video_url = rect.video_url
        elapsed_time_millis = rect.elapsed_time_millis
        video_reference_uuid = rect.video_data["video_reference_uuid"]

        if (
            abs(rect.scale_x / rect.scale_y - 1)
            > self.SHARKTOPODA_ASPECT_RATIO_TOLERANCE
        ):
            QtWidgets.QMessageBox.warning(
                parent,
                "Different MP4 Aspect Ratio",
                "MP4 video has different aspect ratio than ROI source image. The bounding box may not be displayed correctly.",
            )

        localizations = []
        for rect_q in all_rect_widgets:
            if rect_q.video_url != rect.video_url:
                continue

            localization = Localization(
                uuid=uuid4(),
                concept=rect_q.association.concept,
                elapsed_time_millis=int(rect_q.elapsed_time_millis or 0),
                x=int(round(rect_q.scale_x * rect_q.association.x)),
                y=int(round(rect_q.scale_y * rect_q.association.y)),
                width=int(round(rect_q.scale_x * rect_q.association.width)),
                height=int(round(rect_q.scale_y * rect_q.association.height)),
                duration_millis=self.SHARKTOPODA_LOCALIZATION_DURATION_MILLIS,
                color=color_for_concept(rect_q.association.concept).name(),
            )
            localizations.append(localization)

        def show_localizations() -> None:
            worker = Worker(
                self._publish_sharktopoda_localizations,
                sharktopoda_client,
                video_reference_uuid,
                elapsed_time_millis,
                localizations,
            )
            worker.signals.error.connect(
                lambda err: LOGGER.error(f"Failed to publish localizations: {err[1]}")
            )
            pool = QtCore.QThreadPool.globalInstance()
            if pool is None:
                LOGGER.error(
                    "Global Qt thread pool unavailable; cannot publish localizations"
                )
                return
            pool.start(worker)

        sharktopoda_client.open(
            video_reference_uuid, video_url, callback=show_localizations
        )

    def _publish_sharktopoda_localizations(
        self,
        sharktopoda_client: SharktopodaClient,
        video_reference_uuid,
        elapsed_time_millis: int,
        localizations: list[Localization],
    ) -> None:
        """Publish localization overlays to Sharktopoda off the UI thread."""
        sleep(self.SHARKTOPODA_SHOW_DELAY_SECONDS)
        sharktopoda_client.seek_elapsed_time(
            video_reference_uuid,
            elapsed_time_millis,
        )
        sharktopoda_client.clear_localizations(video_reference_uuid)

        chunk_size = self.SHARKTOPODA_LOCALIZATION_CHUNK_SIZE
        for i in range(0, len(localizations), chunk_size):
            chunk = localizations[i : i + chunk_size]
            sharktopoda_client.add_localizations(video_reference_uuid, chunk)

        sharktopoda_client.show(video_reference_uuid)

        if sys.platform == "darwin":
            try:
                os.system(f"open -a {SHARKTOPODA_APP_NAME}")
            except Exception as e:
                LOGGER.warning(f"Could not open Sharktopoda: {e}")
