from typing import TypedDict, List, Dict, Annotated
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """State for the multi-agent running route system"""

    # Messages between agents
    messages: Annotated[List[BaseMessage], operator.add]

    # User inputs
    start_lat: float
    start_lng: float
    target_distance: float
    query: str  # original user query for router to analyze

    # Agent outputs
    routes: List[Dict]  # from Route Generation Agent
    safety_analysis: List[Dict]  # from Safety Analysis Agent
    weather: Dict  # from Contextual Intelligence Agent (we'll add later)

    # Final output
    final_recommendation: str
