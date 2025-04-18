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