from typing import Annotated, List, Optional, Union, TypedDict

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class CADState(TypedDict):
    """
    LangGraph state model
    """
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    dimension_json: Optional[dict]
    design_instructions: Optional[List[str]]
    object_summary: Optional[str]
    validation_status: Optional[str]
    cad_output: Optional[dict]
