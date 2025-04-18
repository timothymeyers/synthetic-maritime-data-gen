import asyncio
import json
import os
import logging
from typing import List, Sequence


from dotenv import load_dotenv

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient

import searoute as sr
from better_route_finder import BetterRouteFinder

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

finder = BetterRouteFinder()
finder.load_data()

def create_4o_mini_model_client() -> OpenAIChatCompletionClient:
    """Create and configure the Azure OpenAI chat completion client."""
    return AzureOpenAIChatCompletionClient(
        model="gpt-4o-mini",
        azure_deployment="gpt-4o-mini",
    )
    
async def get_ship_route (origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float, waypoints: dict=None) -> json:
    """Get the ship route based on the given coordinates."""
    
    logger.info(f"\n\nGetting ship route from {origin_lon}, {origin_lat} to {dest_lon}, {dest_lat} with waypoints {waypoints}\n\n")
    
    origin = [origin_lon, origin_lat]
    destination = [dest_lon, dest_lat]
    
    myM = None
    if waypoints is not None:
        waypoint_keys = list(waypoints.keys())
        if len(waypoint_keys) >= 2:
            my_edges = {
                waypoint_keys[0]: { waypoint_keys[1]: {"weight": 1} },
                waypoint_keys[1]: { waypoint_keys[0]: {"weight": 1} }
            }
            myM = sr.from_nodes_edges_set(sr.Marnet(), waypoints, my_edges)
        else:
            my_edges = {}
    else:
        my_edges = {}
    
    print (f"\n\nmy_edges: {my_edges}\n\n")

    logger.info(f"myM: {myM}")

    route = sr.searoute(origin, destination, M=myM, include_ports=False, append_orig_dest=True)
           
    if route is not None:
        logger.info (f"\n\n\tSearoute: {str(route)}\n\n")
        return route
    else:
        logger.warning("No route found.")
        return None

async def get_possible_ship_route (longitude: float, latitude: float, heading: float) -> json:
   
    distance_threshold = 5  # in nautical miles
    heading_threshold = 5  # in degrees
    
    logger.info(f"Searching for route with distance threshold: {distance_threshold} and heading threshold: {heading_threshold}")
    for heading_threshold in range(5, 46, 5):
        for distance_threshold in range(25, 201, 25):
            logger.info(f"Searching for route with distance threshold: {distance_threshold} and heading threshold: {heading_threshold}")
            route = finder.find_nearest_route_with_heading(longitude, latitude, heading, distance_threshold=distance_threshold, heading_threshold=heading_threshold)
            if route is not None: 
                logger.info(f"\n\nRoute found: {route}\n\n")
                
                waypoints = finder.get_next_waypoints(longitude, latitude, heading, route["route_id"], route["route_type"], num_waypoints=2)
                logger.info(f"\n\nWaypoints: {waypoints}\n\n")
                
                if waypoints is not None:
                    my_nodes = {
                        (longitude, latitude): {'x': longitude, 'y': latitude},
                        #(waypoints[0][0], waypoints[0][1]): {'x': waypoints[0][0], 'y': waypoints[0][1]},
                        (waypoints[1][0], waypoints[1][1]): {'x': waypoints[1][0], 'y': waypoints[1][1]}
                    }
                    logger.info(f"my_nodes: {my_nodes}")
               
                searoute = await get_ship_route(longitude, latitude, route["ending_point"][0], route["ending_point"][1], waypoints=my_nodes)
                if searoute is not None:
                    # update searoute["geometry"]["coorinates"] with the waypoints
                    #searoute["geometry"]["coordinates"] = [[longitude, latitude]] + [waypoints[0], waypoints[1]] + searoute["geometry"]["coordinates"][1:]
                    logger.info(f"\n\n\tSearoute: {str(searoute)}\n\n")
               
                return searoute
    
    logger.info("No route found")
        
    return None


async def get_ship_waypoints (longitude: float, latitude: float, heading: float, speed: float, interval: int, num_waypoints: int, route_id: str) -> json:
    """Get the ship waypoints based on the given coordinates."""
    logger.info(f"\n\n\nGetting ship waypoints from {longitude}, {latitude} with heading {heading}, speed {speed}, interval {interval}, num_waypoints {num_waypoints}, route_id {route_id}\n\n\n")
    
    return {"coordinates": [[0,1], [0,2], [0,3], [0,4], [0,5]]}

    
# what is the ship's route from [0.3515625, 50.064191736659104] to [117.42187500000001, 39.36827914916014]

