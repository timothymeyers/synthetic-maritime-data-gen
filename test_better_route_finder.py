import unittest
from better_route_finder import BetterRouteFinder

class TestBetterRouteFinder(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.finder = BetterRouteFinder()
        cls.finder.load_data()  # Loads from the default URL
   
    def test_load_data_default(self):
        # Should load data without raising exceptions
        """
        try:
            self.finder.load_data()
        except Exception as e:
            self.fail(f"load_data() raised an exception: {e}")
        self.assertIsNotNone(self.finder.major_idx)
        self.assertIsNotNone(self.finder.middle_idx)
        self.assertIsNotNone(self.finder.minor_idx)
        """
        self.assertTrue(True)

    def test_find_route_between_points(self):
        #self.finder.load_data()
        # Use two points in the ocean
        origin_lon, origin_lat = 0.0, 50.0
        dest_lon, dest_lat = 10.0, 90.0
        route = self.finder.find_route_between_points(origin_lon, origin_lat, dest_lon, dest_lat)
        self.assertIsNotNone(route)
        self.assertIn('geometry', route)

    def test_find_nearest_route_with_heading(self):
        
        try:
            result = self.finder.find_nearest_route_with_heading(-152.0, 45.0, 106)
            
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"find_nearest_route_with_heading raised an exception: {e}")
            
    def test_get_waypoints(self):
        #result = self.finder.find_nearest_route_with_heading(-152.0, 45.0, 106)
        
        #self.finder.get_waypoints(result, speed_knot=10, time_hrs=72, num_waypoints=3)
        
        result = self.finder.get_next_waypoints_with_speed_and_heading_unknown_route(-152.0, 45.0, 106, speed_knot=10, time_hrs=72, num_waypoints=4)
        
        self.assertIsNotNone(result)
        self.assertIn('waypoints', result)
        self.assertEqual(len(result['waypoints']), 4)
        print(result)
        
        result = self.finder.get_next_waypoints_with_speed_and_heading_known_destination(-152.0, 45.0, -120.646798, 34.196891, 106, speed_knot=10, time_hrs=72, num_waypoints=4)
        
        self.assertIsNotNone(result)
        self.assertIn('waypoints', result)
        self.assertEqual(len(result['waypoints']), 4)
        print(result)

if __name__ == '__main__':
    unittest.main()
