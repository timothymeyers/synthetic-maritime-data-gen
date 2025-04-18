"""Route finding functionality for maritime routing."""

import logging
import math
from typing import Dict, List, Optional, Tuple
from shapely.geometry import Point, LineString
from rtree import index
import searoute as sr
from geopy.distance import geodesic

from .interfaces import RouteInfo, WaypointInfo

from .config import HEADING_WEIGHT, DISTANCE_WEIGHT
from .route_types import RouteType
from .geo_utils import calculate_heading

logger = logging.getLogger(__name__)

class RouteFinder:
    """Class to handle route finding functionality."""

    def __init__(self, data_loader):
        """Initialize route finder with data loader."""
        self.data_loader = data_loader

    def find_route_between_points(self, origin_lon: float, origin_lat: float, 
                              dest_lon: float, dest_lat: float) -> Dict:
        """Find the nearest route between two geographical points."""
        logger.debug(f"Finding route between ({origin_lon}, {origin_lat}) and ({dest_lon}, {dest_lat})")
        
        origin = [origin_lon, origin_lat]
        destination = [dest_lon, dest_lat]
        
        try:
            route_result = sr.searoute(origin, destination, include_ports=False, append_orig_dest=True)
            logger.debug(f"Route found with {len(route_result['geometry']['coordinates'])} points")
            return route_result
        except Exception as e:
            logger.error(f"Error finding route: {str(e)}")
            raise

    def find_nearest_route_with_heading(
        self,
        lon: float,
        lat: float,
        heading: float,
        distance_threshold: float = 50.0,
        heading_threshold: float = 30.0,
        num_candidates: int = 10
    ) -> Optional[Dict]:
        """Find the nearest shipping route that aligns with the provided heading."""
        logger.debug(f"Finding nearest route at ({lon}, {lat}) with heading {heading}°")
        
        # Get all nearby routes first
        all_routes = []
        route_configs = [
            (self.data_loader.major_idx, self.data_loader.major, RouteType.MAJOR),
            (self.data_loader.middle_idx, self.data_loader.middle, RouteType.MIDDLE),
            (self.data_loader.minor_idx, self.data_loader.minor, RouteType.MINOR)
        ]
        
        for idx, routes, route_type in route_configs:
            if idx is None:
                continue
            result = self._find_single_route(idx, routes, lon, lat, distance_threshold, num_candidates)
            if result:
                result['route_type'] = route_type
                route_id = result['route_id']
                route = self.data_loader.get_route_by_id(route_id, route_type)
                nearest_point = result['nearest_point']
                if hasattr(nearest_point, 'x') and hasattr(nearest_point, 'y'):
                    nearest_point_coords = [nearest_point.x, nearest_point.y]
                else:
                    nearest_point_coords = list(nearest_point)
                result['nearest_point'] = nearest_point_coords
                
                # Get the route heading
                proj_point = Point(nearest_point_coords[0], nearest_point_coords[1])
                next_points = self._get_next_points(route, proj_point, heading, 1)
                
                if next_points:
                    route_heading = calculate_heading(
                        (proj_point.x, proj_point.y),
                        (next_points[0].x, next_points[0].y)
                    )
                    heading_diff = abs(heading - route_heading)
                    heading_diff = min(heading_diff, 360 - heading_diff)
                    result['heading_diff'] = heading_diff
                    result['route_heading'] = route_heading
                    
                    # Get endpoints and determine direction
                    endpoints = self.data_loader.get_route_endpoints(route_id, route_type)
                    if heading_diff <= heading_threshold:
                        result['starting_point'] = endpoints['end']
                        result['ending_point'] = endpoints['start']
                    else:
                        result['starting_point'] = endpoints['start']
                        result['ending_point'] = endpoints['end']
                        
                    if heading_diff <= heading_threshold:
                        all_routes.append(result)

        if not all_routes:
            return None

        # Sort routes by weighted combination of heading difference and distance
        sorted_routes = sorted(
            all_routes,
            key=lambda x: ((x['heading_diff'] * HEADING_WEIGHT + x['distance_nm'] * DISTANCE_WEIGHT) / 2.0)
        )
        
        best_route = sorted_routes[0]
        
        # Calculate the route based on current position and best route ending
        return self.find_route_between_points(
            lon, lat,
            best_route['ending_point'][0],
            best_route['ending_point'][1]
        )

    def _find_single_route(
        self,
        idx: index.Index,
        routes: List,
        lon: float,
        lat: float,
        distance_threshold: float,
        num_candidates: int
    ) -> Optional[Dict]:
        """Find the nearest route of a specific type."""
        query_point = Point(lon, lat)
        candidate_indices = list(idx.nearest((lon, lat, lon, lat), num_candidates))
        
        closest_route = None
        closest_id = None
        min_distance = float('inf')
        closest_proj_distance = None
        closest_point = None

        for i in candidate_indices:
            route = routes[i]
            proj_distance = route.project(query_point)
            nearest_point = route.interpolate(proj_distance)
            distance_in_nm = query_point.distance(nearest_point) * 60
            
            if distance_in_nm < min_distance:
                min_distance = distance_in_nm
                closest_route = route
                closest_id = i
                closest_proj_distance = proj_distance
                closest_point = nearest_point

        if min_distance <= distance_threshold:
            return {
                'route_id': closest_id + 1,
                'proj_distance': closest_proj_distance,
                'nearest_point': closest_point,
                'distance_nm': min_distance
            }

        return None

    def _get_next_points(self, route, point: Point, heading: float, num_points: int) -> List[Point]:
        """Get the next points along a route."""
        from .waypoint_calculator import WaypointCalculator
        return WaypointCalculator.get_next_waypoints_internal(route, point, heading, num_points)
