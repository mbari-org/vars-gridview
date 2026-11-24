"""Queries with tens of thousands of listed values are split to fit the
database's parameter limit, and paged across the pieces as one result."""

from __future__ import annotations

import random
import uuid

import pytest
from PyQt6.QtCore import QThreadPool

from vars_gridview.controllers.query_controller import QueryController
from vars_gridview.lib.m3.query import (
    MAX_QUERY_PARAMETERS,
    QueryConstraint,
    QueryRequest,
    page_slices,
    split_where,
)

SQL_SERVER_LIMIT = 2100


def _params(where: list[QueryConstraint]) -> int:
    n = 0
    for c in where:
        if c.in_ is not None:
            n += len(c.in_)
        elif c.minmax is not None or c.between is not None:
            n += 2
        elif c.isnull is None:
            n += 1
    return n


# ── split_where ───────────────────────────────────────────────────────────────


def test_short_query_isnt_split() -> None:
    where = [
        QueryConstraint("link_name", equals="bounding box"),
        QueryConstraint("concept", in_=["a", "b"]),
    ]
    assert split_where(where) == [where]


def test_long_list_is_split_into_pieces_that_fit() -> None:
    values = [str(uuid.uuid4()) for _ in range(40_000)]
    where = [
        QueryConstraint("link_name", equals="bounding box"),
        QueryConstraint("association_uuid", in_=values),
        QueryConstraint("depth_meters", minmax=[100.0, 500.0]),
    ]
    parts = split_where(where)
    assert len(parts) == 21  # 40,000 / (2,000 - 3)
    seen: list[str] = []
    for part in parts:
        assert _params(part) <= MAX_QUERY_PARAMETERS < SQL_SERVER_LIMIT
        assert part[0] is where[0] and part[2] is where[2]
        seen.extend(part[1].in_)
    assert sorted(seen) == sorted(values)
    assert len(set(seen)) == len(values)


def test_only_the_longest_list_is_split() -> None:
    concepts = [f"c{i}" for i in range(50)]
    uuids = [str(uuid.uuid4()) for _ in range(5_000)]
    parts = split_where(
        [QueryConstraint("concept", in_=concepts), QueryConstraint("x", in_=uuids)]
    )
    assert all(part[0].in_ == concepts for part in parts)


def test_two_long_lists_are_refused() -> None:
    with pytest.raises(ValueError, match="only the longest one can be split"):
        split_where(
            [
                QueryConstraint("concept", in_=[f"c{i}" for i in range(3_000)]),
                QueryConstraint("x", in_=[f"u{i}" for i in range(5_000)]),
            ]
        )


# ── page_slices ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("offset", "limit", "expected"),
    [
        (0, 10, [(0, 0, 5), (1, 0, 5)]),
        (3, 4, [(0, 3, 2), (1, 0, 2)]),
        (5, 5, [(1, 0, 5)]),
        (8, 100, [(1, 3, 4)]),
        (12, 10, []),  # past the end
    ],
)
def test_page_slices(offset, limit, expected) -> None:
    assert page_slices([5, 7, 0], offset, limit) == expected


def test_page_slices_skip_empty_pieces() -> None:
    assert page_slices([2, 0, 3], 0, 10) == [(0, 0, 2), (2, 0, 3)]
    assert page_slices([2, 0, 3], 1, 2) == [(0, 1, 1), (2, 0, 1)]


# ── the controller against a fake Annosaurus ──────────────────────────────────


class _Response:
    def __init__(self, *, json=None, text="") -> None:
        self._json = json
        self.text = text

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._json


class _FakeAnnosaurus:
    """Box rows (one per box per image), refusing what SQL Server would."""

    def __init__(self, uuids: list[str], seed: int = 0) -> None:
        rng = random.Random(seed)
        self.rows = []
        for n, association in enumerate(uuids):
            stamp = f"2020-01-01T{rng.randrange(24):02}:{rng.randrange(60):02}:00Z"
            images = 2 if n % 50 == 0 else 1  # some moments have two images
            for k in range(images):
                self.rows.append(
                    {
                        "association_uuid": association,
                        "image_reference_uuid": f"img-{n}-{k}",
                        "index_recorded_timestamp": stamp,
                        "concept": "Pyrosoma",
                    }
                )
        self.counts = 0
        self.downloads = 0

    def _matching(self, request: QueryRequest) -> list[dict]:
        if _params(request.where) > SQL_SERVER_LIMIT:
            raise RuntimeError("The incoming request has too many parameters.")
        rows = self.rows
        for c in request.where:
            if c.column == "link_name":
                continue
            wanted = set(c.in_) if c.in_ is not None else {c.equals}
            rows = [r for r in rows if r[c.column] in wanted]
        order = request.order_by or []
        return sorted(rows, key=lambda r: tuple(r[col] for col in order))

    def query_count(self, request: QueryRequest) -> _Response:
        self.counts += 1
        return _Response(json={"count": len(self._matching(request))})

    def query_download(self, request: QueryRequest) -> _Response:
        self.downloads += 1
        assert request.limit is not None and request.offset is not None
        rows = self._matching(request)[request.offset : request.offset + request.limit]
        # Only the columns this fake has; the app asks for 33.
        columns = [c for c in request.select if c in self.rows[0]]
        lines = ["\t".join(columns)]
        lines += ["\t".join(r[c] for c in columns) for r in rows]
        return _Response(text="\n".join(lines) + "\n")


