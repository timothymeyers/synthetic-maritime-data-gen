import json, requests, os
import logging
from shapely.geometry import shape, MultiLineString, LineString, Point
from rtree import index
from io import BytesIO
import geopandas as gpd

# Load the existing data
# URL of the GeoJSON file
url = 'https://github.com/newzealandpaul/Shipping-Lanes/blob/main/data/Shipping_Lanes_v1.geojson?raw=true'

# Fetch the GeoJSON file
response = requests.get(url)
response.raise_for_status()  # Ensure the request was successful

data = json.loads(response.content)

# Convert features to Shapely LineString objects
major = []
middle = []
minor = []

for feature in data['features']:
    route_type = feature['properties']['Type']
    routes = [] 
    geom = shape(feature['geometry'])
    if isinstance(geom, MultiLineString):
        for line in geom.geoms:
            routes.append(line)
    
    if route_type == 'Major':
        major = routes
    elif route_type == 'Middle':
        middle = routes
    elif route_type == 'Minor':
        minor = routes

# Build spatial indices
def build_spatial_index(routes):
    idx = index.Index()
    for i, line in enumerate(routes):
        idx.insert(i, line.bounds, obj=line)
    return idx

major_idx = build_spatial_index(major)
middle_idx = build_spatial_index(middle)
minor_idx = build_spatial_index(minor)

# Improved version of find_candidate_route
def find_nearest_route(idx, routes, lon, lat, distance_threshold=50, num_candidates=10):
    """
    Find the closest route to a given point.
    
    Parameters:
    - idx: Spatial index for route lookup
    - routes: List of route geometries
    - lon, lat: Coordinates of the query point
    - distance_threshold: Maximum distance (in nautical miles) to consider a route
    - num_candidates: Number of nearest candidates to check
    
    Returns:
    - route_id: Index of the route (1-based)
    - route: The route geometry
    - proj_distance: Position along the route (projection distance)
    - nearest_point: The closest point on the route to the query point
    - distance_nm: Distance to the route in nautical miles
    """
    query_point = Point(lon, lat)
    
    # Find the nearest candidates
    candidate_indices = list(idx.nearest((lon, lat, lon, lat), num_candidates))
    
    closest_route = None
    closest_id = None
    min_distance = float('inf')
    closest_proj_distance = None
    closest_point = None
    
    # Check all candidates and find the closest one
    for i in candidate_indices:
        route = routes[i]
        # Find the closest point on the route
        proj_distance = route.project(query_point)
        nearest_point = route.interpolate(proj_distance)
        
        # Calculate distance in degrees
        distance_in_degrees = query_point.distance(nearest_point)
        
        # Convert to nautical miles (1 degree ≈ 60 nautical miles)
        distance_in_nm = distance_in_degrees * 60
        
        # Keep track of the closest route
        if distance_in_nm < min_distance:
            min_distance = distance_in_nm
            closest_route = route
            closest_id = i
            closest_proj_distance = proj_distance
            closest_point = nearest_point
    
    # If the closest route is within threshold, return it
    if min_distance <= distance_threshold:
        return {
            'route_id': closest_id + 1,
            'route': closest_route,
            'proj_distance': closest_proj_distance,
            'nearest_point': closest_point,
            'distance_nm': min_distance
        }
    
    return None

# Test with different coordinate sets
def find_nearest_route_all(lon, lat, distance_threshold=50):
    """
    Test the route finder with specific coordinates
    
    Parameters:
    - lon, lat: Coordinates to test
    - distance_threshold: Maximum distance in nautical miles
    
    Returns:
    - A dictionary containing route information or None if no route found
    """
    print(f"\nTesting route finder with coordinates: ({lon}, {lat})")
    print(f"Distance threshold: {distance_threshold} nautical miles")
    
    # Try major routes first
    result = find_nearest_route(major_idx, major, lon, lat, distance_threshold=distance_threshold)
    route_type = "major"
    
    # If no major route found, try middle routes
    if not result:
        print("No major route found, trying middle routes...")
        result = find_nearest_route(middle_idx, middle, lon, lat, distance_threshold=distance_threshold)
        route_type = "middle"
    
    # If no middle route found, try minor routes
    if not result:
        print("No middle route found, trying minor routes...")
        result = find_nearest_route(minor_idx, minor, lon, lat, distance_threshold=distance_threshold)
        route_type = "minor"
    
    if result:
        print(f"✅ Found {route_type} route {result['route_id']} with distance {result['distance_nm']:.2f} nautical miles")
        print(f"Position along route: {result['proj_distance']:.2f}")
        
        # Print additional debugging info
        routes_list = major if route_type == "major" else (middle if route_type == "middle" else minor)
        print(f"Total {route_type} routes available: {len(routes_list)}")
        print(f"Route coordinates sample: {list(routes_list[result['route_id']-1].coords)[:3]}")
        
        # Add route type to result
        result['route_type'] = route_type
        return result
    else:
        print("❌ No route found within the distance threshold in any route category.")
        return None

def get_route_start_end(route):
    """
    Get the start and end coordinates of a route.
    
    Parameters:
    - route: The route geometry
    
    Returns:
    - A tuple containing the start and end coordinates
    """
    coords = list(route.coords)
    start = coords[0]
    end = coords[-1]
    return start, end



# Test cases
print("\n=== TESTING ROUTE FINDER WITH DIFFERENT SCENARIOS ===")

# Test case 1: US West Coast - should find a major route
print("\nTest case 1: US West Coast (should find major route)")
result = find_nearest_route_all(-125.4321268, 42.8346738, distance_threshold=50)

# Test case 2: Pacific Ocean - may need a larger threshold
print("\nTest case 2: Pacific Ocean (larger threshold)")
result = find_nearest_route_all(-129.6383054, 36.1078860, distance_threshold=125)

# Test case 3: Mediterranean
print("\nTest case 3: Mediterranean (very large threshold)")
result = find_nearest_route_all(47.3832503, -7.2682782, distance_threshold=200)

# Test case 4: Test with a smaller threshold to see fallback to middle/minor routes
print("\nTest case 4: Testing route type fallback")
result = find_nearest_route_all(-125.4321268, 42.8346738, distance_threshold=25)

# Test case 5: Pacific - should find Minor Route
print("\nTest case 5: Pacific (should find minor route)")
result = find_nearest_route_all(-54.1721954, 18.1547936, distance_threshold=50)
print (result)

start, end = get_route_start_end(result['route'])
print(f"Start coordinates: {start}")
print(f"End coordinates: {end}")
