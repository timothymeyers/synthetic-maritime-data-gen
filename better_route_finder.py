# Standard library imports
import logging
from typing import Dict, List, Optional

# Third-party imports
from geopy.distance import geodesic

# Maritime package imports
from maritime import (
    RouteDataLoader, PortFinder, WaypointCalculator, 
    RouteFinder, calculate_heading, WaypointInfo
)

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
    
class BetterRouteFinder:
    """Class to find maritime shipping routes.
    
    This class acts as a facade for the maritime routing system, coordinating between
    specialized modules for route finding, port detection, and waypoint calculation.
    """
    
    def __init__(self):
        """Initialize the route finder."""
        logger.debug("Initializing BetterRouteFinder")
        self.data_loader = RouteDataLoader()
        self.port_finder = PortFinder()
        self.waypoint_calculator = WaypointCalculator()
        self.route_finder = RouteFinder(self.data_loader)

    def load_data(self, url: str = None) -> None:
        """Load shipping route data from a GeoJSON URL.
        
        Args:
            url: URL to the GeoJSON data. If None, uses default URL.
        """
        self.data_loader.load_data(url)
    
    def find_route_between_points(self, origin_lon: float, origin_lat: float, 
                                 dest_lon: float, dest_lat: float) -> Dict:
        """Find the nearest route between two geographical points.
        
        Args:
            origin_lon: Origin longitude
            origin_lat: Origin latitude
            dest_lon: Destination longitude
            dest_lat: Destination latitude
            
        Returns:
            Dict containing the route information
        """
        return self.route_finder.find_route_between_points(origin_lon, origin_lat, dest_lon, dest_lat)
    
    def is_near_port(self, lon: float, lat: float, distance_threshold: float = 5.0) -> bool:
        """Check if a point is near a port within a specified distance.
        
        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            distance_threshold: Distance in nautical miles to consider as "near"
            
        Returns:
            True if the point is near a port, False otherwise
        """
        return self.port_finder.is_near_port(lon, lat, distance_threshold)
    

    
    def get_next_waypoints_with_speed_and_heading_known_destination(
        self,
        lon: float,
        lat: float,
        destination_lon: float,
        destination_lat: float,
        heading: float,
        speed_knot: float,
        time_hrs: float,
        num_waypoints: int = None
    ) -> WaypointInfo:
        """Get the next waypoints when destination is known.
        
        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            destination_lon: Destination longitude
            destination_lat: Destination latitude
            heading: Current heading in degrees (0-360)
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Optional number of waypoints to return
            
        Returns:
            WaypointInfo containing route and waypoint information
        """
        route = self.route_finder.find_route_between_points(lon, lat, destination_lon, destination_lat)
        if not route:
            logger.warning("No route found")
            return WaypointInfo(
                current_position=(lon, lat),
                current_heading=heading,
                current_speed=speed_knot,
                waypoints=[],
                observed_hrs=time_hrs,
                num_observations=0,
                route_start=(lon, lat),
                route_end=(lon, lat),
                end_at_port=False
            )
            
        # Get waypoints using calculator
        waypoints = self.waypoint_calculator.get_waypoints(route, speed_knot, time_hrs, num_waypoints)
        start = route['geometry']['coordinates'][0]
        end = route['geometry']['coordinates'][-1]
        end_at_port = self.port_finder.is_near_port(end[0], end[1], 25)
        
        return WaypointInfo(
            current_position=(lon, lat),
            current_heading=heading,
            current_speed=speed_knot,
            waypoints=waypoints,
            observed_hrs=time_hrs,
            num_observations=len(waypoints),
            route_start=start,
            route_end=end,
            end_at_port=end_at_port
        )
     
    def get_next_waypoints_with_speed_and_heading_unknown_route_improved(
        self,
        lon: float,
        lat: float,
        heading: float,
        speed_knot: float,
        time_hrs: float,
        num_waypoints: int = None
    ) -> List[WaypointInfo]:
        """Find a chain of routes that lead to a port.
        
        Many shipping lanes do not end at a port, so this method chains multiple routes together.
        For example, MAJ ROUTE 12 stops off the coast of California and connects to MAJ ROUTE 30,
        which then goes past the Port of LA to the Port of San Diego.

        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            heading: Current heading in degrees (0-360)
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Optional number of waypoints to return
            
        Returns:
            List of WaypointInfo objects, each containing route and waypoint information
        """    
        at_port = False
        routes = []
        current_lon, current_lat = lon, lat
        current_heading = heading
        
        while not at_port:
            route_info = self.get_next_waypoints_with_speed_and_heading_unknown_route(
                current_lon, current_lat, current_heading, speed_knot, time_hrs, num_waypoints
            )
            
            if route_info is None:
                logger.warning("No route found")
                return routes if routes else []
            
            routes.append(route_info)
            
            # Check if the route ends at a port
            at_port = route_info.end_at_port
            current_lon, current_lat = route_info.route_end
            
            # Calculate heading between last waypoint and route end
            if route_info.waypoints:
                current_heading = calculate_heading(
                    route_info.waypoints[-1],
                    route_info.route_end
                )
            else:
                break  # No waypoints found, stop searching
                
        return routes
            
            
            
        
    
    def get_next_waypoints_with_speed_and_heading_unknown_route(
        self,
        lon: float,
        lat: float,
        heading: float,
        speed_knot: float,
        time_hrs: float,
        num_waypoints: int = None
    ) -> WaypointInfo:
        """Get the next waypoints along a route based on speed and heading.
        
        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            heading: Current heading in degrees (0-360)
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Number of waypoints to return
            
        Returns:
            WaypointInfo containing route and waypoint information
        """
        # Initial thresholds
        distance_threshold = 5  # in nautical miles
        heading_threshold = 5  # in degrees
        max_distance_threshold = 100
        max_heading_threshold = 45

        route = None
        current_lon, current_lat = lon, lat

        while not route:
            route = self.route_finder.find_nearest_route_with_heading(
                current_lon, current_lat, heading, distance_threshold, heading_threshold
            )

            if not route:
                # Move 10 nautical miles along current heading
                destination_point = geodesic(nautical=10).destination(
                    (current_lat, current_lon), heading
                )
                current_lat, current_lon = destination_point.latitude, destination_point.longitude
                
                # Increase thresholds for next iteration
                distance_threshold = min(distance_threshold + 25, max_distance_threshold)
                heading_threshold = min(heading_threshold + 5, max_heading_threshold)
              
        # Get the waypoints along the route
        waypoints = self.waypoint_calculator.get_waypoints(route, speed_knot, time_hrs, num_waypoints)
        start = route['geometry']['coordinates'][0]
        end = route['geometry']['coordinates'][-1]
        
        end_at_port = self.port_finder.is_near_port(end[0], end[1], 25)
        
        return WaypointInfo(
            current_position=(lon, lat),
            current_heading=heading,
            current_speed=speed_knot,
            waypoints=waypoints,
            observed_hrs=time_hrs,
            num_observations=len(waypoints),
            route_start=start,
            route_end=end,
            end_at_port=end_at_port
        )
    
    def find_nearest_route_with_heading(
        self,
        lon: float,
        lat: float,
        heading: float,
        distance_threshold: float = 50.0,
        heading_threshold: float = 30.0,
        num_candidates: int = 10
    ) -> Optional[Dict]:
        """Find the nearest shipping route that aligns with the provided heading.

        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            heading: Current heading in degrees (0-360)
            distance_threshold: Maximum distance in nautical miles to consider
            heading_threshold: Maximum allowed difference in degrees between route and heading
            num_candidates: Number of nearest candidates to check

        Returns:
            Dictionary containing route information or None if no route found
        """
        return self.route_finder.find_nearest_route_with_heading(
            lon, lat, heading, distance_threshold, heading_threshold, num_candidates
        )
    

        
