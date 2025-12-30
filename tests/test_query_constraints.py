import unittest
from vars_gridview.lib.m3.query import QueryConstraint


class TestDepthConstraints(unittest.TestCase):
    """Test the depth range constraints functionality."""

    def test_min_depth_constraint(self):
        """Test that a minimum depth constraint is created correctly."""
        constraint = QueryConstraint(column="depth_meters", min=100.0)
        result_dict = constraint.to_dict()
        
        self.assertEqual(result_dict["column"], "depth_meters")
        self.assertEqual(result_dict["min"], 100.0)
        self.assertNotIn("max", result_dict)
        self.assertNotIn("minmax", result_dict)

    def test_max_depth_constraint(self):
        """Test that a maximum depth constraint is created correctly."""
        constraint = QueryConstraint(column="depth_meters", max=2500.0)
        result_dict = constraint.to_dict()
        
        self.assertEqual(result_dict["column"], "depth_meters")
        self.assertEqual(result_dict["max"], 2500.0)
        self.assertNotIn("min", result_dict)
        self.assertNotIn("minmax", result_dict)

    def test_minmax_depth_constraint(self):
        """Test that a depth range (minmax) constraint is created correctly."""
        constraint = QueryConstraint(column="depth_meters", minmax=[100.0, 2500.0])
        result_dict = constraint.to_dict()
        
        self.assertEqual(result_dict["column"], "depth_meters")
        self.assertEqual(result_dict["minmax"], [100.0, 2500.0])
        self.assertNotIn("min", result_dict)
        self.assertNotIn("max", result_dict)

    def test_constraint_to_dict_skip_null(self):
        """Test that null values are excluded when skip_null=True."""
        constraint = QueryConstraint(
            column="depth_meters",
            min=100.0,
            max=None,
            equals=None
        )
        result_dict = constraint.to_dict(skip_null=True)
        
        self.assertIn("column", result_dict)
        self.assertIn("min", result_dict)
        self.assertNotIn("max", result_dict)
        self.assertNotIn("equals", result_dict)


class TestLikeConstraints(unittest.TestCase):
    """Test the like and notlike constraints functionality."""

    def test_like_constraint(self):
        """Test that a like constraint is created correctly."""
        constraint = QueryConstraint(column="link_value", like='%"verifier":%')
        result_dict = constraint.to_dict()
        
        self.assertEqual(result_dict["column"], "link_value")
        self.assertEqual(result_dict["like"], '%"verifier":%')
        self.assertNotIn("notlike", result_dict)

    def test_notlike_constraint(self):
        """Test that a notlike constraint is created correctly."""
        constraint = QueryConstraint(column="link_value", notlike='%"verifier":%')
        result_dict = constraint.to_dict()
        
        self.assertEqual(result_dict["column"], "link_value")
        self.assertEqual(result_dict["notlike"], '%"verifier":%')
        self.assertNotIn("like", result_dict)

    def test_notlike_skip_null(self):
        """Test that null notlike value is excluded when skip_null=True."""
        constraint = QueryConstraint(
            column="link_value",
            notlike=None
        )
        result_dict = constraint.to_dict(skip_null=True)
        
        self.assertIn("column", result_dict)
        self.assertNotIn("notlike", result_dict)


if __name__ == "__main__":
    unittest.main()
