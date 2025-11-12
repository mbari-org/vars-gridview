import unittest
from vars_gridview.ui.QueryDialog import DepthRangeConstraintResult


class TestDepthRangeConstraintResult(unittest.TestCase):
    """Test the DepthRangeConstraintResult class."""

    def test_both_min_and_max(self):
        """Test depth range with both min and max values."""
        result = DepthRangeConstraintResult(100.0, 2500.0)
        
        # Check string representation
        self.assertEqual(str(result), "Depth: 100.0m - 2500.0m")
        
        # Check constraints
        constraints = list(result.constraints)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].column, "depth_meters")
        self.assertEqual(constraints[0].minmax, [100.0, 2500.0])

    def test_min_only(self):
        """Test depth range with only minimum value (>= 100m)."""
        result = DepthRangeConstraintResult(100.0, None)
        
        # Check string representation
        self.assertEqual(str(result), "Depth: >= 100.0m")
        
        # Check constraints
        constraints = list(result.constraints)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].column, "depth_meters")
        self.assertEqual(constraints[0].min, 100.0)
        self.assertIsNone(constraints[0].max)
        self.assertIsNone(constraints[0].minmax)

    def test_max_only(self):
        """Test depth range with only maximum value (<= 2500m)."""
        result = DepthRangeConstraintResult(None, 2500.0)
        
        # Check string representation
        self.assertEqual(str(result), "Depth: <= 2500.0m")
        
        # Check constraints
        constraints = list(result.constraints)
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].column, "depth_meters")
        self.assertEqual(constraints[0].max, 2500.0)
        self.assertIsNone(constraints[0].min)
        self.assertIsNone(constraints[0].minmax)

    def test_neither_min_nor_max(self):
        """Test depth range with neither min nor max (edge case)."""
        result = DepthRangeConstraintResult(None, None)
        
        # Check string representation
        self.assertEqual(str(result), "Depth: (no constraint)")
        
        # Check that no constraints are yielded
        constraints = list(result.constraints)
        self.assertEqual(len(constraints), 0)

    def test_example_shallow_water(self):
        """Example: Query for shallow water observations (0-100m)."""
        result = DepthRangeConstraintResult(0.0, 100.0)
        self.assertEqual(str(result), "Depth: 0.0m - 100.0m")

    def test_example_deep_water(self):
        """Example: Query for deep water observations (>= 2500m)."""
        result = DepthRangeConstraintResult(2500.0, None)
        self.assertEqual(str(result), "Depth: >= 2500.0m")


if __name__ == "__main__":
    unittest.main()
