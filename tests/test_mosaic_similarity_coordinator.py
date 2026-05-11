from __future__ import annotations

from typing import Any, cast

from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    MosaicSimilarityCoordinator,
)


class _Rect:
    def __init__(
        self, name: str, label: str, distances: dict[str, float] | None = None
    ):
        self.name = name
        self.text_label = label
        self._distances = distances or {}

    def embedding_distance(self, other: "_Rect") -> float:
        if other.name not in self._distances:
            raise RuntimeError("distance unavailable")
        return self._distances[other.name]


def test_compute_similarity_sort_order_basic() -> None:
    clicked = _Rect("clicked", "fish", {"a": 0.3, "b": 0.1, "c": 0.2})
    rects = [
        _Rect("a", "fish"),
        _Rect("b", "fish"),
        _Rect("c", "fish"),
    ]

    order = MosaicSimilarityCoordinator.compute_similarity_sort_order(
        rect_widgets=cast(Any, rects),
        clicked_rect=cast(Any, clicked),
        same_class_only=False,
    )

    assert order == [1, 2, 0]


def test_compute_similarity_sort_order_same_class_only() -> None:
    clicked = _Rect("clicked", "fish", {"a": 0.1, "b": 0.2})
    rects = [
        _Rect("a", "fish"),
        _Rect("b", "coral"),
    ]

    order = MosaicSimilarityCoordinator.compute_similarity_sort_order(
        rect_widgets=cast(Any, rects),
        clicked_rect=cast(Any, clicked),
        same_class_only=True,
    )

    assert order == [0, 1]


def test_compute_similarity_sort_order_handles_distance_errors() -> None:
    clicked = _Rect("clicked", "fish", {"a": 0.4})
    rects = [_Rect("a", "fish"), _Rect("b", "fish")]

    order = MosaicSimilarityCoordinator.compute_similarity_sort_order(
        rect_widgets=cast(Any, rects),
        clicked_rect=cast(Any, clicked),
        same_class_only=False,
    )

    assert order == [0, 1]
