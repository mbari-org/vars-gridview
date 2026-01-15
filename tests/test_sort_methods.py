import unittest
from unittest.mock import Mock
from vars_gridview.lib.sort_methods import AspectRatioSort


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
