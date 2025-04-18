"""Port finding functionality for maritime routing."""

import logging
import osmnx as ox
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Point
from .config import METERS_PER_NAUTICAL_MILE

logger = logging.getLogger(__name__)

class PortFinder:
    """Class to find ports in proximity to geographic coordinates."""
    
    @staticmethod
    def is_near_port(lon: float, lat: float, distance_threshold: float = 5.0) -> bool:
        """Check if a point is near a port within a specified distance.
        
        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            distance_threshold: Distance in nautical miles to consider as "near"
            
        Returns:
            True if the point is near a port, False otherwise
        """
        logger.debug(f"Checking if point ({lon}, {lat}) is near a port within {distance_threshold}nm")
        
        # Define search radius in meters based on distance threshold
        radius = distance_threshold * METERS_PER_NAUTICAL_MILE

        # Query features tagged as 'harbour' or 'port
        tags = {'harbour': True, 'seaport': True, 'port': True}

        try: 
            # Run the query
            gdf = ox.features_from_point((lat, lon), tags=tags, dist=radius)
        except InsufficientResponseError as e:
            logger.debug(f"Error querying ports: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error querying ports: {str(e)}")
            return False

        # Check if any ports are found
        if not gdf.empty:
            logger.info("✅ Port(s) found nearby!")
            return True
        
        return False