@pytest.fixture
def run(monkeypatch):
    """Run a query's stages inline against a fake server.

    ``run(server, uuids, limit)`` returns ``(controller, pages, execute)``;
    each page is a ``results_ready`` payload.
    """

    class _Inline:
        def start(self, worker) -> None:
            worker.run()

    pool = _Inline()
    monkeypatch.setattr(QThreadPool, "globalInstance", lambda: pool)

    def make(server, uuids: list[str], limit: int):
        ctrl = QueryController()
        ctrl.set_annosaurus_client(server)
        pages: list = []
        ctrl.results_ready.connect(lambda *payload: pages.append(payload))
        ctrl.query_failed.connect(pytest.fail)

        def execute() -> None:
            ctrl.execute([QueryConstraint("association_uuid", in_=uuids)], limit=limit)

        return ctrl, pages, execute

    return make


def _rows(page) -> list[tuple[str, str]]:
    headers, rows = page[0], page[1]
    a, i = headers.index("association_uuid"), headers.index("image_reference_uuid")
    return [(r[a], r[i]) for r in rows]


def test_split_query_pages_in_one_time_order(run) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(18_568)]
    server = _FakeAnnosaurus(uuids[:18_500])  # some have no box
    ctrl, pages, execute = run(server, uuids, limit=5_000)

    execute()
    counts_after_first_page = server.counts
    while ctrl.has_next_page():
        ctrl.next_page()

    # Counted once, not again for each page.
    assert server.counts == counts_after_first_page == 10
    total = len(server.rows)
    assert [p[4] for p in pages] == [total] * len(pages)
    got = [key for page in pages for key in _rows(page)]
    expected = [
        (r["association_uuid"], r["image_reference_uuid"])
        for r in sorted(
            server.rows,
            key=lambda r: (
                r["index_recorded_timestamp"],
                r["association_uuid"],
                r["image_reference_uuid"],
            ),
        )
    ]
    assert got == expected  # every row once, in time order across pages

    last = len(pages)  # page numbers are 1-based
    ctrl.previous_page()
    assert _rows(pages[-1]) == expected[(last - 2) * 5_000 : (last - 1) * 5_000]
    assert server.counts == 10


def test_a_new_query_plans_again(run) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(3_000)]
    server = _FakeAnnosaurus(uuids)
    _ctrl, _pages, execute = run(server, uuids, limit=1_000)
    execute()
    execute()
    assert server.counts == 4  # two pieces, counted for each query


def test_huge_split_result_pages_by_piece(run, monkeypatch) -> None:
    from vars_gridview.lib.m3 import split_query

    monkeypatch.setattr(split_query, "MAX_RESOLVED_ROWS", 1_000)
    uuids = [str(uuid.uuid4()) for _ in range(5_000)]
    server = _FakeAnnosaurus(uuids)
    ctrl, pages, execute = run(server, uuids, limit=1_500)
    execute()
    while ctrl.has_next_page():
        ctrl.next_page()
    got = [key for page in pages for key in _rows(page)]
    assert sorted(got) == sorted(
        (r["association_uuid"], r["image_reference_uuid"]) for r in server.rows
    )
    assert len(got) == len(set(got))


def test_short_list_is_one_count_and_one_download(run) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(500)]
    server = _FakeAnnosaurus(uuids)
    _ctrl, pages, execute = run(server, uuids, limit=100)
    execute()
    assert (server.counts, server.downloads, len(pages[0][1])) == (1, 1, 100)


def test_nothing_matching_gives_an_empty_page(run) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(5_000)]
    server = _FakeAnnosaurus([str(uuid.uuid4())])
    _ctrl, pages, execute = run(server, uuids, limit=100)
    execute()
    assert pages[0][1] == [] and pages[0][4] == 0
