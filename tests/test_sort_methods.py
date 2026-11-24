import unittest
from unittest.mock import Mock

from vars_gridview.lib.sorting.sort_methods import AspectRatioSort


class TestAspectRatioSort(unittest.TestCase):
    def test_aspect_ratio_wide_box(self):
        """Test aspect ratio for a wide (horizontal) box."""
        rect = Mock()
        rect.association.width = 100
        rect.association.height = 50

        result = AspectRatioSort.key(rect)
        self.assertEqual(result, 2.0)  # 100/50 = 2.0 (wide)

    def test_aspect_ratio_tall_box(self):
        """Test aspect ratio for a tall (narrow/vertical) box."""
        rect = Mock()
        rect.association.width = 50
        rect.association.height = 100

        result = AspectRatioSort.key(rect)
        self.assertEqual(result, 0.5)  # 50/100 = 0.5 (tall)

    def test_aspect_ratio_square_box(self):
        """Test aspect ratio for a square box."""
        rect = Mock()
        rect.association.width = 100
        rect.association.height = 100

        result = AspectRatioSort.key(rect)
        self.assertEqual(result, 1.0)  # 100/100 = 1.0 (square)

    def test_aspect_ratio_zero_height(self):
        """Test aspect ratio with zero height (edge case)."""
        rect = Mock()
        rect.association.width = 100
        rect.association.height = 0

        result = AspectRatioSort.key(rect)
        self.assertEqual(result, 0.0)  # Should handle division by zero


if __name__ == "__main__":
    unittest.main()


def test_sorts_tolerate_missing_and_mixed_keys():
    """None / mixed-type keys (confidence: null, ROI not loaded yet) used to
    raise TypeError out of the sort."""
    from vars_gridview.lib.sorting.sort_methods import (
        ConfidenceSort,
        IntensityMeanSort,
        NoopSort,
        SortMethodGroup,
    )

    def rect(confidence, roi=None):
        r = Mock()
        r.association.data = (
            {} if confidence == "absent" else {"confidence": confidence}
        )
        r.roi = roi
        r.name = repr(confidence)
        return r

    rects = [rect(None), rect(0.9), rect("absent"), rect("0.5"), rect(0.1)]
    ConfidenceSort.sort(rects)
    # Numbers first (absent counts as the 0.0 default), then text, then null.
    assert [r.name for r in rects] == ["'absent'", "0.1", "0.9", "'0.5'", "None"]

    rects = [rect(0.2), rect(0.1)]
    NoopSort.sort(rects)
    assert [r.name for r in rects] == ["0.2", "0.1"]  # order kept

    rects = [rect(0.2), rect(0.1)]  # roi None: the pixel key fails -> missing
    SortMethodGroup(IntensityMeanSort, ConfidenceSort).sort(rects)
    assert [r.name for r in rects] == ["0.1", "0.2"]
