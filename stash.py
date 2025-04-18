    
    def _get_course_correction(
        self,
        lon: float,
        lat: float,
        heading: float,
        speed: float,
        route_id: int,
        route_type: str = None,
        heading_change_maximum: float = 15.0
    ) -> Dict:
        """
        Calculate course correction to align with a specified route.
        
        Args:
            lon: Current longitude coordinate
            lat: Current latitude coordinate
            heading: Current heading in degrees (0-360)
            speed: Current speed in knots
            route_id: ID of the target route
            route_type: Type of route (MAJOR, MIDDLE, MINOR)
            heading_change_maximum: Maximum allowed heading change in degrees per hour
            
        Returns:
            Dictionary containing:
            {
                'new_heading': float,  # The recommended new heading
                'new_position': [lon, lat],  # Projected position after 1 hour
                'distance_to_route': float,  # Distance to route in nm after correction
                'route_heading': float,  # Heading of the route at nearest point
                'heading_change': float,  # Amount heading was changed
                'reached_route': bool  # Whether the route will be reached
            }
        """
        logger.info(f"[DEBUG] Starting course correction calculation:")
        logger.info(f"[DEBUG] Input parameters: lon={lon:.6f}, lat={lat:.6f}, heading={heading:.2f}°, speed={speed:.2f}kt")
        logger.info(f"[DEBUG] Route info: id={route_id}, type={route_type}, max_heading_change={heading_change_maximum:.2f}°")
        
        # Get the specified route
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            logger.error(f"[DEBUG] Route not found: id={route_id}, type={route_type}")
            raise ValueError(f"Route not found: id={route_id}, type={route_type}")
        else:
            logger.info(f"[DEBUG] Route found with {len(list(route.coords))} coordinate points")
        
        # Create Point object from current position
        current_position = Point(lon, lat)
        
        # Find nearest point on route
        proj_distance = route.project(current_position)
        nearest_point = route.interpolate(proj_distance)
        
        # Calculate distance to route in nautical miles
        distance_to_route = current_position.distance(nearest_point) * 60
        
        logger.info(f"[DEBUG] Nearest point on route: [{nearest_point.x:.6f}, {nearest_point.y:.6f}]")
        logger.info(f"[DEBUG] Current distance to route: {distance_to_route:.2f} nautical miles")
        
        # Get coords to determine route direction
        coords = list(route.coords)
        
        # Find surrounding points on the route
        segment_found = False
        logger.info(f"[DEBUG] Searching for route segment containing nearest point")
        
        for i in range(len(coords) - 1):
            segment = LineString([coords[i], coords[i + 1]])
            segment_distance = segment.distance(nearest_point)
            
            if segment_distance < 1e-10:  # Point is on this segment
                segment_found = True
                logger.info(f"[DEBUG] Found segment at index {i} with points:")
                logger.info(f"[DEBUG]   Point {i}: [{coords[i][0]:.6f}, {coords[i][1]:.6f}]")
                logger.info(f"[DEBUG]   Point {i+1}: [{coords[i+1][0]:.6f}, {coords[i+1][1]:.6f}]")
                
                # Calculate forward and backward headings
                forward_heading = self._calculate_heading(coords[i], coords[i + 1])
                backward_heading = self._calculate_heading(coords[i + 1], coords[i])
                
                logger.info(f"[DEBUG] Segment headings: forward={forward_heading:.2f}°, backward={backward_heading:.2f}°")
                logger.info(f"[DEBUG] Current vessel heading: {heading:.2f}°")
                
                # Determine which direction is better
                forward_diff = min(abs(heading - forward_heading), 360 - abs(heading - forward_heading))
                backward_diff = min(abs(heading - backward_heading), 360 - abs(heading - backward_heading))
                
                logger.info(f"[DEBUG] Heading differences: forward={forward_diff:.2f}°, backward={backward_diff:.2f}°")
                
                if forward_diff <= backward_diff:
                    route_heading = forward_heading
                    heading_diff = forward_diff
                    logger.info(f"[DEBUG] Selected forward direction as best match")
                else:
                    route_heading = backward_heading
                    heading_diff = backward_diff
                    logger.info(f"[DEBUG] Selected backward direction as best match")
                
                break
            else:
                # If loop didn't break, use the endpoints
                logger.info(f"[DEBUG] No matching segment found for nearest point, using fallback logic")
                
                if len(coords) >= 2:
                    route_heading = self._calculate_heading(coords[0], coords[1])
                    heading_diff = min(abs(heading - route_heading), 360 - abs(heading - route_heading))
                    logger.info(f"[DEBUG] Using route endpoints for heading: {route_heading:.2f}°")
                    logger.info(f"[DEBUG] Heading difference with vessel: {heading_diff:.2f}°")
                else:
                    # Fallback if route has insufficient points
                    route_heading = heading
                    heading_diff = 0
                    logger.info(f"[DEBUG] Route has insufficient points, using vessel heading as fallback")
        
        # Calculate new heading based on maximum allowed change
        new_heading = heading
        if heading_diff > 0:
            # Determine direction of turn (clockwise or counterclockwise)
            heading_change = min(heading_diff, heading_change_maximum)
            logger.info(f"[DEBUG] Heading change required: {heading_diff:.2f}°, limited to: {heading_change:.2f}°")
            
            # Calculate shortest direction to turn
            turn_direction = "counterclockwise" if (heading - route_heading + 360) % 360 < 180 else "clockwise"
            logger.info(f"[DEBUG] Turn direction: {turn_direction}")
            
            if turn_direction == "counterclockwise":
                # Turn counterclockwise
                new_heading = (heading - heading_change + 360) % 360
            else:
                # Turn clockwise
                new_heading = (heading + heading_change) % 360
                
            logger.info(f"[DEBUG] New heading calculated: {new_heading:.2f}°")
        
        # Calculate new position based on speed (in knots) traveling for 1 hour
        # 1 knot = 1 nautical mile per hour
        import math
        
        # Convert heading to radians for calculation
        heading_rad = math.radians(new_heading)
        
        # Calculate displacement in degrees
        # 1 degree latitude = 60 nautical miles
        distance_nm = speed  # Speed in knots * 1 hour = distance in nm
        logger.info(f"[DEBUG] Projecting movement: speed={speed:.2f}kt, distance in 1hr={distance_nm:.2f}nm")
        
        # Calculate new position
        new_lat = lat + (distance_nm * math.cos(heading_rad) / 60.0)  # Convert nm to degrees
        new_lon = lon + (distance_nm * math.sin(heading_rad) / (60.0 * math.cos(math.radians(lat))))
        logger.info(f"[DEBUG] Projected new position: lon={new_lon:.6f}, lat={new_lat:.6f}")
        
        # Check if the new position overshoots the route
        new_position = Point(new_lon, new_lat)
        new_dist_to_route = new_position.distance(route) * 60  # Convert degrees to nm
        logger.info(f"[DEBUG] Distance to route after movement: {new_dist_to_route:.2f}nm (was {distance_to_route:.2f}nm)")
        
        # Check if we'll reach the route with this correction
        reached_route = False
        
        # If we will reach the route within this hour, adjust the position
        if new_dist_to_route < 0.01:  # Effectively on the route
            reached_route = True
            logger.info(f"[DEBUG] Vessel will be effectively on the route (distance < 0.01nm)")
        elif distance_to_route > new_dist_to_route and new_dist_to_route < 1.0:
            # We're getting closer but not quite there - check if we would cross over
            logger.info(f"[DEBUG] Getting closer to route, checking if path crosses the route")
            
            # Create a line from current to projected position
            movement_line = LineString([(lon, lat), (new_lon, new_lat)])
            
            # Check if this line intersects the route
            if movement_line.intersects(route):
                logger.info(f"[DEBUG] Path intersects with route, adjusting position to intersection point")
                
                # Find intersection point
                intersection = movement_line.intersection(route)
                logger.info(f"[DEBUG] Intersection type: {intersection.geom_type}")
                
                # If the intersection is a point or multiple points, adjust to the first intersection
                if intersection.geom_type == 'Point':
                    new_lon, new_lat = intersection.x, intersection.y
                    reached_route = True
                    logger.info(f"[DEBUG] Adjusted to intersection point: lon={new_lon:.6f}, lat={new_lat:.6f}")
                elif 'Point' in intersection.geom_type:  # MultiPoint or GeometryCollection
                    point = next(iter(intersection.geoms))
                    new_lon, new_lat = point.x, point.y
                    reached_route = True
                    logger.info(f"[DEBUG] Adjusted to first intersection point: lon={new_lon:.6f}, lat={new_lat:.6f}")
                else:
                    logger.info(f"[DEBUG] Complex intersection type {intersection.geom_type}, not adjusting position")
        
        
        result={
            'new_heading': new_heading,
            'new_position': [new_lon, new_lat],
            'distance_to_route': new_dist_to_route,
            'route_heading': route_heading,
            'heading_change': abs(new_heading - heading),
            'reached_route': reached_route
        }
        #pretty_print(result)
        logger.info(f"\n\n\nCourse correction result: {result}\n\n\n")
        
        return result
    
    def _get_intercept_bearing(
        self,
        lon: float,
        lat: float,
        current_heading: float,
        speed: float,
        route_id: int,
        route_type: str = None,
        heading_change_maximum: float = 15.0
    ) -> float:
        """
        Calculate the intercept bearing to a specified route.
        
        Args:
            lon: Current longitude coordinate
            lat: Current latitude coordinate
            current_heading: Current heading in degrees (0-360)
            speed: Current speed in knots
            route_id: ID of the target route
            route_type: Type of route (MAJOR, MIDDLE, MINOR)
            heading_change_maximum: Maximum allowed heading change in degrees per hour
            
        Returns:
            Intercept bearing in degrees (0-360)
        """
        logger.info(f"[DEBUG] Starting intercept bearing calculation:")
        logger.info(f"[DEBUG] Input parameters: lon={lon:.6f}, lat={lat:.6f}, heading={current_heading:.2f}°, speed={speed:.2f}kt")
        logger.info(f"[DEBUG] Route info: id={route_id}, type={route_type}, max_heading_change={heading_change_maximum:.2f}°")
        
        # Get the specified route
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            logger.error(f"Route not found: id={route_id}, type={route_type}")
            raise ValueError(f"Route not found: id={route_id}, type={route_type}")
        else:
            logger.info(f"[DEBUG] Route found with {len(list(route.coords))} coordinate points")
            
        # Create Point object and find nearest point on route
        current_position = Point(lon, lat)
        proj_distance = route.project(current_position)
        nearest_point = route.interpolate(proj_distance)
        
        # Calculate the direction between current_position and nearest point
        nearest_point_heading = self._calculate_heading((current_position.x, current_position.y), (nearest_point.x, nearest_point.y))
         
        heading_difference = (current_heading - nearest_point_heading + 360) % 360 / 2.0
        
        # Calculate distance to route in nautical miles
        distance_to_route = current_position.distance(nearest_point) * 60
        logger.info(f"[DEBUG] \tNearest point on route: [{nearest_point.x:.6f}, {nearest_point.y:.6f}]")
        logger.info(f"[DEBUG] \tNearest point heading: {nearest_point_heading:.2f}°")
        logger.info(f"[DEBUG] \tTurn to intercept: {heading_difference:.2f}°")
        logger.info(f"[DEBUG] \tDistance to route: {distance_to_route:.2f} nm")
        
        # Find the route segment containing the nearest point
        coords = list(route.coords)
        route_heading = None
        heading_diff = None
        
        logger.info(f"[DEBUG] Searching for route segment containing nearest point")
        
        # Try to find the segment containing the nearest point
        for i in range(len(coords) - 1):
            segment = LineString([coords[i], coords[i + 1]])
            if segment.distance(nearest_point) < 1e-10:  # Point is on this segment
                logger.info(f"[DEBUG] Found segment at index {i} with points:")
                logger.info(f"[DEBUG]   Point {i}: [{coords[i][0]:.6f}, {coords[i][1]:.6f}]")
                logger.info(f"[DEBUG]   Point {i+1}: [{coords[i+1][0]:.6f}, {coords[i+1][1]:.6f}]")
                
                # Calculate forward and backward headings
                forward_heading = self._calculate_heading(coords[i], coords[i + 1])
                backward_heading = self._calculate_heading(coords[i + 1], coords[i])
                
                logger.info(f"[DEBUG] Segment headings: forward={forward_heading:.2f}°, backward={backward_heading:.2f}°")
                logger.info(f"[DEBUG] Current vessel heading: {current_heading:.2f}°")
                
                # Determine which direction aligns better with current heading
                forward_diff = min(abs(current_heading - forward_heading), 360 - abs(current_heading - forward_heading))
                backward_diff = min(abs(current_heading - backward_heading), 360 - abs(current_heading - backward_heading))
                
                logger.info(f"[DEBUG] Heading differences: forward={forward_diff:.2f}°, backward={backward_diff:.2f}°")
                
                if forward_diff <= backward_diff:
                    route_heading = forward_heading
                    heading_diff = forward_diff
                    logger.info(f"[DEBUG] Selected forward direction as best match")
                else:
                    route_heading = backward_heading
                    heading_diff = backward_diff
                    logger.info(f"[DEBUG] Selected backward direction as best match")
                    
                break
                
        # Fallback if no segment was found
        if route_heading is None:
            logger.info(f"[DEBUG] No matching segment found for nearest point, using fallback logic")
            
            if len(coords) >= 2:
                route_heading = self._calculate_heading(coords[0], coords[1])
                heading_diff = min(abs(current_heading - route_heading), 360 - abs(current_heading - route_heading))
                logger.info(f"[DEBUG] Using route endpoints for heading: {route_heading:.2f}°")
                logger.info(f"[DEBUG] Heading difference with vessel: {heading_diff:.2f}°")
            else:
                # Fallback if route has insufficient points
                route_heading = current_heading
                heading_diff = 0
                logger.info(f"[DEBUG] Route has insufficient points, using vessel heading as fallback")
                
        # Calculate new heading based on maximum allowed change
        new_heading = current_heading
        if heading_diff > 0:
            # Determine direction of turn (clockwise or counterclockwise)
            heading_change = min(heading_diff, heading_change_maximum)
            logger.info(f"[DEBUG] Heading change required: {heading_diff:.2f}°, limited to: {heading_change:.2f}°")
            
            # Calculate shortest direction to turn
            turn_direction = "counterclockwise" if (current_heading - route_heading + 360) % 360 < 180 else "clockwise"
            logger.info(f"[DEBUG] Turn direction: {turn_direction}")
            
            if turn_direction == "counterclockwise":
                # Turn counterclockwise
                new_heading = (current_heading - heading_change + 360) % 360
            else:
                # Turn clockwise
                new_heading = (current_heading + heading_change) % 360
        
        logger.info(f"[DEBUG] Final intercept bearing calculated: {new_heading:.2f}°")
        return new_heading

    def _check_heading_for_route_intersection(
        self,
        lon: float,
        lat: float,
        heading: float,
        route_id: int,
        route_type: str = None) -> bool:
        """
        Calculate course correction to align with a specified route.
        Args:
            lon: Current longitude coordinate
            lat: Current latitude coordinate
            heading: Current heading in degrees (0-360)
            route_id: ID of the target route
            route_type: Type of route (MAJOR, MIDDLE, MINOR)
        Returns:
            True if the vessel will eventually intersect with the route, False otherwise
        """
        logger.debug(f"[DEBUG] Starting route intersection check:")        
        logger.debug(f"[DEBUG] Input parameters: lon={lon:.6f}, lat={lat:.6f}, heading={heading:.2f}°")
        logger.debug(f"[DEBUG] Route info: id={route_id}, type={route_type}")
        
        # Get the specified route
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            logger.error(f"[DEBUG] Route not found: id={route_id}, type={route_type}")
            raise ValueError(f"Route not found: id={route_id}, type={route_type}")
        else:
            logger.debug(f"[DEBUG] Route found with {len(list(route.coords))} coordinate points")
        
        # Create Point object and calculate current distance to route
        current_position = Point(lon, lat)
        distance_to_route = current_position.distance(route) * 60  # Convert degrees to nm
        
        # determine if, at the current heading, the vessel will intersect with the route, eventually.
        # Create a line from current position in the current heading direction
        import math
        heading_rad = math.radians(heading)
        distance_nm = 1.0
        new_lat = lat + (distance_nm * math.cos(heading_rad) / 60.0)
        new_lon = lon + (distance_nm * math.sin(heading_rad) / (60.0 * math.cos(math.radians(lat))))
        new_position = Point(new_lon, new_lat)
        new_distance_to_route = new_position.distance(route) * 60
        logger.debug(f"[DEBUG] \tProjected new position: lon={new_lon:.6f}, lat={new_lat:.6f}")
        logger.debug(f"[DEBUG] \tDistance to route after movement: {new_distance_to_route:.2f}nm (was {distance_to_route:.2f}nm)")
        
        if new_distance_to_route < distance_to_route:
            # If the new position is closer to the route, we can assume that the vessel will eventually intersect with the route
            logger.debug(f"[DEBUG] Vessel will eventually intersect with the route")
            return True
        else:
            logger.debug(f"[DEBUG] Vessel will not intersect with the route")
            return False
    
    def _get_course_correction_2(
        self,
        lon: float,
        lat: float,
        heading: float,
        speed: float,
        route_id: int,
        route_type: str = None,
        heading_change_maximum: float = 15.0
    ) -> Dict:
        """
        Calculate course correction to align with a specified route.
        
        Args:
            lon: Current longitude coordinate
            lat: Current latitude coordinate
            heading: Current heading in degrees (0-360)
            speed: Current speed in knots
            route_id: ID of the target route
            route_type: Type of route (MAJOR, MIDDLE, MINOR)
            heading_change_maximum: Maximum allowed heading change in degrees per hour
            
        Returns:
            Dictionary containing:
            {
                'new_heading': float,  # The recommended new heading
                'new_position': [lon, lat],  # Projected position after 1 hour
                'distance_to_route': float,  # Distance to route in nm after correction
                'route_heading': float,  # Heading of the route at nearest point
                'heading_change': float,  # Amount heading was changed
                'reached_route': bool  # Whether the route will be reached
            }
        """
        logger.info(f"[DEBUG] Starting course correction calculation:")
        logger.info(f"[DEBUG] Input parameters: lon={lon:.6f}, lat={lat:.6f}, heading={heading:.2f}°, speed={speed:.2f}kt")
        logger.info(f"[DEBUG] Route info: id={route_id}, type={route_type}, max_heading_change={heading_change_maximum:.2f}°")
        # Get the specified route
        route = self._get_route_by_id(route_id, route_type)
        if route is None:
            logger.error(f"[DEBUG] Route not found: id={route_id}, type={route_type}")
            raise ValueError(f"Route not found: id={route_id}, type={route_type}")
        else:
            logger.info(f"[DEBUG] Route found with {len(list(route.coords))} coordinate points")
            
        # 1. First see if the vessel will eventually intersect with the route
        will_intersect = self._check_heading_for_route_intersection(lon, lat, heading, route_id, route_type)
        logger.info(f"[DEBUG] Will intersect with route: {will_intersect}")
        
        
        
        
        
        
        
        #2. Calculate the intercept bearing
        intercept_bearing = self._get_intercept_bearing(lon, lat, heading, speed, route_id, route_type)
        intercept_bearing = intercept_bearing
        logger.info(f"[DEBUG] Intercept bearing: {intercept_bearing:.2f}°")
        
        #3 . Calculate the new position based on the intercept bearing
        import math
        heading_rad = math.radians(intercept_bearing)
        distance_nm = speed
        logger.info(f"[DEBUG] Projecting movement: speed={speed:.2f}kt, distance in 1hr={distance_nm:.2f}nm")
        # Calculate new position
        new_lat = lat + (distance_nm * math.cos(heading_rad) / 60.0)
        new_lon = lon + (distance_nm * math.sin(heading_rad) / (60.0 * math.cos(math.radians(lat))))
        logger.info(f"[DEBUG] Projected new position: lon={new_lon:.6f}, lat={new_lat:.6f}")
        # Check if the new position overshoots the route
        new_position = Point(new_lon, new_lat)
        new_distance_to_route = new_position.distance(route) * 60
        logger.info(f"[DEBUG] Distance to route after movement: {new_distance_to_route:.2f}nm")
        
        
        return {
            'new_heading': intercept_bearing,
            'new_position': [new_lon, new_lat],  # Updated to use the calculated new position
            'distance_to_route': new_distance_to_route,  # Updated to use the calculated distance
            
            'heading_change': abs(heading - intercept_bearing),  # Calculate heading change
            'will_intersect': will_intersect
        }
        