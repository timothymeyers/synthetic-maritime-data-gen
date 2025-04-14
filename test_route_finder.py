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

    def test_find_nearest_route_with_heading_aligned(self):
        """Test finding a route that aligns with the current heading"""
        self._create_test_routes()
        # Test point near major route (y=0) heading east (90 degrees)
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 90, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)  # Should be close to 90 degrees
        
    def test_find_nearest_route_with_heading_misaligned(self):
        """Test that misaligned routes are not returned"""
        self._create_test_routes()
        # Test point near major route but heading north (0 degrees)
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 0, distance_threshold=50)
        
        self.assertIsNone(result)  # Should not find a route as heading is perpendicular
        
    def test_find_nearest_route_with_heading_priority(self):
        """Test that major routes are prioritized when multiple routes align with heading"""
        self._create_test_routes()
        # Add a parallel major route
        major_route2 = LineString([(0, 0.5), (10, 0.5)])
        self.finder.major.append(major_route2)
        self.finder._build_indices()
        
        # Test point between two parallel routes heading east
        result = self.finder.find_nearest_route_with_heading(5.0, 0.25, 90, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)
        
    def test_find_nearest_route_with_heading_reverse_direction(self):
        """Test finding a route when traveling in reverse direction"""
        self._create_test_routes()
        # Test point near major route heading west (270 degrees)
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 270, distance_threshold=50)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)

class TestRouteFinderWithRealData(unittest.TestCase):
    """Test RouteFinder with actual shipping lane data from default URL."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the route finder once for all tests and load real data."""
        cls.finder = RouteFinder()
        cls.finder.load_data()  # Loads from the default URL
    
    def test_atlantic_ocean_major_route(self):
        """Test finding a major route in the Atlantic Ocean."""
        result = self.finder.find_nearest_route(
            lon=-67.5313058, 
            lat=34.9986041, 
            distance_threshold=150
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 16)
    
    
    def test_pacific_ocean_minor_route(self):
        """Test finding a minor route in the Pacific Ocean."""
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=15
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertEqual(result['route_id'], 14)
    
    def test_pacific_ocean_middle_route(self):
        """Test finding a middle route in the Pacific Ocean."""
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=25
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MIDDLE)
        self.assertEqual(result['route_id'], 49)
    
    def test_pacific_ocean_major_route(self):
        """Test finding a major route in the Pacific Ocean."""
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 17)
        
    def test_pacific_ocean_all_routes(self):
        """Test finding a major route in the Pacific Ocean."""
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75,
            all_routes=True
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertEqual(result['route_id'], 14)
        
    def test_get_next_waypoints_pacific_eastward(self):
        """Test getting the next 5 waypoints on a Pacific Ocean route with eastward heading."""
        # First find a suitable route in the Pacific
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75
        )
        
        self.assertIsNotNone(result)
        route = result['route']
        
        # Select a point somewhere on the route
        point_on_route = Point(route.coords[len(route.coords) // 3])
        
        # Use an eastward heading (90 degrees)
        heading = 90
        
        # Get the next 5 waypoints
        waypoints = self.finder.get_next_waypoints(route, point_on_route, heading, 5)
        
        # Verify we got waypoints
        self.assertEqual(len(waypoints), 5)
        
        # Verify the waypoints are in the correct direction (generally eastward)
        for i in range(1, len(waypoints)):
            # Each subsequent point should be eastward (increasing longitude)
            self.assertGreaterEqual(waypoints[i].x, waypoints[i-1].x)
            
    def test_find_nearest_route_with_heading_pacific_NW(self):
        """Test finding a route with a specific heading in the Pacific Ocean."""
        # First find a suitable route in the Pacific
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75,
            heading=304.5,
            heading_threshold=20
        )

        # Verify we got a result
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 17)
        self.assertLess(result['heading_diff'], 20)
        
    def test_find_nearest_route_with_heading_pacific_Fail(self):
        """Test finding a route with a specific heading in the Pacific Ocean."""
        # First find a suitable route in the Pacific
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=15,
            heading=304.5,
            heading_threshold=20
        )

        # Verify we got a result
        self.assertIsNone(result)
        
    def test_find_nearest_route_with_heading_pacific_SW(self):
        """Test finding a route with a specific heading in the Pacific Ocean."""
        # First find a suitable route in the Pacific
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75,
            heading=259.052897776481,
            heading_threshold=20
        )
        
        """expected_result = [
            {'route_id': 14, 'route': <LINESTRING (-180 9.079, -179.78 9.215, -179.35 9.477, -179.128 9.612, -178....>, 'proj_distance': 60.753517908220836, 'nearest_point': <POINT (-124.023 31.642)>, 'distance_nm': 8.611009030208416, 'route_type': 'Minor', 'heading_diff': 0.0, 'route_heading': 259.052897776481}, {'route_id': 49, 'route': <LINESTRING (-157.621 21.321, -157.256 21.489, -157.185 21.522, -157.114 21....>, 'proj_distance': 35.277247311102265, 'nearest_point': <POINT (-124.051 31.806)>, 'distance_nm': 18.61356735080749, 'route_type': 'Middle', 'heading_diff': 0.07369215317851285, 'route_heading': 258.9792056233025}]"""
       
        
        # Verify we got a result
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertEqual(result['route_id'], 14)
        self.assertLess(result['heading_diff'], 20)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    unittest.main()
