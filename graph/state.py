from typing import Annotated, List, Union, TypedDict

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class CADState(TypedDict):
    """
    LangGraph state model
    """
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    human_messages: List[str]
    dimensions: dict
    design_instructions: List[str]
    design_summary: str
    program_validation_status: str
    cadquery_program: str
