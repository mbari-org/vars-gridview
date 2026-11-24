from __future__ import annotations

from types import SimpleNamespace

import pytest

from vars_gridview.ui.mosaic.mosaic_view import (
    MosaicView,
    MosaicVisibilityFilters,
    association_confidence,
)


def _tile(confidence: object, label: str = "fish") -> SimpleNamespace:
    data = {} if confidence is None else {"confidence": confidence}
    association = SimpleNamespace(
        data=data, text_label=label, verified=False, is_training=False
    )
    return SimpleNamespace(association=association)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.71, 0.71),  # fraction
        (71.0, 0.71),  # percentage, as the Piscivore detector stores it
        ("59", 0.59),
        (100, 1.0),
        (1.0, 1.0),
        (0, 0.0),
        (None, None),
        ("n/a", None),
        (float("nan"), None),
        (-3, None),
        (True, None),
    ],
)
def test_association_confidence_scales(raw: object, expected: float | None) -> None:
    value = association_confidence(_tile(raw).association)
    assert value == (None if expected is None else pytest.approx(expected))


def test_confidence_range_on_percentage_values() -> None:
    tiles = [_tile(c) for c in (20.0, 55.0, 71.0, 98.0)]

    def shown(lo: float, hi: float) -> list[float]:
        result = MosaicView.apply_filters(
            all_widgets=tiles,
            filters=MosaicVisibilityFilters(min_confidence=lo, max_confidence=hi),
        )
        return [t.association.data["confidence"] for t in result.visible]

    assert shown(0.0, 1.0) == [20.0, 55.0, 71.0, 98.0]
    assert shown(0.0, 0.99) == [20.0, 55.0, 71.0, 98.0]  # used to hide all
    assert shown(0.5, 0.8) == [55.0, 71.0]
