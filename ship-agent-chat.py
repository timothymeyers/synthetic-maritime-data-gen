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
    await asyncio.sleep(1)
    
    route = finder.find_nearest_route_with_heading(longitude, latitude, heading)
        
    return route

async def main() -> None:
    
    # Create the chat completion client
    client = create_4o_mini_model_client()

    # Create the agent
    agent = AssistantAgent (
        name="ShipAgent",
        model_client=client,
        description="A ship expert who can answer questions about ships. You always responde in clear, consise, and accurate english. Never return JSON.",
        reflect_on_tool_use=True,
        
        tools=[
            FunctionTool(
                finder.find_nearest_route_with_heading,
                description="Get the ship route based on the given coordinates and heading.",
            ),
            
        ]
    )

    # Create the user
    user = UserProxyAgent(
        name="User",
        description="A user who is asking questions about ships.",
    )
    
    team = RoundRobinGroupChat([agent], max_turns=1)
    
    task = input("> ")
    while True:
        stream = team.run_stream(task=task)
        await Console(stream)
        task = input("> ")
        if task.lower() in ["exit", "quit"]:
            break
        
    await client.close()   
    
    
asyncio.run(main())