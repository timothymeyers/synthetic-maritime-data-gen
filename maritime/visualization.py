"""Visualization utilities for maritime routes."""

import os
import logging
import folium
from typing import List, Dict, Tuple, Optional
from .interfaces import WaypointInfo

logger = logging.getLogger(__name__)

def create_route_map(waypoint_info: WaypointInfo, filename: str = "route_map.html") -> str:
    """Create an interactive map visualization of the route.
    
    Args:
        waypoint_info: WaypointInfo containing route and waypoint data
        filename: Name of the output HTML file
        
    Returns:
        Path to the generated HTML file
    """
    # Create a map centered on the starting point
    start_lat = waypoint_info.current_position[1]
    start_lon = waypoint_info.current_position[0]
    m = folium.Map(location=[start_lat, start_lon], zoom_start=6)
    
    # Add start marker
    folium.Marker(
        [start_lat, start_lon],
        popup="Start",
        icon=folium.Icon(color='green', icon='info-sign')
    ).add_to(m)
    
    # Add waypoint markers and connect them with lines
    coordinates = [(wp[1], wp[0]) for wp in waypoint_info.waypoints]
    if coordinates:
        # Create route line
        folium.PolyLine(
            coordinates,
            weight=2,
            color='blue',
            opacity=0.8
        ).add_to(m)
        
        # Add waypoint markers
        for i, coord in enumerate(coordinates):
            folium.CircleMarker(
                location=coord,
                radius=3,
                popup=f'Waypoint {i+1}',
                color="#3186cc",
                fill=True
            ).add_to(m)
    
    # Add end marker if different from start
    if waypoint_info.route_end != waypoint_info.current_position:
        end_lat = waypoint_info.route_end[1]
        end_lon = waypoint_info.route_end[0]
        folium.Marker(
            [end_lat, end_lon],
            popup="End" + (" (Port)" if waypoint_info.end_at_port else ""),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
    
    # Save the map
    output_path = os.path.abspath(filename)
    m.save(output_path)
    return output_path

def find_alternative_routes(current_pos: Tuple[float, float], 
                          heading: float,
                          route_finder,
                          max_alternatives: int = 3,
                          search_radius_nm: float = 50.0) -> List[WaypointInfo]:
    """Find alternative routes from the current position.
    
    Args:
        current_pos: Current position (lon, lat)
        heading: Current heading in degrees
        route_finder: Instance of BetterRouteFinder
        max_alternatives: Maximum number of alternative routes to return
        search_radius_nm: Search radius in nautical miles
        
    Returns:
        List of alternative WaypointInfo objects
    """
    # Try different headings around the current heading
    alternatives = []
    heading_offsets = [0, 15, -15, 30, -30, 45, -45]
    
    for offset in heading_offsets:
        new_heading = (heading + offset) % 360
        route = route_finder.find_nearest_route_with_heading(
            current_pos[0], current_pos[1], 
            new_heading, search_radius_nm
        )
        
        if route and len(alternatives) < max_alternatives:
            alternatives.append(route)
            
    return alternatives

def suggest_nearby_ports(current_pos: Tuple[float, float], 
                        port_finder,
                        search_radius_nm: float = 100.0) -> List[Dict]:
    """Find nearby ports when no route is found.
    
    Args:
        current_pos: Current position (lon, lat)
        port_finder: Instance of PortFinder
        search_radius_nm: Search radius in nautical miles
        
    Returns:
        List of nearby ports with distances
    """
    return port_finder.find_nearby_ports(current_pos[0], current_pos[1], search_radius_nm)
