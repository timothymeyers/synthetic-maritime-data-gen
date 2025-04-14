from typing import Dict, List, Optional, Tuple, Union
import json
import requests
import logging
from shapely.geometry import shape, MultiLineString, LineString, Point
from rtree import index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_DATA = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'

class RouteType:
    MAJOR = "Major"
    MIDDLE = "Middle"
    MINOR = "Minor"

class RouteFinder:
    def __init__(self):
        self.major: List[LineString] = []
        self.middle: List[LineString] = []
        self.minor: List[LineString] = []
        self.major_idx: Optional[index.Index] = None
        self.middle_idx: Optional[index.Index] = None
        self.minor_idx: Optional[index.Index] = None

    def load_data(self, url: str = None) -> None:
        """Load shipping route data from a GeoJSON URL."""
        
        if not url:
            url = DEFAULT_DATA
            logger.info(f"No URL provided, using default: {url}")
        
        logger.info(f"Loading route data from {url}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = json.loads(response.content)
            self._process_features(data['features'])
            self._build_indices()
            logger.info("Successfully loaded and processed route data")
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Failed to load route data: {str(e)}")
            raise

    def _process_features(self, features: List[Dict]) -> None:
        """Process GeoJSON features into route lists."""
        for feature in features:
            route_type = feature['properties']['Type']
            routes = []
            geom = shape(feature['geometry'])
            
            if isinstance(geom, MultiLineString):
                routes.extend(list(geom.geoms))
            elif isinstance(geom, LineString):
                routes.append(geom)

            if route_type == RouteType.MAJOR:
                self.major.extend(routes)
            elif route_type == RouteType.MIDDLE:
                self.middle.extend(routes)
            elif route_type == RouteType.MINOR:
                self.minor.extend(routes)

    def _build_indices(self) -> None:
        """Build spatial indices for all route types."""
        def build_spatial_index(routes: List[LineString]) -> index.Index:
            idx = index.Index()
            for i, line in enumerate(routes):
                idx.insert(i, line.bounds, obj=line)
            return idx

        self.major_idx = build_spatial_index(self.major)
        self.middle_idx = build_spatial_index(self.middle)
        self.minor_idx = build_spatial_index(self.minor)

    def find_nearest_route(
        self,
        lon: float,
        lat: float,
        distance_threshold: float = 50,
        num_candidates: int = 10
    ) -> Optional[Dict]:
        """
        Find the nearest shipping route to the given coordinates.

        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            distance_threshold: Maximum distance in nautical miles to consider a route
            num_candidates: Number of nearest candidates to check

        Returns:
            Dictionary containing route information or None if no route found
        """
        # Try routes in order of priority: major, middle, minor
        route_configs = [
            (self.major_idx, self.major, RouteType.MAJOR),
            (self.middle_idx, self.middle, RouteType.MIDDLE),
            (self.minor_idx, self.minor, RouteType.MINOR)
        ]

        best_result = None
        best_distance = float('inf')
        
        for idx, routes, route_type in route_configs:
            result = self._find_single_route(idx, routes, lon, lat, distance_threshold, num_candidates)
            if result:
                # Always take a major route if within threshold
                if route_type == RouteType.MAJOR and result['distance_nm'] <= distance_threshold:
                    result['route_type'] = route_type
                    return result
                # For other routes, only take if closer than current best
                elif result['distance_nm'] < best_distance:
                    result['route_type'] = route_type
                    best_result = result
                    best_distance = result['distance_nm']
                    
        return best_result

    def _find_single_route(
        self,
        idx: index.Index,
        routes: List[LineString],
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
            distance_in_nm = query_point.distance(nearest_point) * 60  # Convert degrees to nautical miles

            if distance_in_nm < min_distance:
                min_distance = distance_in_nm
                closest_route = route
                closest_id = i
                closest_proj_distance = proj_distance
                closest_point = nearest_point

        if min_distance <= distance_threshold:
            return {
                'route_id': closest_id + 1,
                'route': closest_route,
                'proj_distance': closest_proj_distance,
                'nearest_point': closest_point,
                'distance_nm': min_distance
            }

        return None

    @staticmethod
    def get_route_endpoints(route: LineString) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get the start and end coordinates of a route."""
        coords = list(route.coords)
        return coords[0], coords[-1]

    @staticmethod
    def get_next_waypoints(
        route: LineString,
        point: Point,
        heading: float,
        num_waypoints: int
    ) -> List[Point]:
        """
        Get the next waypoints along a route based on current position and heading.

        Args:
            route: A LineString representing the shipping route
            point: Point object representing current position on route
            heading: Current heading in degrees (0-360)
            num_waypoints: Number of next waypoints to return

        Returns:
            List of Point objects representing the next waypoints
        """
        # Project the point onto the route to get the exact location
        proj_distance = route.project(point)
        coords = list(route.coords)
        
        # Find the segment we're currently on
        current_segment_idx = 0
        current_distance = 0
        segment_distances = []
        
        # Calculate cumulative distances along the route
        for i in range(len(coords) - 1):
            segment = LineString([coords[i], coords[i + 1]])
            distance = segment.length
            segment_distances.append(current_distance + distance)
            if current_distance <= proj_distance <= current_distance + distance:
                current_segment_idx = i
            current_distance += distance
            
        # Determine direction based on heading and route orientation
        forward_direction = True
        if current_segment_idx < len(coords) - 1:
            segment_heading = RouteFinder._calculate_heading(
                coords[current_segment_idx],
                coords[current_segment_idx + 1]
            )
            # If the difference between current heading and segment heading is > 90°,
            # we're likely going in the opposite direction
            heading_diff = abs(heading - segment_heading)
            if heading_diff > 90 and heading_diff < 270:
                forward_direction = False
                
        waypoints = []
        if forward_direction:
            # Get next points in forward direction
            for i in range(current_segment_idx + 1, min(len(coords), current_segment_idx + num_waypoints + 1)):
                waypoints.append(Point(coords[i]))
        else:
            # Get next points in reverse direction
            for i in range(current_segment_idx, max(-1, current_segment_idx - num_waypoints), -1):
                waypoints.append(Point(coords[i]))
                
        return waypoints[:num_waypoints]

    @staticmethod
    def _calculate_heading(start_coord: Tuple[float, float], end_coord: Tuple[float, float]) -> float:
        """
        Calculate the heading between two coordinates.
        
        Args:
            start_coord: Starting coordinate (lon, lat)
            end_coord: Ending coordinate (lon, lat)
            
        Returns:
            Heading in degrees (0-360)
        """
        import math
        
        start_lon, start_lat = start_coord
        end_lon, end_lat = end_coord
        
        # Convert to radians
        lat1 = math.radians(start_lat)
        lat2 = math.radians(end_lat)
        diff_lon = math.radians(end_lon - start_lon)
        
        # Calculate heading
        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon))
        bearing = math.atan2(x, y)
        
        # Convert to degrees
        heading = math.degrees(bearing)
        
        # Normalize to 0-360
        return (heading + 360) % 360
