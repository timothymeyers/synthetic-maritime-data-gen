import unittest
from shapely.geometry import LineString, Point
import math, logging
from route_finder import RouteFinder, RouteType

class TestRouteFinder(unittest.TestCase):
    def setUp(self):
        self.finder = RouteFinder()
        # Create test routes for use with route_id-based API
        self.coords_major = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
        self.major_route = LineString(self.coords_major)
        self.finder.major = [self.major_route]
        self.finder.middle = []
        self.finder.minor = []
        self.finder._build_indices()

    def test_get_next_waypoints_forward(self):
        """Test getting waypoints in forward direction"""
        # Use route_id=1, current position between points 1 and 2
        route_id = 1
        lon, lat = 1.5, 0
        heading = 90  # Moving east
        waypoints = self.finder.get_next_waypoints(route_id, lon, lat, heading, 2)
        self.assertEqual(len(waypoints), 2)
        self.assertEqual(waypoints[0], [2, 0])
        self.assertEqual(waypoints[1], [3, 0])

    def test_get_next_waypoints_reverse(self):
        """Test getting waypoints in reverse direction"""
        route_id = 1
        lon, lat = 1.5, 0
        heading = 270  # Moving west
        waypoints = self.finder.get_next_waypoints(route_id, lon, lat, heading, 2)
        self.assertEqual(len(waypoints), 2)
        self.assertEqual(waypoints[0], [1, 0])
        self.assertEqual(waypoints[1], [0, 0])

    def test_get_next_waypoints_fewer_available(self):
        """Test when fewer waypoints are available than requested"""
        # Use a short route
        coords = [(0, 0), (1, 0), (2, 0)]
        self.finder.major = [LineString(coords)]
        self.finder._build_indices()
        route_id = 1
        lon, lat = 0.5, 0
        heading = 90
        waypoints = self.finder.get_next_waypoints(route_id, lon, lat, heading, 3)
        self.assertEqual(len(waypoints), 2)
        self.assertEqual(waypoints[0], [1, 0])
        self.assertEqual(waypoints[1], [2, 0])

    def test_calculate_heading(self):
        """Test heading calculation"""
        heading = self.finder._calculate_heading((0, 0), (1, 0))
        self.assertAlmostEqual(heading, 90, places=1)
        heading = self.finder._calculate_heading((0, 0), (0, 1))
        self.assertAlmostEqual(heading, 0, places=1)
        heading = self.finder._calculate_heading((0, 0), (-1, 0))
        self.assertAlmostEqual(heading, 270, places=1)
        heading = self.finder._calculate_heading((0, 0), (0, -1))
        self.assertAlmostEqual(heading, 180, places=1)

    def _create_test_routes(self):
        major_route = LineString([(0, 0), (10, 0)])
        middle_route = LineString([(0, 1), (10, 1)])
        minor_route = LineString([(0, 2), (10, 2)])
        self.finder.major = [major_route]
        self.finder.middle = [middle_route]
        self.finder.minor = [minor_route]
        self.finder._build_indices()

    def test_find_nearest_major_route(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 0.1, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)

    def test_find_nearest_middle_route(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 1.1, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MIDDLE)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)

    def test_find_nearest_minor_route(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 2.1, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertAlmostEqual(result['distance_nm'], 6.0, places=1)

    def test_no_route_found(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route(5.0, 5.0, distance_threshold=50)
        self.assertIsNone(result)

    def test_distance_threshold_progression(self):
        self._create_test_routes()
        test_point = (5.0, 0.5)
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=5)
        self.assertIsNone(result)
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=10)
        self.assertIsNone(result)
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=15)
        self.assertIsNone(result)
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=35)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['distance_nm'], 35)

    def test_route_priority(self):
        test_point = (5.0, 1.0)
        major_route = LineString([(0, 0), (10, 0)])
        middle_route = LineString([(0, 2), (10, 2)])
        minor_route = LineString([(0, 3), (10, 3)])
        self.finder.major = [major_route]
        self.finder.middle = [middle_route]
        self.finder.minor = [minor_route]
        self.finder._build_indices()
        result = self.finder.find_nearest_route(test_point[0], test_point[1], distance_threshold=70)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertAlmostEqual(result['distance_nm'], 60.0, places=1)

    def test_num_candidates(self):
        routes = [LineString([(0, i), (10, i)]) for i in range(5)]
        self.finder.major = routes
        self.finder._build_indices()
        result_limited = self.finder.find_nearest_route(5.0, 2.5, distance_threshold=50, num_candidates=1)
        result_all = self.finder.find_nearest_route(5.0, 2.5, distance_threshold=50, num_candidates=5)
        self.assertIsNotNone(result_limited)
        self.assertIsNotNone(result_all)
        self.assertGreaterEqual(result_limited['distance_nm'], result_all['distance_nm'])

    def test_find_nearest_route_with_heading_aligned(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 90, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)

    def test_find_nearest_route_with_heading_misaligned(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 0, distance_threshold=50)
        self.assertIsNone(result)

    def test_find_nearest_route_with_heading_priority(self):
        self._create_test_routes()
        major_route2 = LineString([(0, 0.5), (10, 0.5)])
        self.finder.major.append(major_route2)
        self.finder._build_indices()
        result = self.finder.find_nearest_route_with_heading(5.0, 0.25, 90, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)

    def test_find_nearest_route_with_heading_reverse_direction(self):
        self._create_test_routes()
        result = self.finder.find_nearest_route_with_heading(5.0, 0.1, 270, distance_threshold=50)
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertLess(result['heading_diff'], 45)

    def test_will_intersect_route_circle(self):
        """Test _will_intersect_route for 32 headings around a simple horizontal route."""
        import math
        finder = RouteFinder()
        # Horizontal route from (0,0) to (10,0)
        route = LineString([(0, 0), (10, 0)])
        finder.major = [route]
        finder.middle = []
        finder.minor = []
        finder._build_indices()
        route_id = 1
        route_type = RouteType.MAJOR
        # Place ship at (5, 1) (1 unit north of the route)
        lon, lat = 5, 1
        results = []
        for i in range(32):
            heading = i * 360 / 32
            intersects = finder._will_intersect_route(lon, lat, heading, route_id, route_type)
            results.append((heading, intersects))
        # Headings 180 (south, toward route) should intersect, 0 (north, away) should not
        # Parallel (90, 270) should not intersect
        for heading, intersects in results:
            # Toward route: headings between 135 and 225 (±45° around 180)
            if 90 < heading < 270:
                self.assertTrue(intersects, f"Heading {heading} should intersect route")
            # Away from route: headings between 315-360 or 0-45 (±45° around 0)
            elif heading == 90 or heading == 270:
                self.assertFalse(intersects, f"Heading {heading} should not intersect route (parallel)")
            # Parallel: 80-100 and 260-280
            elif heading < 90 or heading > 270:
                self.assertFalse(intersects, f"Heading {heading} should not intersect route (away)")
            # Other angles: ambiguous, just check it's a boolean
            else:
                self.assertIsInstance(intersects, bool)

