import numpy as np
import pandas as pd
import datetime
import math
import random
from math import radians, cos, sin, asin, sqrt, atan2, degrees

# --- Helper Functions ---

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees), returns kilometers.
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles.
    return c * r

def destination_point(lat, lon, bearing, distance):
    """
    Given a start (lat, lon in degrees), a bearing (deg) and distance (km),
    calculate the destination point using the great circle route.
    """
    r = 6371.0  # Earth radius in km
    bearing = radians(bearing)
    lat1 = radians(lat)
    lon1 = radians(lon)
    
    lat2 = asin(sin(lat1) * cos(distance/r) + cos(lat1) * sin(distance/r) * cos(bearing))
    lon2 = lon1 + atan2(sin(bearing) * sin(distance/r) * cos(lat1),
                        cos(distance/r) - sin(lat1) * sin(lat2))
    return degrees(lat2), degrees(lon2)

def generate_environmental_conditions(timestamp):
    """ Generate simulated environmental conditions.
        You can incorporate seasonal variation via the month.
    """
    # Base wind speed (knots) with some seasonal effect: higher in winter.
    month = timestamp.month
    base_wind = 10 + (5 if month in [12, 1, 2] else 0)   # ~15 knots in winter
    wind_speed = max(0, np.random.normal(base_wind, 2))
    
    wind_direction = np.random.uniform(0, 360)
    # Sea state index from 0 (calm) to 5 (storm); higher on days with high wind speed.
    sea_state = min(5, max(0, int(np.random.normal( (wind_speed / 5), 0.5) )))
    
    return round(wind_speed,1), round(wind_direction,1), sea_state

def adjust_course_for_environment(course, wind_speed):
    """
    If high wind speed, simulate a small course correction.
    """
    # If wind speed > threshold, adjust course by a random small angle.
    if wind_speed > 15:
        correction = np.random.uniform(-10, 10)  # adjust course by up to 10 degrees
        return (course + correction) % 360, True
    return course, False

# --- Ports and Routes Definitions ---

# Define a dictionary with key ports and their coordinates (lat, lon).
ports = {
    'Shanghai': (31.2304, 121.4737),
    'Yantian': (22.5431, 114.0579),
    'Singapore': (1.3521, 103.8198),
    'LosAngeles': (33.7405, -118.2775),
    'Vancouver': (49.2827, -123.1207),
    'Rotterdam': (51.9244, 4.4777),
    'Antwerp': (51.2194, 4.4025),
    'Durban': (-29.8587, 31.0218),
    'CapeTown': (-33.9249, 18.4241)
}

# Define route type probabilities:
# 60% Asia <-> North America, 20% Asia -> Europe/Africa, 10% full round world, 10% random maritime (among defined ports)
route_types = ['Asia-NorthAmerica', 'Asia-EuropeAfrica', 'RoundWorld', 'Random']

def choose_route():
    rt = random.choices(route_types, weights=[60, 20, 10, 10])[0]
    if rt == 'Asia-NorthAmerica':
        # pick one port from Asia and one from North America
        start = random.choice(['Shanghai', 'Yantian', 'Singapore'])
        end = random.choice(['LosAngeles', 'Vancouver'])
        return rt, ports[start], ports[end]
    elif rt == 'Asia-EuropeAfrica':
        start = random.choice(['Shanghai', 'Yantian', 'Singapore'])
        end = random.choice(['Rotterdam', 'Antwerp', 'Durban', 'CapeTown'])
        return rt, ports[start], ports[end]
    elif rt == 'RoundWorld':
        # For round world, we simulate a cyclic route around major coasts.
        # For simplicity, we choose a sequence of 4 ports that roughly circle the globe.
        # E.g., from Asia -> NorthAmerica -> Europe -> Africa -> back to Asia.
        route_seq = random.sample(['Shanghai', 'LosAngeles', 'Rotterdam', 'Durban'], 4)
        ports_seq = [ports[p] for p in route_seq]
        return rt, ports_seq  # We'll use the list in simulation.
    elif rt == 'Random':
        # Randomly choose two different ports from the keys
        start_p, end_p = random.sample(list(ports.keys()), 2)
        return rt, ports[start_p], ports[end_p]
    else:
        # Fallback to Asia-NorthAmerica
        return 'Asia-NorthAmerica', ports['Shanghai'], ports['LosAngeles']

