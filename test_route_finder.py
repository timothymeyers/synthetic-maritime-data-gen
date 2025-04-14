import logging
from route_finder import RouteFinder

def test_route_finder():
    # Initialize the route finder
    finder = RouteFinder()
    logger = logging.getLogger(__name__)
    
    # Load the data
    #url = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'
    finder.load_data()
    
    test_cases = [
        {
            "name": "US West Coast (should find major route)",
            "coords": (-125.4321268, 42.8346738),
            "threshold": 50
        },
        {
            "name": "Pacific Ocean (larger threshold)",
            "coords": (-129.6383054, 36.1078860),
            "threshold": 125
        },
        {
            "name": "Mediterranean",
            "coords": (47.3832503, -7.2682782),
            "threshold": 200
        },
        {
            "name": "Pacific (should find minor route)",
            "coords": (-54.1721954, 18.1547936),
            "threshold": 50
        }
    ]
    
    for case in test_cases:
        logger.info(f"\nTesting: {case['name']}")
        lon, lat = case['coords']
        result = finder.find_nearest_route(lon, lat, case['threshold'])
        
        if result:
            start, end = finder.get_route_endpoints(result['route'])
            logger.info(f"✅ Found {result['route_type']} Route {result['route_id']}" +
            f" | Distance: {result['distance_nm']:.2f} nautical miles"+
            f" | Position along route: {result['proj_distance']:.2f}" +
            f" | Route endpoints: {start} -> {end}")
        else:
            logger.warning(f"❌ No route found within {case['threshold']} nautical miles")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'  # Simple format to match previous print output
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting route finder tests...")
    # Run the test function
    test_route_finder()
