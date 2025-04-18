"""Data loading functionality for maritime routing."""

import json
import logging
import math
from typing import Dict, List, Optional
import requests
from rtree import index
from shapely.geometry import shape, MultiLineString, LineString, Point
from .route_types import RouteType
from .config import DEFAULT_DATA
from .interfaces import RouteInfo

logger = logging.getLogger(__name__)

class RouteDataLoader:
    """Class to load and manage route data."""
    
    def __init__(self):
        """Initialize the route data loader."""
        self.major: List[LineString] = []
        self.middle: List[LineString] = []
        self.minor: List[LineString] = []
        self.major_idx: Optional[index.Index] = None
        self.middle_idx: Optional[index.Index] = None
        self.minor_idx: Optional[index.Index] = None
    
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
        """Build spatial indices for all route types."""
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
        
    def get_route_by_id(self, route_id: int, route_type: str = None) -> Optional[LineString]:
        """Get a route by ID and optionally by type.
        
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
                middle_idx = idx - len(self.major)
                return self.middle[middle_idx]
            elif 0 <= idx - len(self.major) - len(self.middle) < len(self.minor):
                minor_idx = idx - len(self.major) - len(self.middle)
                return self.minor[minor_idx]
                
        return None

    def get_route_endpoints(self, route_id: int, route_type: str = None) -> Optional[Dict[str, List[float]]]:
        """Get the start and end coordinates of a route by ID.
        
        Args:
            route_id: ID of the route (1-based index)
            route_type: Optional route type (MAJOR, MIDDLE, MINOR)
            
        Returns:
            Dictionary with start and end coordinates or None if route not found
        """
        route = self.get_route_by_id(route_id, route_type)
        if route is None:
            return None
            
        coords = list(route.coords)
        return {
            'start': list(coords[0]),
            'end': list(coords[-1])
        }
