"""Type definitions and interfaces for maritime routing."""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class RouteInfo:
    """Information about a found route."""
    route_id: int
    route_type: str
    distance_nm: float
    heading_diff: Optional[float] = None
    route_heading: Optional[float] = None
    starting_point: Optional[Tuple[float, float]] = None
    ending_point: Optional[Tuple[float, float]] = None

@dataclass
class WaypointInfo:
    """Information about calculated waypoints."""
    current_position: Tuple[float, float]
    current_heading: float
    current_speed: float
    waypoints: List[Tuple[float, float]]
    observed_hrs: float
    num_observations: int
    route_start: Tuple[float, float]
    route_end: Tuple[float, float]
    end_at_port: bool = False
