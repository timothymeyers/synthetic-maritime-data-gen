"""Waypoint calculation functionality for maritime routing."""

import logging
import math
from typing import List, Dict, Tuple, Optional
from shapely.geometry import Point, LineString, MultiLineString
from .geo_utils import get_bisected_point, calculate_heading
from .interfaces import WaypointInfo
from .config import METERS_PER_NAUTICAL_MILE

logger = logging.getLogger(__name__)

class WaypointCalculator:
    """Class to handle waypoint calculations along routes."""
    
    @staticmethod
    def get_waypoints(route: Dict, speed_knot: float, time_hrs: float, num_waypoints: int = None) -> List[Tuple[float, float]]:
        """Get waypoints along a route based on speed and time.
        
        Args:
            route: Route data in JSON format
            speed_knot: Speed in knots
            time_hrs: Time in hours
            num_waypoints: Number of waypoints to return
            
        Returns:
            List of waypoint coordinates (lon, lat)
        """
        logger.debug(f"Getting waypoints for route with speed {speed_knot} knots and time {time_hrs} hours")
        
        # Calculate distance in nautical miles
        distance_nm_total = speed_knot * time_hrs * num_waypoints
        logger.debug(f"Total distance to cover: {distance_nm_total}nm")
        
        distance_per_waypoint = speed_knot * time_hrs
        logger.debug(f"Distance per waypoint: {distance_per_waypoint}nm")
        remaining_distance = distance_per_waypoint
        
        # Get the coordinates of the route
        coords = list(route['geometry']['coordinates'])
        waypoints = []
        current_coord = coords[0]
        idx = 1
        
        while current_coord != coords[-1]:
            if idx >= len(coords):
                logger.debug("Reached the end of coordinates.")
                break

            segment = LineString([current_coord, coords[idx]])
            segment_length_nm = segment.length * 60  # Convert degrees to nautical miles
            
            if segment_length_nm < remaining_distance:
                remaining_distance -= segment_length_nm
                current_coord = coords[idx]
                idx += 1
                distance_nm_total -= segment_length_nm
            else:
                x, y = get_bisected_point(
                    current_coord[0], current_coord[1],
                    coords[idx][0], coords[idx][1],
                    remaining_distance
                )
                waypoints.append((x, y))
                current_coord = [x, y]
                distance_nm_total -= remaining_distance
                remaining_distance = distance_per_waypoint
            
        return waypoints

    @staticmethod
    def get_next_waypoints_internal(
        route: LineString,
        point: Point,
        heading: float,
        num_waypoints: int
    ) -> List[Point]:
        """Get the next waypoints along a route (internal method).
        
        Args:
            route: A LineString representing the shipping route
            point: Point object representing current position on route
            heading: Current heading in degrees (0-360)
            num_waypoints: Number of next waypoints to return
            
        Returns:
            List of Point objects representing the next waypoints
        """
        # Project the point onto the route
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
            from .geo_utils import calculate_heading
            segment_heading = calculate_heading(
                coords[current_segment_idx],
                coords[current_segment_idx + 1]
            )
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
