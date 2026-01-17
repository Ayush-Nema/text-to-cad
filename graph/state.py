from typing import Annotated, List, Union, TypedDict, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class CodeInsights(BaseModel):
    error_stack: Optional[str]
    line_no: Optional[int]
    warning_msgs: List[str]


class CritiqueIssue(BaseModel):
    category: str = Field(description="geometry, dimensions, practicality, cadquery, intent, image, ambiguity")
    severity: str = Field(description="critical, major, or minor")
    description: str
    suggestion: str


class DesignCritiqueResult(BaseModel):
    status: bool
    summary: str
    issues: List[CritiqueIssue]


class CADState(TypedDict):
    """
    LangGraph state model
    """
    messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
    human_messages: List[str]
    dimensions: dict
    design_instructions: List[str]
    cadquery_context: str
    design_summary: str
    cadquery_program: str

    # validation flags
    is_dims_valid: bool
    is_code_valid: bool
    is_review_passed: bool

    # code validation
    code_insights: CodeInsights

    # iteration tracker
    current_iter: int
    is_last_iter: bool

    design_critique: Optional[DesignCritiqueResult]