# --- Main Simulation Function ---

def simulate_journey(start_time, duration_hours, start_coord, end_coord, journey_type):
    """
    Simulate a journey between start_coord and end_coord.
    Returns a DataFrame with hourly steps.
    For round world journeys, end_coord is a list of waypoints.
    """
    records = []
    if journey_type != 'RoundWorld':
        # Compute the distance between start and end
        lat1, lon1 = start_coord
        lat2, lon2 = end_coord
        total_distance = haversine(lon1, lat1, lon2, lat2)  # in km
        # Assume a baseline speed of ~23 knots (1 knot ≈ 1.852 km/h)
        baseline_speed = np.random.normal(23, 1)  # knots
        baseline_speed_kmh = baseline_speed * 1.852
        
        # Total journey time in hours based on distance, but add noise (+/- 20%)
        journey_duration = total_distance / baseline_speed_kmh
        journey_duration *= np.random.uniform(0.8, 1.2)
        journey_duration = max(1, int(journey_duration))
        
        # Create hourly timestamps for the journey
        timestamps = [start_time + datetime.timedelta(hours=i) for i in range(journey_duration)]
        
        # Interpolate along the great circle route linearly
        for i, t in enumerate(timestamps):
            frac = i / (journey_duration - 1) if journey_duration > 1 else 0
            # Simple linear interpolation in lat/lon (not exactly geodesic; good enough for simulation)
            lat = start_coord[0] + frac * (end_coord[0] - start_coord[0])
            lon = start_coord[1] + frac * (end_coord[1] - start_coord[1])
            
            # Simulate speed with noise
            speed = np.random.normal(baseline_speed, 0.5)
            # Compute course (bearing) using the formula for initial bearing
            dLon = radians(end_coord[1] - start_coord[1])
            lat1 = radians(start_coord[0])
            lat2 = radians(end_coord[0])
            x = sin(dLon) * cos(lat2)
            y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dLon)
            bearing = (degrees(atan2(x, y)) + 360) % 360
            
            # Simulate environmental conditions and adjust course if necessary.
            wind_speed, wind_dir, sea_state = generate_environmental_conditions(t)
            adjusted_course, course_adjusted = adjust_course_for_environment(bearing, wind_speed)
            
            # Set vessel status as "Underway"
            vessel_status = "Underway"
            port_call = False
            
            record = {
                'timestamp': t,
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'speed_knots': round(speed, 2),
                'course_deg': round(adjusted_course, 2),
                'vessel_status': vessel_status,
                'port_call_flag': port_call,
                'wind_speed_knots': wind_speed,
                'wind_direction_deg': wind_dir,
                'sea_state': sea_state,
                'course_adjusted': course_adjusted
            }
            records.append(record)
        return pd.DataFrame(records), timestamps[-1]  # Return the DF and the journey’s end time
    else:
        # For Round World, use the list of waypoints (simulate cycle)
        waypoints = end_coord  # In this case, end_coord is a list of waypoints
        current_time = start_time
        for idx in range(len(waypoints)):
            wp_start = waypoints[idx]
            wp_end = waypoints[(idx+1)%len(waypoints)]
            df_segment, current_time = simulate_journey(current_time, None, wp_start, wp_end, 'Segment')
            records.append(df_segment)
            # Simulate port call delay at each waypoint (e.g., 6 to 12 hours)
            delay = int(np.random.uniform(6, 12))
            port_time = [current_time + datetime.timedelta(hours=i) for i in range(1, delay+1)]
            for t in port_time:
                record = {
                    'timestamp': t,
                    'latitude': wp_end[0],
                    'longitude': wp_end[1],
                    'speed_knots': 0,
                    'course_deg': 0,
                    'vessel_status': "At Port",
                    'port_call_flag': True,
                    'wind_speed_knots': np.nan,
                    'wind_direction_deg': np.nan,
                    'sea_state': np.nan,
                    'course_adjusted': False
                }
                records.append(pd.DataFrame([record]))
            current_time = port_time[-1] if port_time else current_time
        # Concatenate all segments
        return pd.concat(records, ignore_index=True), current_time

