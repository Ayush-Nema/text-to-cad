from __future__ import annotations

from typing import List, TypedDict, Dict, Any

from langchain_core.messages import BaseMessage
from graph.nodes.partspec import PartSpec


class GraphState(TypedDict, total=False):
    messages: List[BaseMessage]

    # output of spec node
    parts_spec: Dict[str, Any]
    parts_spec_obj: PartSpec
    parts_spec_json: str

    # output of validation node
    is_valid: bool
    validation_errors: List[Dict[str, Any]]

    # output of repair loop control
    repair_attempts: int

    # output of compile/export node
    step_path: str
    stl_path: str
    compile_failed: bool

    # optional: for routing / UI
    needs_clarification: bool
    clarification_questions: List[Dict[str, Any]]

    # populated when the system cannot fulfill the request (out-of-scope or
    # repair-loop exhaustion). main.py prints these uniformly.
    unsupported_aspects: List[str]
    suggested_alternatives: List[str]
    scope_decision: Dict[str, Any]
