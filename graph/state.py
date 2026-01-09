from typing import Annotated, List, Union, TypedDict, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class CodeInsights(BaseModel):
    is_code_valid: bool
    error_stack: str
    line_no: Optional[int]
    warning_msgs: List[str]


class CADState(TypedDict):
    """
    LangGraph state model
    """
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    human_messages: List[str]
    dimensions: dict
    design_instructions: List[str]
    design_summary: str
    cadquery_program: str

    # validation flags
    is_dims_valid: bool
    is_code_valid: bool  # todo: repeated. also present in code_insights. remove from latter.
    is_review_passed: bool

    # code validation
    code_insights: CodeInsights

    # iteration tracker
    current_iter: int
    is_last_iter: bool
