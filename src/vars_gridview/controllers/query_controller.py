"""Query controller — runs VARS queries and manages paging.

:class:`QueryController` owns query lifecycle: it wraps the blocking
``query_count`` / ``query_download`` calls in a :class:`~vars_gridview.lib.runtime.runnables.Worker`
(thread-pool) and emits typed Qt signals so the UI layer never blocks.

Typical usage::

    ctrl = QueryController(parent=window)
    ctrl.results_ready.connect(mosaic.populate)
    ctrl.query_failed.connect(status_bar.show_error)
    ctrl.execute(constraints, limit=100, offset=0)
"""

from __future__ import annotations

import logging
import threading
from typing import Sequence

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from vars_gridview.lib.m3.clients import AnnosaurusClient
from vars_gridview.lib.m3.query import (
    QueryConstraint,
    QueryRequest,
    merge_constraints,
)
from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.lib.common.tsv import parse_tsv

_LOG = logging.getLogger(__name__)


class QueryController(QObject):
    """Manages VARS database queries and result paging.

    All network I/O is performed off the Qt main thread via the global
    :class:`~PyQt6.QtCore.QThreadPool`.

    Signals:
        query_started: Emitted just before I/O begins.
        query_stage_started: Emitted with the stage key ("count", "download",
            or "parse") just before that stage's work begins.
        results_ready: Emitted on success.  Arguments are ``(headers, rows,
            page_number, total_pages, total_rows)``.
        query_failed: Emitted on any error with a human-readable message.
        query_cancelled: Emitted when a cancelled query stops before finishing.
    """

    query_started = pyqtSignal()
    query_stage_started = pyqtSignal(str)  # stage key
    results_ready = pyqtSignal(
        list, list, int, int, int
    )  # headers, rows, page, total_pages, total_rows
    query_failed = pyqtSignal(str)
    query_cancelled = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._last_request: QueryRequest | None = None
        self._total_rows: int = 0
        self._request_generation: int = 0
        self._annosaurus_client: AnnosaurusClient | None = None
        self._cancel_event: threading.Event = threading.Event()

    @property
    def cancel_event(self) -> threading.Event:
        """The cancellation token for the most recently dispatched query."""
        return self._cancel_event

    def cancel(self) -> None:
        """Request cancellation of the in-flight query pipeline, if any."""
        self._cancel_event.set()

    def set_annosaurus_client(self, client: AnnosaurusClient) -> None:
        """Attach the authenticated Annosaurus client for future queries."""
        self._annosaurus_client = client

    # ── Queries ────────────────────────────────────────────────────────────────

    @property
    def has_results(self) -> bool:
        """``True`` when a successful query has been loaded."""
        return self._last_request is not None and self._total_rows > 0

    @property
    def current_page(self) -> int:
        """1-based current page number, or 0 when nothing is loaded."""
        if self._last_request is None:
            return 0
        return 1 + self._last_request.offset // self._last_request.limit

    @property
    def total_pages(self) -> int:
        """Total number of pages for the current query, or 0."""
        if self._last_request is None:
            return 0
        limit = self._last_request.limit
        return self._total_rows // limit + (1 if self._total_rows % limit else 0)

    # ── Commands ───────────────────────────────────────────────────────────────

    def execute(
        self,
        constraints: Sequence[QueryConstraint],
        limit: int,
        offset: int = 0,
    ) -> None:
        """Run a new query asynchronously.

        Builds a :class:`~vars_gridview.lib.m3.query.QueryRequest` from
        *constraints* and dispatches the download to a worker thread.  Emits
        :attr:`query_started` immediately, then either :attr:`results_ready`
        or :attr:`query_failed` once the worker returns.

        Args:
            constraints: Sequence of :class:`~vars_gridview.lib.m3.query.QueryConstraint`
                objects that express the filter.
            limit: Maximum number of rows per page.
            offset: Row offset for the first page (default ``0``).
        """
        merged = merge_constraints(list(constraints))
        request = QueryRequest(
            select=[
                "video_reference_uuid",
                "imaged_moment_uuid",
                "observation_uuid",
                "association_uuid",
                "image_reference_uuid",
                "video_sequence_name",
                "chief_scientist",
                "camera_platform",
                "dive_number",
                "video_start_timestamp",
                "video_container",
                "video_uri",
                "video_width",
                "video_height",
                "index_elapsed_time_millis",
                "index_recorded_timestamp",
                "index_timecode",
                "image_url",
                "image_format",
                "observer",
                "concept",
                "link_name",
                "to_concept",
                "link_value",
                "depth_meters",
                "latitude",
                "longitude",
                "oxygen_ml_per_l",
                "pressure_dbar",
                "salinity",
                "temperature_celsius",
                "light_transmission",
                "observation_group",
            ],
            where=[QueryConstraint("link_name", equals="bounding box"), *merged],
            order_by=["index_recorded_timestamp"],
            limit=limit,
            offset=offset,
        )
        self._dispatch(request)

    def next_page(self) -> None:
        """Fetch the next page of the last query.

        No-op if already on the last page or nothing is loaded.
        """
        if self._last_request is None:
            return
        limit = self._last_request.limit
        if self._last_request.offset >= self._total_rows - limit:
            return
        request = QueryRequest(
            select=self._last_request.select,
            where=self._last_request.where,
            order_by=self._last_request.order_by,
            limit=limit,
            offset=self._last_request.offset + limit,
        )
        self._dispatch(request)

    def previous_page(self) -> None:
        """Fetch the previous page of the last query.

        No-op if already on the first page or nothing is loaded.
        """
        if self._last_request is None or self._last_request.offset == 0:
            return
        limit = self._last_request.limit
        new_offset = max(0, self._last_request.offset - limit)
        request = QueryRequest(
            select=self._last_request.select,
            where=self._last_request.where,
            order_by=self._last_request.order_by,
            limit=limit,
            offset=new_offset,
        )
        self._dispatch(request)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _dispatch(self, request: QueryRequest) -> None:
        """Dispatch *request* to a thread-pool worker.

        Args:
            request: The query to run.
        """
        if self._annosaurus_client is None:
            self.query_failed.emit("Query service is unavailable: no Annosaurus client")
            return

        self._request_generation += 1
        generation = self._request_generation
        self._cancel_event = threading.Event()

        self.query_started.emit()
        self.query_stage_started.emit("count")

        worker = Worker(self._fetch_count, self._annosaurus_client, request, generation)
        worker.signals.result.connect(self._on_count_result)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _fetch_count(
        client: AnnosaurusClient,
        request: QueryRequest,
        generation: int,
    ) -> tuple[QueryRequest, int, int]:
        """Count matching rows in a worker thread.

        Args:
            request: Query parameters.
            generation: Request generation token.

        Returns:
            A tuple ``(request, total_rows, generation)``.

        Raises:
            Exception: Any network error.
        """
        response = client.query_count(request)
        response.raise_for_status()
        total = response.json()["count"]
        return request, total, generation

    @staticmethod
    def _fetch_download(
        client: AnnosaurusClient,
        request: QueryRequest,
        total_rows: int,
        generation: int,
    ) -> tuple[QueryRequest, int, int, str]:
        """Download raw TSV payload in a worker thread.

        Args:
            request: Query parameters.
            total_rows: Precomputed total row count.
            generation: Request generation token.

        Returns:
            A tuple ``(request, total_rows, generation, raw_tsv)``.

        Raises:
            Exception: Any network error.
        """
        response = client.query_download(request)
        response.raise_for_status()
        raw = response.text
        return request, total_rows, generation, raw

    @staticmethod
    def _parse_download(
        request: QueryRequest,
        total_rows: int,
        generation: int,
        raw_tsv: str,
    ) -> tuple[QueryRequest, int, int, list, list]:
        """Parse TSV payload off the UI thread.

        Args:
            request: Query parameters.
            total_rows: Precomputed total row count.
            generation: Request generation token.
            raw_tsv: Downloaded TSV text.

        Returns:
            A tuple ``(request, total_rows, generation, headers, rows)``.

        Raises:
            Exception: Any network or parsing error.
        """
        headers, rows = parse_tsv(raw_tsv)
        return request, total_rows, generation, headers, rows

    def _on_count_result(self, payload: tuple) -> None:
        request, total_rows, generation = payload
        if generation != self._request_generation:
            return
        if self._cancel_event.is_set():
            self.query_cancelled.emit()
            return

        self.query_stage_started.emit("download")
        if self._annosaurus_client is None:
            self.query_failed.emit("Query service is unavailable: no Annosaurus client")
            return
        worker = Worker(
            self._fetch_download,
            self._annosaurus_client,
            request,
            total_rows,
            generation,
        )
        worker.signals.result.connect(self._on_download_result)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    def _on_download_result(self, payload: tuple) -> None:
        request, total_rows, generation, raw_tsv = payload
        if generation != self._request_generation:
            return
        if self._cancel_event.is_set():
            self.query_cancelled.emit()
            return

        self.query_stage_started.emit("parse")
        worker = Worker(
            self._parse_download,
            request,
            total_rows,
            generation,
            raw_tsv,
        )
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    def _on_result(self, payload: tuple) -> None:
        """Handle successful query completion.

        Args:
            payload: ``(request, total_rows, generation, headers, rows)``.
        """
        request, total, generation, headers, rows = payload
        if generation != self._request_generation:
            return
        if self._cancel_event.is_set():
            self.query_cancelled.emit()
            return

        self._last_request = request
        self._total_rows = total
        page = 1 + request.offset // request.limit
        total_pages = total // request.limit + (1 if total % request.limit else 0)
        _LOG.info("Query complete: %d total rows, page %d/%d", total, page, total_pages)
        self.results_ready.emit(headers, rows, page, total_pages, total)

    def _on_error(self, error: tuple) -> None:
        """Handle a query failure.

        Args:
            error: ``(exc_type, exc_value, traceback)`` from the worker.
        """
        exc_type, exc_value, _tb = error
        msg = f"{exc_type.__name__}: {exc_value}"
        _LOG.error("Query failed: %s", msg)
        self.query_failed.emit(msg)


__all__ = ["QueryController"]