class TestRouteFinderWithRealData(unittest.TestCase):
    """Test RouteFinder with actual shipping lane data from default URL."""
    
    @classmethod
    def setUpClass(cls):
        cls.finder = RouteFinder()
        cls.finder.load_data()  # Loads from the default URL

    def test_atlantic_ocean_major_route(self):
        result = self.finder.find_nearest_route(
            lon=-67.5313058, 
            lat=34.9986041, 
            distance_threshold=150
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 16)
    
    def test_pacific_ocean_minor_route(self):
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=15
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MINOR)
        self.assertEqual(result['route_id'], 14)
    
    def test_pacific_ocean_middle_route(self):
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=25
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MIDDLE)
        self.assertEqual(result['route_id'], 49)
    
    def test_pacific_ocean_major_route(self):
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 17)
        
    def test_pacific_ocean_all_routes(self):
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
        result = self.finder.find_nearest_route(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75
        )
        self.assertIsNotNone(result)
        route_id = result['route_id']
        # Use a point on the route (simulate as first coordinate)
        endpoints = self.finder.get_route_endpoints(route_id, result['route_type'])
        lon, lat = endpoints['start']
        heading = 90
        waypoints = self.finder.get_next_waypoints(route_id, lon, lat, heading, 5, result['route_type'])
        self.assertEqual(len(waypoints), 5)
        for i in range(1, len(waypoints)):
            self.assertGreaterEqual(waypoints[i][0], waypoints[i-1][0])
            # longitude should be increasing or equal
        
    def test_find_nearest_route_with_heading_pacific_NW(self):
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75,
            heading=304.5,
            heading_threshold=20
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['route_type'], RouteType.MAJOR)
        self.assertEqual(result['route_id'], 17)
        self.assertLess(result['heading_diff'], 20)
        
    def test_find_nearest_route_with_heading_pacific_Fail(self):
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=15,
            heading=304.5,
            heading_threshold=20
        )
        self.assertIsNone(result)
        
    def test_find_nearest_route_with_heading_pacific_SW(self):
        result = self.finder.find_nearest_route_with_heading(
            lon=-124, 
            lat=31.5, 
            distance_threshold=75,
            heading=259.052897776481,
            heading_threshold=20
        )
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