async def get_ship_waypoints_unknown_route (longitude: float, latitude: float, heading: float, speed_knots: float, interval_hrs: int, num_waypoints: int = None )  -> json:
    """Get the ship waypoints based on the given coordinates."""
    logger.info(f"\n\n\nGetting ship waypoints from {longitude}, {latitude} with heading {heading}, speed {speed_knots}, interval {interval_hrs}, num_waypoints {num_waypoints}\n\n\n")
    
    route = finder.get_next_waypoints_with_speed_and_heading_unknown_route(longitude, latitude, heading, speed_knots, interval_hrs, num_waypoints)
    if route is not None:
        logger.info(f"\n\nRoute found: {route}\n\n")
        return route
    else:
        logger.warning("No route found.")
        return None
    
async def get_ship_waypoints_known_route (longitude: float, latitude: float, dest_longitude:float, dest_latitude: float, heading: float, speed_knots: float, interval_hrs: int, num_waypoints: int = None) -> json:
    """Get the ship waypoints based on the given coordinates."""
    logger.info(f"\n\n\nGetting ship waypoints from {longitude}, {latitude} to {dest_longitude}, {dest_latitude} with heading {heading}, speed {speed_knots}, interval {interval_hrs}, num_waypoints {num_waypoints}\n\n\n")
    
    route = finder.get_next_waypoints_with_speed_and_heading_known_destination(longitude, latitude, dest_longitude, dest_latitude, heading, speed_knots, interval_hrs, num_waypoints)
    if route is not None:
        logger.info(f"\n\nRoute found: {route}\n\n")
        return route
    else:
        logger.warning("No route found.")
        return None

async def main() -> None:
    
    # Create the chat completion client
    client = create_4o_mini_model_client()

    # Create the agent
    routeFinderAgent = AssistantAgent (
        name="RouteFinderAgent",
        model_client=client,
        description="A ship expert who answers questions using only data from available tools. Respond in clear, concise, and accurate English. Do not make assumptions or inferences. Always report the ROUTE ID Number Never return JSON.",
        reflect_on_tool_use=True,
        
        tools=[
            FunctionTool(
                get_possible_ship_route,
                description="If you don't know the ship's origin AND destination, look-up the likely ship route based on the ship's current coordinates and heading.",
                
            ),
            FunctionTool(
                get_ship_route,
                description="Get the ship route based on an origin and destination.",  
            ),
            #FunctionTool(
            #    get_ship_waypoints,
            #    description="Get the ship waypoints based a current position, heading, speed in knots, interval in minutes, number of waypoints, and route id.",
            #)
        ]
    )
    
    betterRouteFinderAgent = AssistantAgent (
        name="BetterRouteFinderAgent",
        model_client=client,
        description="A ship expert who answers questions using only data from available tools. Respond in clear, concise, and accurate English. Do not make assumptions or inferences. Always report the ROUTE ID Number Never return JSON.",
        reflect_on_tool_use=True,
        
        tools=[
            FunctionTool(
                get_ship_waypoints_known_route,
                description="Get the ship waypoints based on a current position, destination, heading, speed in knots, interval in minutes, number of waypoints.",
            ),
            FunctionTool(
                get_ship_waypoints_unknown_route,
                description="Get the ship waypoints based on a current position, heading, speed in knots, interval in minutes, number of waypoints.",
            )
        ]
    )
    
    
    # Create the agent
    waypointAgent = AssistantAgent (
        name="WaypointAgent",
        model_client=client,
        description="A shiping route expert who answers questions using only data from available tools. Respond in clear, concise, and accurate English. When provided a route id and or type, you are able to provide start and endpoint data, as well as waypoint data on that route. Do not make assumptions or inferences. Never return JSON.",
        reflect_on_tool_use=True,
        
        tools=[]
    )
    
    summarizerAgent = AssistantAgent (
        name="SummarizerAgent",
        model_client=client,
        description="You will summarize the information within conversation so far and report back to the user. You always go last in a chat conversation. You will not make assumptions or inferences.",
        
    )

    # Create the user
    user = UserProxyAgent(
        name="User",
        description="A user who is asking questions about ships.",
    )
    
    team = RoundRobinGroupChat([betterRouteFinderAgent], max_turns=1)
    
    task = input("> ")
    while True:
        stream = team.run_stream(task=task)
        await Console(stream)
        task = input("> ")
        if task.lower() in ["exit", "quit"]:
            break
        
    await client.close()   
    
    
asyncio.run(main())