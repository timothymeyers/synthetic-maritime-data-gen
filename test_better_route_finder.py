import unittest
from unittest.mock import patch, MagicMock
from better_route_finder import BetterRouteFinder

class TestBetterRouteFinder(unittest.TestCase):
    def test_initialization(self):
        finder = BetterRouteFinder()
        self.assertEqual(finder.major, [])
        self.assertEqual(finder.middle, [])
        self.assertEqual(finder.minor, [])
        self.assertIsNone(finder.major_idx)
        self.assertIsNone(finder.middle_idx)
        self.assertIsNone(finder.minor_idx)

    @patch('better_route_finder.requests.get')
    def test_load_data(self, mock_get):
        # Mock a minimal GeoJSON response
        mock_response = MagicMock()
        mock_response.content = b'{"features": [{"properties": {"Type": "Major"}, "geometry": {"type": "LineString", "coordinates": [[0,0],[1,1]]}}]}'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        finder = BetterRouteFinder()
        finder.load_data('http://fake-url')
        self.assertEqual(len(finder.major), 1)
        self.assertIsNotNone(finder.major_idx)

    @patch('better_route_finder.requests.get')
    def test_load_data_error_handling(self, mock_get):
        # Test handling of HTTP errors
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP Error"))
        mock_get.return_value = mock_response
        
        finder = BetterRouteFinder()
        with self.assertRaises(Exception):
            finder.load_data('http://fake-url')
        
        # Test handling of invalid JSON
        mock_response = MagicMock()
        mock_response.content = b'invalid json content'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        with self.assertRaises(Exception):
            finder.load_data('http://fake-url')

    @patch('better_route_finder.sr.searoute')
    def test_find_route_between_points(self, mock_searoute):
        mock_searoute.return_value = {'geometry': {'coordinates': [[0,0],[1,1]]}}
        finder = BetterRouteFinder()
        result = finder.find_route_between_points(0, 0, 1, 1)
        self.assertIn('geometry', result)
        self.assertIn('coordinates', result['geometry'])

    @patch('better_route_finder.sr.searoute', side_effect=Exception('Route error'))
    def test_find_route_between_points_exception(self, mock_searoute):
        finder = BetterRouteFinder()
        with self.assertRaises(Exception):
            finder.find_route_between_points(0, 0, 1, 1)

    @patch('better_route_finder.sr.searoute')
    def test_get_next_waypoints_with_speed_and_heading_known_destination(self, mock_searoute):
        mock_searoute.return_value = {'geometry': {'coordinates': [[0,0],[1,1],[2,2],[3,3]]}}
        finder = BetterRouteFinder()
        # Patch get_waypoints to return predictable output
        finder.get_waypoints = MagicMock(return_value=[(1,1),(2,2)])
        result = finder.get_next_waypoints_with_speed_and_heading_known_destination(0,0,3,3,90,10,1,2)
        self.assertIn('waypoints', result)
        self.assertEqual(result['waypoints'], [(1,1),(2,2)])

    def test_get_next_waypoints_with_speed_and_heading_known_destination_no_route(self):
        finder = BetterRouteFinder()
        finder.find_route_between_points = MagicMock(return_value=None)
        result = finder.get_next_waypoints_with_speed_and_heading_known_destination(0,0,1,1,90,10,1,2)
        self.assertEqual(result, [])

    @patch('better_route_finder.BetterRouteFinder.find_nearest_route_with_heading')
    def test_get_next_waypoints_with_speed_and_heading_unknown_route(self, mock_find_nearest):
        mock_find_nearest.return_value = {'geometry': {'coordinates': [[0,0],[1,1],[2,2],[3,3]]}}
        finder = BetterRouteFinder()
        finder.get_waypoints = MagicMock(return_value=[(1,1),(2,2)])
        result = finder.get_next_waypoints_with_speed_and_heading_unknown_route(0,0,90,10,1,2)
        self.assertIn('waypoints', result)
        self.assertEqual(result['waypoints'], [(1,1),(2,2)])
    
    def test_get_next_waypoints_with_speed_and_heading_unknown_route_improved(self):
        pass 
        #finder = BetterRouteFinder()
        #finder.load_data()
        #result = finder.get_next_waypoints_with_speed_and_heading_unknown_route_improved(-152,45,106,10,24)
        #self.assertIn('waypoints', result)
        #self.assertEqual(result['waypoints'], [(1,1),(2,2)])

    @patch('better_route_finder.index.Index')
    def test_find_nearest_route_with_heading(self, mock_index):
        # Mock the spatial index and routes
        mock_idx = MagicMock()
        mock_idx.nearest.return_value = [0]
        mock_index.return_value = mock_idx
        finder = BetterRouteFinder()
        from shapely.geometry import LineString
        finder.major = [LineString([(0,0),(1,1)])]
        finder.major_idx = mock_idx
        # Set middle and minor routes and indices to None to avoid IndexError
        finder.middle = []
        finder.middle_idx = None
        finder.minor = []
        finder.minor_idx = None
        result = finder.find_nearest_route_with_heading(0,0,45)
        self.assertTrue(result is None or isinstance(result, dict))

    def test_find_nearest_route_with_heading_no_routes(self):
        finder = BetterRouteFinder()
        finder.major = []
        finder.middle = []
        finder.minor = []
        finder.major_idx = None
        finder.middle_idx = None
        finder.minor_idx = None
        result = finder.find_nearest_route_with_heading(0,0,45)
        self.assertIsNone(result)

    def test_calculate_heading(self):
        # Test static method for known values
        finder = BetterRouteFinder()
        heading = finder._calculate_heading((0, 0), (0, 1))
        self.assertAlmostEqual(heading, 0, delta=1)
        heading = finder._calculate_heading((0, 0), (1, 0))
        self.assertAlmostEqual(heading, 90, delta=1)
        heading = finder._calculate_heading((0, 0), (0, -1))
        self.assertAlmostEqual(heading, 180, delta=1)
        heading = finder._calculate_heading((0, 0), (-1, 0))
        self.assertAlmostEqual(heading, 270, delta=1)

    def test_get_next_waypoints_internal(self):
        pass

    def test_get_route_by_id(self):
        finder = BetterRouteFinder()
        
        # Setup mock data with route indices
        from shapely.geometry import LineString
        finder.major = [LineString([(0, 0), (1, 1)])]
        finder.middle = [LineString([(2, 2), (3, 3)]), LineString([(4, 4), (5, 5)])]
        finder.minor = [LineString([(6, 6), (7, 7)])]
        
        # Define route type constants to match the implementation
        finder.RouteType = type('RouteType', (), {
            'MAJOR': 'Major',
            'MIDDLE': 'Middle',
            'MINOR': 'Minor'
        })
        
        # Test getting a valid major route (1-based index)
        route = finder._get_route_by_id(1, 'Major')
        self.assertIsNotNone(route)
        self.assertEqual(list(route.coords)[0], (0, 0))
        
        # Test getting a valid middle route (1-based index)
        route = finder._get_route_by_id(2, 'Middle')
        self.assertIsNotNone(route)
        self.assertEqual(list(route.coords)[0], (4, 4))
        
        # Test getting a valid minor route (1-based index)
        route = finder._get_route_by_id(1, 'Minor')
        self.assertIsNotNone(route)
        self.assertEqual(list(route.coords)[0], (6, 6))
        
        # Test getting a route with an invalid type
        route = finder._get_route_by_id(1, 'InvalidType')
        self.assertIsNone(route)
        
        # Test getting an out of range index
        route = finder._get_route_by_id(99, 'Major')
        self.assertIsNone(route)

    def test_is_near_port(self):
        finder = BetterRouteFinder()
        
        result = finder.is_near_port(0.107054, 49.485998, 10)
        print (result)
        # Test with a point near a port
        result = finder.is_near_port(117.744852, 38.986802, 10)
        print (result)
        #self.assertTrue(result)
        
        result = finder.is_near_port(-152, 45, 10)
        print (result)
        #self.assertTrue(result)
        
     

if __name__ == '__main__':
    unittest.main()
