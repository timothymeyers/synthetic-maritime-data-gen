import unittest
from shapely.geometry import LineString, Point
import math, logging
from route_finder import RouteFinder, RouteType

class TestRouteFinder(unittest.TestCase):
    def setUp(self):
        self.finder = RouteFinder()
        
    def test_get_next_waypoints_forward(self):
        """Test getting waypoints in forward direction"""
        # Create a simple route going east
        coords = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
        route = LineString(coords)
        current_point = Point(1.5, 0)  # Between points 1 and 2
        heading = 90  # Moving east
        
        waypoints = self.finder.get_next_waypoints(route, current_point, heading, 2)
        
        self.assertEqual(len(waypoints), 2)
        self.assertEqual((waypoints[0].x, waypoints[0].y), (2, 0))
        self.assertEqual((waypoints[1].x, waypoints[1].y), (3, 0))
        
    def test_get_next_waypoints_reverse(self):
        """Test getting waypoints in reverse direction"""
        # Create a simple route going east
        coords = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
        route = LineString(coords)
        current_point = Point(1.5, 0)  # Between points 1 and 2
        heading = 270  # Moving west
        
        waypoints = self.finder.get_next_waypoints(route, current_point, heading, 2)
        
        self.assertEqual(len(waypoints), 2)
        self.assertEqual((waypoints[0].x, waypoints[0].y), (1, 0))
        self.assertEqual((waypoints[1].x, waypoints[1].y), (0, 0))
        
    def test_get_next_waypoints_fewer_available(self):
        """Test when fewer waypoints are available than requested"""
        coords = [(0, 0), (1, 0), (2, 0)]
        route = LineString(coords)
        current_point = Point(0.5, 0)
        heading = 90
        
        waypoints = self.finder.get_next_waypoints(route, current_point, heading, 3)
        
        self.assertEqual(len(waypoints), 2)  # Should only return available points
        self.assertEqual((waypoints[0].x, waypoints[0].y), (1, 0))
        self.assertEqual((waypoints[1].x, waypoints[1].y), (2, 0))
        
    def test_calculate_heading(self):
        """Test heading calculation"""
        # Test east direction
        heading = self.finder._calculate_heading((0, 0), (1, 0))
        self.assertAlmostEqual(heading, 90, places=1)
        
        # Test north direction
        heading = self.finder._calculate_heading((0, 0), (0, 1))
        self.assertAlmostEqual(heading, 0, places=1)
        
        # Test west direction
        heading = self.finder._calculate_heading((0, 0), (-1, 0))
        self.assertAlmostEqual(heading, 270, places=1)
        
        # Test south direction
        heading = self.finder._calculate_heading((0, 0), (0, -1))
        self.assertAlmostEqual(heading, 180, places=1)

    def _create_test_routes(self):
        """Helper method to create test routes of different types"""
        # Create a simple route layout:
        # Major route at y=0, Middle route at y=1, Minor route at y=2
        major_route = LineString([(0, 0), (10, 0)])
        middle_route = LineString([(0, 1), (10, 1)])
        minor_route = LineString([(0, 2), (10, 2)])
        
        self.finder.major = [major_route]
        self.finder.middle = [middle_route]
        self.finder.minor = [minor_route]
        self.finder._build_indices()

    def test_find_nearest_major_route(self):
        """Test finding nearest major route"""
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 0.1, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)  # 0.1 degrees ≈ 6 nm

    def test_find_nearest_middle_route(self):
        """Test finding nearest middle route when closer to middle route"""
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 1.1, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MIDDLE)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)

    def test_find_nearest_minor_route(self):
        """Test finding nearest minor route when closer to minor route"""
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 2.1, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)

    def test_no_route_found(self):
        """Test when no route is within distance threshold"""
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 5.0, distance_threshold=50)
        
        self.assertIsNone(result)

    def test_distance_threshold_progression(self):
        """Test finding route with incrementally increasing distance thresholds"""
        self._create_test_routes()
        test_point = (5.0, 0.5)  # 30nm from major route
        
        # Should not find route at small thresholds
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=5)
        self.assertIsNone(result)
        
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=10)
        self.assertIsNone(result)
        
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=15)
        self.assertIsNone(result)
        
        # Should find route at larger threshold
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=35)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['distance_nm'], 35)

    def test_route_priority(self):
        """Test that major routes are preferred when equidistant"""
        # Place all routes at exactly the same distance from test point
        test_point = (5.0, 1.0)
        major_route = LineString([(0, 0), (10, 0)])  # 1 degree below test point
        middle_route = LineString([(0, 2), (10, 2)])  # 1 degree above test point
        minor_route = LineString([(0, 3), (10, 3)])   # 2 degrees above test point
        
        self.finder.major = [major_route]
        self.finder.middle = [middle_route]
        self.finder.minor = [minor_route]
        self.finder._build_indices()
        
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=70)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        # Both routes should be 60nm away (1 degree = 60 nautical miles)
        self.assertAlmostEqual(result['distance_nm'], 60.0, places=1)

    def test_num_candidates(self):
        """Test that num_candidates parameter affects search"""
        # Create multiple major routes
        routes = [
            LineString([(0, i), (10, i)]) for i in range(5)
        ]
        self.finder.major = routes
        self.finder._build_indices()
        
        # Test with limited candidates
        result_limited = self.finder.find_nearest_route(5.0, 2.5, distance_threshold=50, num_candidates=1)
        result_all = self.finder.find_nearest_route(5.0, 2.5, distance_threshold=50, num_candidates=5)
        
        self.assertIsNotNone(result_limited)
        self.assertIsNotNone(result_all)
        self.assertGreaterEqual(result_limited['distance_nm'], result_all['distance_nm'])

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    unittest.main()
