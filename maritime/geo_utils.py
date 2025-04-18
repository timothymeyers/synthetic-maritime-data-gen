"""Geographic utility functions for maritime routing."""

import math
from typing import Tuple
from shapely.geometry import Point, LineString, MultiLineString

def calculate_heading(start_coord: Tuple[float, float], end_coord: Tuple[float, float]) -> float:
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

def get_bisected_point(x: float, y: float, x2: float, y2: float, distance_nm: float) -> Tuple[float, float]:
    """Get a point that is bisected between two coordinates at a specific distance.
    
    Args:
        x: Longitude of the first point
        y: Latitude of the first point
        x2: Longitude of the second point
        y2: Latitude of the second point
        distance_nm: Distance in nautical miles to bisect
        
    Returns:
        Tuple of (longitude, latitude) of the bisected point
    """
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
    
    return bisected_point.x, bisected_point.y
