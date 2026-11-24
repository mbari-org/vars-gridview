"""Running a query whose ``in`` list is too long for one database statement.

Annosaurus binds each listed value as its own SQL parameter, and SQL Server
takes at most 2,100, so a list of tens of thousands of UUIDs has to go to the
server in pieces (see :func:`~vars_gridview.lib.m3.query.split_where`). The
pieces are counted once, when the query is first run, and a
:class:`SplitPlan` records how to page through the combined result:

* Usually the matching rows' keys are fetched once and sorted, so the whole
  result is in one order (time, then UUIDs) and a page is fetched by the
  association UUIDs of its rows.
* When the result is too large to hold every key, the pieces are paged as
  if their results were concatenated, each in time order.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol, TypeVar

from vars_gridview.lib.common.tsv import parse_tsv
from vars_gridview.lib.m3.query import (
    QueryConstraint,
    QueryRequest,
    page_slices,
    split_where,
)

_LOG = logging.getLogger(__name__)

# How many requests for one query are in flight at once.
PARALLEL_REQUESTS = 4

# Above this many rows, keys aren't fetched and the pieces are paged in turn.
# 200,000 keys are about 20 MB of TSV.
MAX_RESOLVED_ROWS = 200_000

# A row of the annotations view is one box on one image: an imaged moment
# with two image references gives each of its boxes two rows.
ASSOCIATION = "association_uuid"
IMAGE_REFERENCE = "image_reference_uuid"
TIMESTAMP = "index_recorded_timestamp"
KEY_COLUMNS = [TIMESTAMP, ASSOCIATION, IMAGE_REFERENCE]

RowKey = tuple[str, str]  # (association UUID, image reference UUID)
T = TypeVar("T")
R = TypeVar("R")


class QueryClient(Protocol):
    def query_count(self, request: QueryRequest): ...
    def query_download(self, request: QueryRequest): ...


@dataclass(frozen=True)
class SplitPlan:
    """How to page through a split query's combined result.

    Attributes:
        where: The query's constraints, as given; a page request with the
            same constraints reuses the plan.
        total: Rows in the combined result.
        others: The constraints other than the split list.
        keys: Every row's key in result order, when resolved.
        pieces: Each piece's constraints and row count, when not resolved.
    """

    where: list[QueryConstraint]
    total: int
    others: list[QueryConstraint]
    keys: list[RowKey] | None = None
    pieces: list[tuple[list[QueryConstraint], int]] | None = None


def _parallel(fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    items = list(items)
    if len(items) <= 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(PARALLEL_REQUESTS) as pool:
        return list(pool.map(fn, items))


def _count(client: QueryClient, request: QueryRequest) -> int:
    response = client.query_count(request)
    response.raise_for_status()
    return response.json()["count"]


def _download(client: QueryClient, request: QueryRequest) -> str:
    response = client.query_download(request)
    response.raise_for_status()
    return response.text


def plan(
    client: QueryClient, request: QueryRequest, max_resolved: int | None = None
) -> SplitPlan | None:
    """Count a query in pieces if it needs splitting.

    Args:
        client: Annosaurus client.
        request: The query; its limit and offset are ignored.
        max_resolved: Most rows to fetch keys for (default
            :data:`MAX_RESOLVED_ROWS`).

    Returns:
        A plan, or ``None`` when the query fits in one statement.

    Raises:
        ValueError: If the query can't be split to fit (see
            :func:`~vars_gridview.lib.m3.query.split_where`).
        Exception: Any network error.
    """
    where = request.where or []
    wheres = split_where(where)
    if len(wheres) == 1:
        return None
    others = [c for c in wheres[0] if any(c is w for w in where)]

    def piece(constraints: list[QueryConstraint], **kw) -> QueryRequest:
        return QueryRequest(
            where=constraints, order_by=request.order_by, offset=0, **kw
        )

    counts = _parallel(
        lambda w: _count(client, piece(w, select=request.select, limit=request.limit)),
        wheres,
    )
    pieces = [(w, n) for w, n in zip(wheres, counts, strict=True) if n]
    total = sum(counts)
    limit = MAX_RESOLVED_ROWS if max_resolved is None else max_resolved
    _LOG.info(
        "Query split into %d pieces for the database's parameter limit; %d rows",
        len(wheres),
        total,
    )
    if total > limit:
        return SplitPlan(where=where, total=total, others=others, pieces=pieces)

    texts = _parallel(
        lambda p: _download(client, piece(p[0], select=KEY_COLUMNS, limit=p[1])),
        pieces,
    )
    rows: list[tuple[str, str, str]] = []
    for text in texts:
        header, body = parse_tsv(text)
        col = [header.index(name) for name in KEY_COLUMNS]
        rows.extend(
            tuple(row[i] for i in col)  # type: ignore[misc]
            for row in body
            if len(row) >= len(header)
        )
    rows.sort()  # time, then association, then image reference
    keys = list(dict.fromkeys((a, i) for _t, a, i in rows))
    return SplitPlan(where=where, total=len(keys), others=others, keys=keys)


def fetch_page(client: QueryClient, request: QueryRequest, split: SplitPlan) -> str:
    """Download one page (``request.offset``/``limit``) of a split query.

    Returns:
        The page as TSV, with the request's columns as its header.
    """
    offset, limit = request.offset or 0, request.limit or 0
    empty = "\t".join(request.select or []) + "\n"

    if split.keys is None:
        assert split.pieces is not None
        requests = [
            QueryRequest(
                select=request.select,
                where=split.pieces[index][0],
                order_by=request.order_by,
                limit=n,
                offset=start,
            )
            for index, start, n in page_slices(
                [n for _w, n in split.pieces], offset, limit
            )
        ]
        texts = _parallel(lambda r: _download(client, r), requests)
        return join_tsv(texts) if texts else empty

    page = split.keys[offset : offset + limit]
    if not page:
        return empty
    associations = list(dict.fromkeys(a for a, _i in page))
    wheres = split_where(
        [*split.others, QueryConstraint(ASSOCIATION, in_=associations)]
    )
    texts = _parallel(
        lambda w: _download(
            client,
            QueryRequest(
                select=request.select,
                where=w,
                order_by=request.order_by,
                limit=split.total,  # can't match more rows than the whole result
                offset=0,
            ),
        ),
        wheres,
    )
    return _in_key_order(texts, page, empty)


def _in_key_order(texts: list[str], page: list[RowKey], empty: str) -> str:
    """Join the pieces' rows in *page* order, dropping rows not on the page."""
    header = texts[0].split("\n", 1)[0]
    names = header.split("\t")
    a, i = names.index(ASSOCIATION), names.index(IMAGE_REFERENCE)
    by_key: dict[RowKey, str] = {}
    for text in texts:
        for line in text.split("\n")[1:]:
            fields = line.split("\t")
            if len(fields) == len(names):
                by_key[(fields[a], fields[i])] = line
    lines = [by_key[key] for key in page if key in by_key]  # gone: deleted since
    return "\n".join([header, *lines]) + "\n" if lines else empty


def join_tsv(texts: list[str]) -> str:
    """Join TSV documents that share a header, keeping the first header."""
    lines = texts[0].rstrip("\n").split("\n")[:1]
    for text in texts:
        lines.extend(line for line in text.rstrip("\n").split("\n")[1:] if line)
    return "\n".join(lines) + "\n"


__all__ = [
    "MAX_RESOLVED_ROWS",
    "SplitPlan",
    "fetch_page",
    "join_tsv",
    "plan",
]
