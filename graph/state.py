from __future__ import annotations

from typing import List, TypedDict, Dict, Any

from langchain_core.messages import BaseMessage
from partspec import PartSpec


class GraphState(TypedDict, total=False):
    messages: List[BaseMessage]

    # output of spec node
    parts_spec: Dict[str, Any]
    parts_spec_obj: PartSpec
    parts_spec_json: str

    # output of compile/export node
    step_path: str
    stl_path: str

    # optional: for routing / UI
    needs_clarification: bool
    clarification_questions: List[Dict[str, Any]]
