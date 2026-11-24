"""Stored-vector fetches are coalesced, and computing embeddings waits for
them so the service isn't asked for vectors the database is about to give."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from PyQt6 import QtCore, QtWidgets

import vars_gridview.lib.annotation  # noqa: F401  (import order)
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _HeldPool:
    """Keeps started workers until the test runs them."""

    def __init__(self) -> None:
        self.workers: list = []

    def start(self, worker) -> None:
        self.workers.append(worker)

    def run_all(self) -> None:
        workers, self.workers = self.workers, []
        for worker in workers:
            worker.run()


class _Store:
    description = "test"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def fetch(self, queries, name):
        self.calls += 1
        if self.fail:
            raise ConnectionError("down")
        return {q.association_uuid: [1.0, 0.0] for q in queries}, 0


def _tile() -> SimpleNamespace:
    tile = SimpleNamespace(
        association_uuid=uuid.uuid4(),
        association=SimpleNamespace(box=(0, 0, 5, 5), x=0, y=0, width=5, height=5),
        has_cached_embedding=False,
    )

    def cache_embedding(vector, box=None, space=None):
        tile.has_cached_embedding = True

    tile.cache_embedding = cache_embedding
    return tile


@pytest.fixture
def mosaic(tmp_path, monkeypatch):
    settings = AppSettings(
        QtCore.QSettings(str(tmp_path / "s.ini"), QtCore.QSettings.Format.IniFormat)
    )
    settings.vector_db_enabled.value = True
    settings.embedding_model_name.value = "dinov3"
    settings.vector_db_url.value = "http://qdrant"
    settings.vector_db_collection.value = "vars"
    view = QtWidgets.QGraphicsView()
    m = ImageMosaic(view, lambda *a: None, settings=settings)
    m._view = view  # keep it alive
    m._rect_widgets = [_tile() for _ in range(3)]
    m._all_rois_loaded = True
    m._embedding_model = SimpleNamespace(model_name="dinov3")
    store = _Store()
    monkeypatch.setattr(m, "_vector_store_for", lambda url, collection: store)
    pool = _HeldPool()
    monkeypatch.setattr(QtCore.QThreadPool, "globalInstance", lambda: pool)
    precomputes: list = []
    monkeypatch.setattr(
        m._embedding, "request_precompute", lambda **kw: precomputes.append(kw)
    )
    yield SimpleNamespace(
        m=m, store=store, pool=pool, precomputes=precomputes, settings=settings
    )
    # Otherwise the view outlives the mosaic's Python side and hands it
    # events in later tests.
    view.removeEventFilter(m)


def _fire(m: ImageMosaic) -> None:
    """Run the coalescing timer now."""
    m._stored_fetch_timer.stop()
    m._fetch_stored_embeddings_now()


def test_requests_close_together_make_one_fetch(mosaic) -> None:
    for _ in range(3):
        mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    assert len(mosaic.pool.workers) == 1


def test_same_fetch_isnt_started_twice(mosaic) -> None:
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    assert len(mosaic.pool.workers) == 1


def test_precompute_waits_for_the_fetch(mosaic) -> None:
    mosaic.m.fetch_stored_embeddings()
    mosaic.m.precompute_embeddings_async()  # e.g. right after a model switch
    assert mosaic.precomputes == []
    _fire(mosaic.m)
    assert mosaic.precomputes == []

    mosaic.pool.run_all()
    assert len(mosaic.precomputes) == 1
    assert all(t.has_cached_embedding for t in mosaic.m._rect_widgets)


def test_failed_fetch_still_starts_precompute(mosaic) -> None:
    mosaic.store.fail = True
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    mosaic.pool.run_all()
    assert len(mosaic.precomputes) == 1


def test_no_vector_database_precomputes_straight_away(mosaic) -> None:
    mosaic.settings.vector_db_enabled.value = False
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    assert mosaic.pool.workers == []
    assert len(mosaic.precomputes) == 1


def test_superseded_fetch_result_is_ignored(mosaic) -> None:
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    first = mosaic.pool.workers.pop()
    mosaic.settings.vector_db_collection.value = "other"
    mosaic.m.fetch_stored_embeddings()
    _fire(mosaic.m)
    assert len(mosaic.pool.workers) == 1  # a new fetch for the new collection

    first.run()  # the old one finishes late
    assert mosaic.precomputes == []
    assert not any(t.has_cached_embedding for t in mosaic.m._rect_widgets)
    mosaic.pool.run_all()
    assert len(mosaic.precomputes) == 1
