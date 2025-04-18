# Standard library imports
import json
import logging
import math
from typing import Dict, List, Optional, Tuple, Union

# Third-party imports
import requests
import searoute as sr
from rtree import index
from shapely.geometry import shape, MultiLineString, LineString, Point
from geopy.distance import geodesic

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_DATA = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'
HEADING_WEIGHT = 0.9  # Weight for heading difference when prioritizing routes
DISTANCE_WEIGHT = 0.1  # Weight for distance when prioritizing routes

class RouteType:
    """Constants for route types."""
    MAJOR = "Major"
    MIDDLE = "Middle"
    MINOR = "Minor"
    
class BetterRouteFinder:
    """Class to find maritime shipping routes."""
    
    def __init__(self):
        """Initialize the route finder with empty data structures."""
        logger.debug("Initializing BetterRouteFinder")
        self.major: List[LineString] = []
        self.middle: List[LineString] = []
        self.minor: List[LineString] = []
        self.major_idx: Optional[index.Index] = None
        self.middle_idx: Optional[index.Index] = None
        self.minor_idx: Optional[index.Index] = None

    # Data loading and processing methods
    
    def load_data(self, url: str = None) -> None:
        """Load shipping route data from a GeoJSON URL.
        
        Args:
            url: URL to the GeoJSON data. If None, uses default URL.
        """
        if not url:
            url = DEFAULT_DATA
            logger.debug(f"No URL provided, using default: {url}")
        
        logger.info(f"Loading route data from {url}")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = json.loads(response.content)
            
            logger.debug(f"Retrieved data with {len(data['features'])} features")
            self._process_features(data['features'])
            self._build_indices()
            
            logger.info(f"Successfully loaded routes: {len(self.major)} major, "
                       f"{len(self.middle)} middle, {len(self.minor)} minor")
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Failed to load route data: {str(e)}")
            raise
    
    def _process_features(self, features: List[Dict]) -> None:
        """Process GeoJSON features into route lists.
        
        Args:
            features: List of GeoJSON features representing shipping routes
        """
        logger.debug(f"Processing {len(features)} features")
        
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
        
        logger.debug(f"Processed routes: {len(self.major)} major, "
                    f"{len(self.middle)} middle, {len(self.minor)} minor")

    def _build_indices(self) -> None:
        """Build spatial indices for all route types to enable efficient spatial queries."""
        logger.debug("Building spatial indices for route types")
        
        def build_spatial_index(routes: List[LineString]) -> index.Index:
            idx = index.Index()
            for i, line in enumerate(routes):
                idx.insert(i, line.bounds, obj=line)
            return idx

        self.major_idx = build_spatial_index(self.major)
        self.middle_idx = build_spatial_index(self.middle)
        self.minor_idx = build_spatial_index(self.minor)
        
        logger.debug("Spatial indices built successfully")
        
    # Route finding methods
    
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
        logger.debug("-" *40)
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
    
    def _find_single_route(
        self,
        idx: index.Index,
        routes: List[LineString],
        lon: float,
        lat: float,
        distance_threshold: float,
        num_candidates: int
    ) -> Optional[Dict]:
        """Find the nearest route of a specific type.
        
        Args:
            idx: Spatial index for the routes
            routes: List of routes to search
            lon: Longitude coordinate
            lat: Latitude coordinate
            distance_threshold: Maximum distance in nautical miles to consider a route
            num_candidates: Number of nearest candidates to check
            
        Returns:
            Dictionary containing route information or None if no route found
        """
        logger.debug(f"Finding single route near ({lon}, {lat}), threshold: {distance_threshold}nm")
        
        query_point = Point(lon, lat)
        candidate_indices = list(idx.nearest((lon, lat, lon, lat), num_candidates))
        
        logger.debug(f"\tFound {len(candidate_indices)} candidate routes to check")

        closest_route = None
        closest_id = None
        min_distance = float('inf')
        closest_proj_distance = None
        closest_point = None

        for i in candidate_indices:
            route = routes[i]
            proj_distance = route.project(query_point)
            nearest_point = route.interpolate(proj_distance)
            # Convert degrees to nautical miles
            distance_in_nm = query_point.distance(nearest_point) * 60  
            
            logger.debug(f"\tRoute {i+1}: distance = {distance_in_nm:.2f}nm")

            if distance_in_nm < min_distance:
                min_distance = distance_in_nm
                closest_route = route
                closest_id = i
                closest_proj_distance = proj_distance
                closest_point = nearest_point

        if min_distance <= distance_threshold:
            logger.debug(f"\t\tFound nearest route: ID {closest_id+1}, distance: {min_distance:.2f}nm")
            return {
                'route_id': closest_id + 1,
                'proj_distance': closest_proj_distance,
                'nearest_point': closest_point,
                'distance_nm': min_distance
            }

        logger.debug(f"\t\tNo route found within threshold of {distance_threshold}nm")
        return None
    
    def get_next_waypoints_with_speed_and_heading_known_destination (
        self,
        lon: float,
        lat: float,
        destination_lon: float,
        destination_lat: float,
        heading: float,
        speed_knot: float,
        time_hrs: float,
        num_waypoints: int
    ):
        """
        """
        logger.debug("-" *40)
        logger.info(f"Finding next waypoints at ({lon}, {lat}) with heading {heading}° going to ({destination_lon}, {destination_lat})")
        
        route = self.find_route_between_points(lon, lat, destination_lon, destination_lat)
        if not route:
            logger.warning("No route found")
            return []
        # Get the waypoints along the route
        waypoints = self.get_waypoints(route, speed_knot, time_hrs, num_waypoints)
        start = route['geometry']['coordinates'][0]
        end = route['geometry']['coordinates'][-1]
        logger.debug(f"Next waypoints: {waypoints}")
        return {
            'current_position': (lon, lat),
            'current_heading': heading,
            'current_speed': speed_knot,
            'waypoints': waypoints,
            'observed_hrs': time_hrs,
            'num_observations': num_waypoints,            
            'route_start': start,
            'route_end': end,     
        }
        
    
    def get_next_waypoints_with_speed_and_heading_unknown_route (
        self,
        lon: float,
        lat: float,
        heading: float,
        speed_knot: float,
        time_hrs: float,
        num_waypoints: int
    ) :
        """Get the next waypoints along a route based on speed and heading.
        
        Args:
            lon: Longitude coordinate
            lat: Latitude coordinate
            heading: Current heading in degrees (0-360)
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Number of waypoints to return
            
        Returns:
            List of tuples containing the next waypoints (lon, lat)
        """
        logger.debug("-" *40)
        logger.info(f"Finding next waypoints at ({lon}, {lat}) with heading {heading}°")
        
        # Initial thresholds
        distance_threshold = 5  # in nautical miles
        heading_threshold = 5  # in degrees
        max_distance_threshold = 100
        max_heading_threshold = 45

        route = None
        current_lon, current_lat = lon, lat

        while not route:
            route = self.find_nearest_route_with_heading(
            current_lon, current_lat, heading, distance_threshold, heading_threshold
            )

            if not route:
            # Move 10 nautical miles along current heading using accurate geodesic calculation
                
                destination_point = geodesic(nautical=10).destination((current_lat, current_lon), heading)
                
                logger.debug(f"\tNo route found - moving to new point: ({destination_point.latitude}, {destination_point.longitude})")
                
                current_lat, current_lon = destination_point.latitude, destination_point.longitude
                # Increase thresholds for next iteration, capped at max values
                distance_threshold = min(distance_threshold + 25, max_distance_threshold)
                heading_threshold = min(heading_threshold + 5, max_heading_threshold)
              
        
        
        # Get the waypoints along the route
        waypoints = self.get_waypoints(route, speed_knot, time_hrs, num_waypoints)
        start = route['geometry']['coordinates'][0]
        end = route['geometry']['coordinates'][-1]
        
        
        logger.debug(f"Next waypoints: {waypoints}")
        return {
            'current_position': (lon, lat),
            'current_heading': heading,
            'current_speed': speed_knot,
            'waypoints': waypoints,
            'observed_hrs': time_hrs,
            'num_observations': num_waypoints,            
            'route_start': start,
            'route_end': end,     
        }
    
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
        logger.debug("-" *40)
        logger.info(f"Finding nearest route at ({lon}, {lat}) with heading {heading}°")
        
        # Get all nearby routes first
        all_routes = []
        route_configs = [
            (self.major_idx, self.major, RouteType.MAJOR),
            (self.middle_idx, self.middle, RouteType.MIDDLE),
            (self.minor_idx, self.minor, RouteType.MINOR)
        ]
        
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

        # Sort routes by a weighted combination of heading difference and distance
        sorted_routes = sorted(
            all_routes,
            key=lambda x: ((x['heading_diff'] * HEADING_WEIGHT + x['distance_nm'] * DISTANCE_WEIGHT) / 2.0)
        )
        
        best_route = sorted_routes[0]
        logger.info(f"Best route found: {best_route['route_type']} ID {best_route['route_id']}, heading diff: {best_route['heading_diff']:.2f}°, distance: {best_route['distance_nm']:.2f}nm")
        
        # Show details of top matches for debugging
        for i, route in enumerate(sorted_routes[:4]):
            if i > 0:  # Skip the best route as it's already logged above
                logger.debug(f"Alternative route {i}: {route['route_type']} ID {route['route_id']}, "
                           f"heading diff: {route['heading_diff']:.2f}°, "
                           f"distance: {route['distance_nm']:.2f}nm")

        logger.debug (f"\n\nBest route: {best_route}\n\n")

        # calculate the route based on the current position and the best_route ending
        route = self.find_route_between_points(
            lon, lat,
            best_route['ending_point'][0],
            best_route['ending_point'][1]
        )
        

        logger.debug(f"Found route: {route}")

        return route
    
    # Utility methods
    
    @staticmethod
    def _calculate_heading(start_coord: Tuple[float, float], end_coord: Tuple[float, float]) -> float:
        """Calculate the heading between two coordinates.
        
        Args:
            start_coord: Starting coordinate (lon, lat)
            end_coord: Ending coordinate (lon, lat)
            
        Returns:
            Heading in degrees (0-360)
        """
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
        
        # Convert to degrees and normalize to 0-360
        heading = math.degrees(bearing)
        normalized_heading = (heading + 360) % 360
        
        return normalized_heading
    
    def _get_next_waypoints_internal(self, 
        route: LineString,
        point: Point,
        heading: float,
        num_waypoints: int
    ) -> List[Point]:
        """Get the next waypoints along a route (internal method returning Shapely Points).

        Args:
            route: A LineString representing the shipping route
            point: Point object representing current position on route
            heading: Current heading in degrees (0-360)
            num_waypoints: Number of next waypoints to return

        Returns:
            List of Point objects representing the next waypoints
        """
        logger.debug(f"Getting next {num_waypoints} waypoints for heading {heading}°")
        
        # Project the point onto the route
        proj_distance = route.project(point)
        coords = list(route.coords)
        
        logger.debug(f"\tRoute has {len(coords)} coordinates")
        
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
            
        logger.debug(f"\tCurrent segment index: {current_segment_idx} of {len(coords)-1}")
        
        # Determine direction based on heading and route orientation
        forward_direction = True
        if current_segment_idx < len(coords) - 1:
            segment_heading = self._calculate_heading(
                coords[current_segment_idx],
                coords[current_segment_idx + 1]
            )
            heading_diff = abs(heading - segment_heading)
            if heading_diff > 90 and heading_diff < 270:
                forward_direction = False
                
        logger.debug(f"\tDirection: {'forward' if forward_direction else 'reverse'}")
        
        waypoints = []
        if forward_direction:
            # Get next points in forward direction
            for i in range(current_segment_idx + 1, min(len(coords), current_segment_idx + num_waypoints + 1)):
                waypoints.append(Point(coords[i]))
        else:
            # Get next points in reverse direction
            for i in range(current_segment_idx, max(-1, current_segment_idx - num_waypoints), -1):
                waypoints.append(Point(coords[i]))
                
        logger.debug(f"Found {len(waypoints)} waypoints")
        return waypoints[:num_waypoints]

    def _get_route_by_id(self, route_id: int, route_type: str = None) -> Optional[LineString]:
        """Get a route by ID and optionally by type.
        
        Args:
            route_id: ID of the route (1-based index)
            route_type: Optional type of route (MAJOR, MIDDLE, MINOR)
            
        Returns:
            The route as a LineString or None if not found
        """
        logger.debug(f"Getting route with ID {route_id}, type {route_type or 'any'}")
        
        # Adjust to 0-based index
        idx = route_id - 1
        
        # If route type is specified, search only that type
        if route_type:
            if route_type == RouteType.MAJOR and 0 <= idx < len(self.major):
                logger.debug(f"Found major route at index {idx}")
                return self.major[idx]
            elif route_type == RouteType.MIDDLE and 0 <= idx < len(self.middle):
                logger.debug(f"Found middle route at index {idx}")
                return self.middle[idx]
            elif route_type == RouteType.MINOR and 0 <= idx < len(self.minor):
                logger.debug(f"Found minor route at index {idx}")
                return self.minor[idx]
        # Otherwise search all types
        else:
            if 0 <= idx < len(self.major):
                logger.debug(f"Found major route at index {idx}")
                return self.major[idx]
            elif 0 <= idx - len(self.major) < len(self.middle):
                middle_idx = idx - len(self.major)
                logger.debug(f"Found middle route at index {middle_idx}")
                return self.middle[middle_idx]
            elif 0 <= idx - len(self.major) - len(self.middle) < len(self.minor):
                minor_idx = idx - len(self.major) - len(self.middle)
                logger.debug(f"Found minor route at index {minor_idx}")
                return self.minor[minor_idx]
                
        logger.warning(f"No route found with ID {route_id}, type {route_type or 'any'}")
        return None
    
    def get_route_endpoints(self, route_id: int, route_type: str = None) -> Dict[str, List[float]]:
        """Get the start and end coordinates of a route by ID.
        
        Args:
            route_id: ID of the route (1-based index)
            route_type: Optional route type (MAJOR, MIDDLE, MINOR)
            
        Returns:
            Dictionary with start and end coordinates {
                'start': [lon, lat],
                'end': [lon, lat]
            } or None if route not found
        """
        logger.debug(f"Getting endpoints for route {route_id}, type {route_type or 'any'}")
        
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            logger.warning(f"\tRoute {route_id} not found, can't get endpoints")
            return None
            
        coords = list(route.coords)
        endpoints = {
            'start': list(coords[0]),
            'end': list(coords[-1])
        }
        
        logger.debug(f"\tRoute endpoints: start={endpoints['start']}, end={endpoints['end']}")
        return endpoints

    def get_waypoints(self, route: json, speed_knot: float, time_hrs: float, num_waypoints: float):
        """Get waypoints along a route based on speed and time.
        
        Args:
            route: Route data in JSON format
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Number of waypoints to return
        """
        logger.debug(f"Getting waypoints for route with speed {speed_knot} knots and time {time_hrs} hours")
        
        # Calculate distance in nautical miles
        distance_nm_total = speed_knot * time_hrs
        logger.debug(f"Distance to cover: {distance_nm_total}nm")
        
        distance_per_waypoint = distance_nm_total / num_waypoints
        logger.debug(f"Distance per waypoint: {distance_per_waypoint}nm")
        remaining_distance = distance_per_waypoint
        
        # Get the coordinates of the route
        coords = list(route['geometry']['coordinates'])
        
        waypoints = []
        
        current_coord = coords[0]
        
        idx = 1
        
        for i in range(1, len(coords)):           
            segment = LineString([current_coord, coords[idx]])
            segment_length_nm = segment.length * 53.4  # Convert degrees to nautical miles
            logger.debug(f"\tChecking segment from {current_coord} to {coords[idx]}: distance {segment_length_nm}nm and remaining distance: {remaining_distance}nm")
            
            if segment_length_nm < remaining_distance:
                logger.debug(f"\t\tSegment length is less than remaining distance.")
                #waypoints.append(coords[i])
                
                remaining_distance -= segment_length_nm
                current_coord = coords[idx]
                idx += 1
            else:
                logger.debug(f"\t\tSegment length is greater than remaining distance. Calculating bisected point")
                x, y = self._get_bisected_point(current_coord[0], current_coord[1], coords[idx][0], coords[idx][1], remaining_distance)
                logger.debug(f"\t\tAdding Bisected point as waypoint: ({x}, {y})")
                waypoints.append((x, y))
                current_coord = [x, y]
                remaining_distance = distance_per_waypoint
            
            if len(waypoints) >= num_waypoints:
                logger.debug(f"\tReached maximum number of waypoints: {num_waypoints}")
                break
                
            
                
                
                
                
            
        
            
        
        logger.debug(f"Waypoints: {waypoints}")
        return waypoints
        
    def _get_bisected_point(self, x: float, y: float, x2: float, y2: float, distance_nm:float):
        """Get a point that is bisected between two coordinates exactly distance_nm nautical miles away from the first point.
        This is useful for finding a point along a route that is a specific distance away from the starting point.
        
        Args:
            x: Longitude of the first point
            y: Latitude of the first point
            x2: Longitude of the second point
            y2: Latitude of the second point
            distance_nm: Distance in nautical miles to bisect
            
        Returns:
            Tuple of (longitude, latitude) of the bisected point
        """
        logger.debug(f"Getting bisected point between ({x}, {y}) and ({x2}, {y2}) at distance {distance_nm}nm")
        
        # Create shapely points
        point1 = Point(x, y)
        point2 = Point(x2, y2)
        
        # Create a linestring between the points
        line = LineString([point1, point2])
        
        # Calculate the fraction along the line
        total_distance_deg = point1.distance(point2)
        total_distance_nm = total_distance_deg * 60  # Convert degrees to nm
        
        # Calculate the fraction of the line where our point should be
        fraction = distance_nm / total_distance_nm
        
        # Interpolate the point along the line
        bisected_point = line.interpolate(fraction, normalized=True)
        
        logger.debug(f"\tBisected point: ({bisected_point.x}, {bisected_point.y})")
        return bisected_point.x, bisected_point.y