"""Input preprocessing utilities for maritime navigation."""

import re
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParsedCoordinate:
    """Represents a parsed coordinate with validation status."""
    longitude: float
    latitude: float
    is_valid: bool
    error_message: Optional[str] = None

def parse_coordinates(coord_input: str) -> ParsedCoordinate:
    """Parse coordinates in various formats into decimal degrees.
    
    Supports formats:
    - Decimal degrees: [lon, lat] or (lon, lat)
    - DMS: 40°26'46"N 79°58'56"W
    - Decimal degrees with cardinal directions: 40.446° N 79.982° W
    """
    try:
        # Clean the input
        coord_input = coord_input.strip().replace('[', '').replace(']', '')
        
        # Try parsing as decimal pair [lon, lat] or (lon, lat)
        if ',' in coord_input:
            lon, lat = map(float, coord_input.split(','))
            return validate_coordinates(lon, lat)
            
        # Try parsing DMS format
        dms_pattern = r'(\d+)°(\d+)\'(\d+)"([NS])\s*(\d+)°(\d+)\'(\d+)"([EW])'
        dms_match = re.match(dms_pattern, coord_input)
        if dms_match:
            lat_d, lat_m, lat_s, lat_dir, lon_d, lon_m, lon_s, lon_dir = dms_match.groups()
            lat = (int(lat_d) + int(lat_m)/60 + int(lat_s)/3600) * (1 if lat_dir == 'N' else -1)
            lon = (int(lon_d) + int(lon_m)/60 + int(lon_s)/3600) * (1 if lon_dir == 'E' else -1)
            return validate_coordinates(lon, lat)
            
        # Try parsing decimal degrees with cardinal directions
        dd_pattern = r'(\d+\.?\d*°?\s*[NS])\s*(\d+\.?\d*°?\s*[EW])'
        dd_match = re.match(dd_pattern, coord_input)
        if dd_match:
            lat_str, lon_str = dd_match.groups()
            lat = float(re.search(r'(\d+\.?\d*)', lat_str).group()) * (-1 if 'S' in lat_str else 1)
            lon = float(re.search(r'(\d+\.?\d*)', lon_str).group()) * (-1 if 'W' in lon_str else 1)
            return validate_coordinates(lon, lat)
            
        return ParsedCoordinate(0, 0, False, "Invalid coordinate format")
        
    except Exception as e:
        return ParsedCoordinate(0, 0, False, f"Error parsing coordinates: {str(e)}")

def validate_coordinates(lon: float, lat: float) -> ParsedCoordinate:
    """Validate that coordinates are within valid ranges."""
    if not (-180 <= lon <= 180):
        return ParsedCoordinate(lon, lat, False, "Longitude must be between -180 and 180")
    if not (-90 <= lat <= 90):
        return ParsedCoordinate(lon, lat, False, "Latitude must be between -90 and 90")
    return ParsedCoordinate(lon, lat, True)

def convert_speed(speed: float, from_unit: str, to_unit: str = 'knots') -> float:
    """Convert speed between different units.
    
    Supported units: knots, km/h, mph
    """
    # Convert to knots first
    if from_unit == 'km/h':
        knots = speed * 0.539957
    elif from_unit == 'mph':
        knots = speed * 0.868976
    else:  # assume knots
        knots = speed
        
    # Convert from knots to target unit
    if to_unit == 'km/h':
        return knots * 1.852
    elif to_unit == 'mph':
        return knots * 1.15078
    return knots  # return in knots by default
