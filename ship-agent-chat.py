import asyncio
import json
import os
from typing import List, Sequence

from dotenv import load_dotenv

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient

# import the RouteFinder class from the route_finder module in this directory
from route_finder import RouteFinder

load_dotenv()

finder = RouteFinder()
finder.load_data()

def create_4o_mini_model_client() -> OpenAIChatCompletionClient:
    """Create and configure the Azure OpenAI chat completion client."""
    return AzureOpenAIChatCompletionClient(
        model="gpt-4o-mini",
        azure_deployment="gpt-4o-mini",
    )

async def get_possible_ship_route (longitude: float, latitude: float, heading: float) -> json:
    """Get the ship route based on the given coordinates."""
    # Simulate a function that fetches the ship route
    #await asyncio.sleep(1)
    
    distance_threshold = 5  # in nautical miles
    heading_threshold = 5  # in degrees
    
    # loop through heading thresholds, increasing by 5 degrees, until you get to 45 degrees.
    # If you don't find a route, return None
    for heading_threshold in range(5, 46, 5):
    
        for distance_threshold in range(25, 201, 25):
    
           print (f"Trying with distance threshold: {distance_threshold} and heading threshold: {heading_threshold}. ")
           route = finder.find_nearest_route_with_heading(longitude, latitude, heading, distance_threshold=distance_threshold, heading_threshold=heading_threshold)
           if route is not None: return route
    
        
    return None

async def main() -> None:
    
    # Create the chat completion client
    client = create_4o_mini_model_client()

    # Create the agent
    routeFinderAgent = AssistantAgent (
        name="RouteFinderAgent",
        model_client=client,
        description="A ship expert who answers questions using only data from available tools. Respond in clear, concise, and accurate English. Do not make assumptions or inferences. Always report the ROUTE ID Number Never return JSON.",
        #reflect_on_tool_use=True,
        
        tools=[
            FunctionTool(
                get_possible_ship_route,
                description="Get the ship route based on the given coordinates and heading.",
                
            )
        ]
    )
    
    # Create the agent
    waypointAgent = AssistantAgent (
        name="WaypointAgent",
        model_client=client,
        description="A shiping route expert who answers questions using only data from available tools. Respond in clear, concise, and accurate English. When provided a route id and or type, you are able to provide start and endpoint data, as well as waypoint data on that route. Do not make assumptions or inferences. Never return JSON.",
        #reflect_on_tool_use=True,
        
        tools=[            
            FunctionTool(
                finder.get_next_waypoints,
                description="Get the next waypoints on a route, given the route id, current coordinates and heading.",
            ),
            FunctionTool(
                finder.get_route_endpoints,
                description="Get the start and end coordinates of a route, given the route id and optionally route type.",
            )
        ]
    )
    
    summarizerAgent = AssistantAgent (
        name="SummarizerAgent",
        model_client=client,
        description="You will summarize the conversation so far and report back to the user. You always go last in a chat conversation. You will not make assumptions or inferences.",
        
    )

    # Create the user
    user = UserProxyAgent(
        name="User",
        description="A user who is asking questions about ships.",
    )
    
    team = RoundRobinGroupChat([routeFinderAgent, waypointAgent,summarizerAgent], max_turns=3)
    
    task = input("> ")
    while True:
        stream = team.run_stream(task=task)
        await Console(stream)
        task = input("> ")
        if task.lower() in ["exit", "quit"]:
            break
        
    await client.close()   
    
    
asyncio.run(main())