# --- Main Simulation Loop ---
def simulate_vessel_movement(start_date, end_date):
    """
    Simulate vessel movement between start_date and end_date.
    Returns a DataFrame of the entire simulation.
    The simulation is done journey-by-journey.
    """
    current_time = start_date
    sim_records = []
    # We'll simulate until current_time >= end_date
    while current_time < end_date:
        # Choose a route type
        route_choice = choose_route()
        rt_type = route_choice[0]
        if rt_type != 'RoundWorld':
            start_coord = route_choice[1]
            end_coord = route_choice[2]
            journey_type = rt_type
            journey_df, journey_end_time = simulate_journey(current_time, None, start_coord, end_coord, journey_type)
        else:
            # For RoundWorld, rt_type is 'RoundWorld' and route_choice[1] is a list of waypoints.
            journey_df, journey_end_time = simulate_journey(current_time, None, None, route_choice[1], 'RoundWorld')
        sim_records.append(journey_df)
        
        # At the arrival port, simulate a port call: dwell time between 6 and 24 hours
        port_delay = int(np.random.uniform(6, 24))
        port_records = []
        for i in range(1, port_delay+1):
            t = journey_end_time + datetime.timedelta(hours=i)
            # Use the arrival port coordinates from journey_df (last record)
            arrival_lat = journey_df.iloc[-1]['latitude']
            arrival_lon = journey_df.iloc[-1]['longitude']
            record = {
                'timestamp': t,
                'latitude': arrival_lat,
                'longitude': arrival_lon,
                'speed_knots': 0,
                'course_deg': 0,
                'vessel_status': "At Port",
                'port_call_flag': True,
                'wind_speed_knots': np.nan,
                'wind_direction_deg': np.nan,
                'sea_state': np.nan,
                'course_adjusted': False
            }
            port_records.append(record)
        port_df = pd.DataFrame(port_records)
        
        sim_records.append(port_df)
        # Set current_time to the end of port call
        current_time = port_delay and (journey_end_time + datetime.timedelta(hours=port_delay+1)) or journey_end_time + datetime.timedelta(hours=1)
    # Concatenate all journeys
    full_simulation = pd.concat(sim_records, ignore_index=True)
    # Sort by timestamp
    full_simulation.sort_values('timestamp', inplace=True)
    # Remove duplicate timestamps if any, and reset index
    full_simulation = full_simulation.drop_duplicates(subset='timestamp').reset_index(drop=True)
    return full_simulation

# --- Run the Simulation for the 10-Year Period ---

start_date = datetime.datetime(2015, 4, 1, 0, 0, 0)
end_date   = datetime.datetime(2025, 4, 1, 0, 0, 0)

# Simulate vessel movement (the simulation runs hourly)
simulation_df = simulate_vessel_movement(start_date, end_date)

# --- Split and Write CSV Files by Year ---
simulation_df['year'] = simulation_df['timestamp'].apply(lambda t: t.year)
for year in simulation_df['year'].unique():
    df_year = simulation_df[simulation_df['year'] == year].copy()
    # Optional: reset index and drop the helper 'year' column
    df_year.reset_index(drop=True, inplace=True)
    df_year.drop(columns=['year'], inplace=True)
    output_filename = f"ever_mast_simulation_{year}.csv"
    df_year.to_csv(output_filename, index=False)
    print(f"Year {year}: {len(df_year)} records written to {output_filename}.")
