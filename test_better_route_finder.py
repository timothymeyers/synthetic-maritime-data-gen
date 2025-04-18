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

    @patch('better_route_finder.sr.searoute')
    def test_find_route_between_points(self, mock_searoute):
        mock_searoute.return_value = {'geometry': {'coordinates': [[0,0],[1,1]]}}
        finder = BetterRouteFinder()
        result = finder.find_route_between_points(0, 0, 1, 1)
        self.assertIn('geometry', result)
        self.assertIn('coordinates', result['geometry'])

    @patch('better_route_finder.sr.searoute')
    def test_get_next_waypoints_with_speed_and_heading_known_destination(self, mock_searoute):
        mock_searoute.return_value = {'geometry': {'coordinates': [[0,0],[1,1],[2,2],[3,3]]}}
        finder = BetterRouteFinder()
        # Patch get_waypoints to return predictable output
        finder.get_waypoints = MagicMock(return_value=[(1,1),(2,2)])
        result = finder.get_next_waypoints_with_speed_and_heading_known_destination(0,0,3,3,90,10,1,2)
        self.assertIn('waypoints', result)
        self.assertEqual(result['waypoints'], [(1,1),(2,2)])

    @patch('better_route_finder.BetterRouteFinder.find_nearest_route_with_heading')
    def test_get_next_waypoints_with_speed_and_heading_unknown_route(self, mock_find_nearest):
        mock_find_nearest.return_value = {'geometry': {'coordinates': [[0,0],[1,1],[2,2],[3,3]]}}
        finder = BetterRouteFinder()
        finder.get_waypoints = MagicMock(return_value=[(1,1),(2,2)])
        result = finder.get_next_waypoints_with_speed_and_heading_unknown_route(0,0,90,10,1,2)
        self.assertIn('waypoints', result)
        self.assertEqual(result['waypoints'], [(1,1),(2,2)])

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

if __name__ == '__main__':
    unittest.main()
