from typing import Dict, List, Optional, Tuple, Union
import json
import requests
import logging
from shapely.geometry import shape, MultiLineString, LineString, Point
from rtree import index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_DATA = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'

HEADING_WEIGHT=0.9
DISTANCE_WEIGHT=0.1


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
        num_candidates: int = 10,
        all_routes: bool = False
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
            
            if result and result['distance_nm'] < best_distance:
                result['route_type'] = route_type
                best_result = result
                best_distance = result['distance_nm']
            
            if not all_routes and best_result: 
                return best_result    
            """
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
            """
                    
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
                'proj_distance': closest_proj_distance,
                'nearest_point': closest_point,
                'distance_nm': min_distance
            }

        return None
    
    def _get_route_by_id(self, route_id: int, route_type: str = None) -> Optional[LineString]:
        """
        Get a route by ID and optionally by type.
        
        Args:
            route_id: ID of the route (1-based index)
            route_type: Optional type of route (MAJOR, MIDDLE, MINOR)
            
        Returns:
            The route as a LineString or None if not found
        """
        # Adjust to 0-based index
        idx = route_id - 1
        
        # If route type is specified, search only that type
        if route_type:
            if route_type == RouteType.MAJOR and 0 <= idx < len(self.major):
                return self.major[idx]
            elif route_type == RouteType.MIDDLE and 0 <= idx < len(self.middle):
                return self.middle[idx]
            elif route_type == RouteType.MINOR and 0 <= idx < len(self.minor):
                return self.minor[idx]
        # Otherwise search all types
        else:
            if 0 <= idx < len(self.major):
                return self.major[idx]
            elif 0 <= idx - len(self.major) < len(self.middle):
                return self.middle[idx - len(self.major)]
            elif 0 <= idx - len(self.major) - len(self.middle) < len(self.minor):
                return self.minor[idx - len(self.major) - len(self.middle)]
                
        return None
    
    def get_route_endpoints(self, route_id: int, route_type: str = None) -> Dict[str, List[float]]:
        """
        Get the start and end coordinates of a route by ID.
        
        Args:
            route_id: ID of the route (1-based index)
            route_type: Optional route type (MAJOR, MIDDLE, MINOR). If None, will search all types.
            
        Returns:
            Dictionary with start and end coordinates {
                'start': [lon, lat],
                'end': [lon, lat]
            }
        """
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            return None
            
        coords = list(route.coords)
        return {
            'start': list(coords[0]),
            'end': list(coords[-1])
        }

    
    def get_next_waypoints(self, 
        route_id: int,
        lon: float,
        lat: float,
        heading: float,
        num_waypoints: int = 5,
        route_type: str = None
    ) -> List[List[float]]:
        """
        Get the next waypoints along a route based on current position and heading.

        Args:
            route_id: ID of the route (1-based index)
            lon: Longitude coordinate of current position
            lat: Latitude coordinate of current position
            heading: Current heading in degrees (0-360)
            num_waypoints: Number of next waypoints to return (default: 5)
            route_type: Optional route type (MAJOR, MIDDLE, MINOR)

        Returns:
            List of waypoints as [lon, lat] coordinates
        """
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            return []
            
        point = Point(lon, lat)
        
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
                waypoints.append(list(coords[i]))
        else:
            # Get next points in reverse direction
            for i in range(current_segment_idx, max(-1, current_segment_idx - num_waypoints), -1):
                waypoints.append(list(coords[i]))
                
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
    
    def find_nearest_route_with_heading(
        self,
        lon: float,
        lat: float,
        heading: float,
        distance_threshold: float = 5,
        heading_threshold: float = 5,
        num_candidates: int = 10
    ) -> Optional[Dict]:
        """
        Find the nearest shipping route to the given coordinates that aligns with the provided heading.

        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            heading: Current heading in degrees (0-360)
            distance_threshold: Maximum distance in nautical miles to consider a route
            heading_threshold: Maximum allowed difference in degrees between route direction and heading
            num_candidates: Number of nearest candidates to check

        Returns:
            Dictionary containing route information or None if no route found
        """
        # Get all nearby routes first
        all_routes = []
        route_configs = [
            (self.major_idx, self.major, RouteType.MAJOR),
            (self.middle_idx, self.middle, RouteType.MIDDLE),
            (self.minor_idx, self.minor, RouteType.MINOR)
        ]

        query_point = Point(lon, lat)
        for idx, routes, route_type in route_configs:
            result = self._find_single_route(idx, routes, lon, lat, distance_threshold, num_candidates)
            if result:
                result['route_type'] = route_type
                route_id = result['route_id']
                route = self._get_route_by_id(route_id, route_type)
                # Convert nearest_point to [lon, lat] list if it's a Point
                nearest_point = result['nearest_point']
                if hasattr(nearest_point, 'x') and hasattr(nearest_point, 'y'):
                    nearest_point_coords = [nearest_point.x, nearest_point.y]
                else:
                    nearest_point_coords = list(nearest_point)
                result['nearest_point'] = nearest_point_coords
                proj_point = Point(nearest_point_coords[0], nearest_point_coords[1])
                shapely_waypoints = self._get_next_waypoints_internal(route, proj_point, heading, 1)
                if shapely_waypoints:
                    route_heading = self._calculate_heading(
                        (proj_point.x, proj_point.y),
                        (shapely_waypoints[0].x, shapely_waypoints[0].y)
                    )
                    heading_diff = abs(heading - route_heading)
                    heading_diff = min(heading_diff, 360 - heading_diff)
                    result['heading_diff'] = heading_diff
                    result['route_heading'] = route_heading
                    endpoints = self.get_route_endpoints(route_id, route_type)
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

        priority_map = {RouteType.MAJOR: 0, RouteType.MIDDLE: 1, RouteType.MINOR: 2}
        
        sorted_routes = sorted(
            all_routes,
            key=lambda x: ( (x['heading_diff'] * HEADING_WEIGHT + x['distance_nm'] * DISTANCE_WEIGHT) / 2.0 )
        )
        
        logger.info(f"\n\nSorted routes: {sorted_routes[:4]}\n\n")

        return sorted_routes[0]
    
    def _get_next_waypoints_internal(self, 
        route: LineString,
        point: Point,
        heading: float,
        num_waypoints: int
    ) -> List[Point]:
        """
        Internal method to get the next waypoints along a route (returns Shapely objects for internal use).

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
