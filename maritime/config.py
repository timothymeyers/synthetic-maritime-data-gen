"""Configuration constants for maritime routing."""

# Data source
DEFAULT_DATA = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'

# Route finding parameters
HEADING_WEIGHT = 0.9  # Weight for heading difference when prioritizing routes
DISTANCE_WEIGHT = 0.1  # Weight for distance when prioritizing routes
METERS_PER_NAUTICAL_MILE = 1852

# Default thresholds
DEFAULT_DISTANCE_THRESHOLD = 5.0  # nautical miles
DEFAULT_HEADING_THRESHOLD = 30.0  # degrees
DEFAULT_NUM_CANDIDATES = 10
