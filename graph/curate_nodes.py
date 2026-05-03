from __future__ import annotations

import json
from typing import List

from graph.nodes.compiler import compile_and_export, CADCompileError
from graph.nodes.partspec import PartSpec
from graph.state import GraphState
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from prompts import partspec_prompt, partspec_repair_prompt


def latest_human_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
    raise ValueError("No HumanMessage found in state['messages'].")


def make_generate_partspec_node(llm: BaseChatModel):
    """
    Node factory that binds `llm` once. Returned node has signature node(state)->state.
    Uses structured output:
      structured_llm = llm.with_structured_output(PartSpec)
      result = structured_llm.invoke(messages)
    """
    # Pin temperature=0 at the node layer so determinism doesn't depend on the caller.
    deterministic_llm = llm.bind(temperature=0)
    structured_llm = deterministic_llm.with_structured_output(PartSpec, method="function_calling")

    def _node(state: GraphState) -> GraphState:
        msgs = state.get("messages", [])
        user_request = latest_human_text(msgs)

        # Keep LLM input small & stable for determinism
        llm_messages = [
            ("system", partspec_prompt.PARTSPEC_SYSTEM_PROMPT),
            ("human", user_request),
        ]

        result = structured_llm.invoke(llm_messages)

        # Normalize for downstream tools/caching
        spec_dict = result.model_dump()
        spec_json = json.dumps(spec_dict, sort_keys=True)

        new_state: GraphState = dict(state)
        new_state["parts_spec_obj"] = result
        new_state["parts_spec"] = spec_dict
        new_state["parts_spec_json"] = spec_json

        # Useful for routing: if clarifications exist, downstream can branch
        needs_clarification = len(result.clarifications_needed) > 0
        new_state["needs_clarification"] = needs_clarification
        new_state["clarification_questions"] = [
            c.model_dump() for c in result.clarifications_needed
        ]

        # Optional: append JSON for trace/debug in LangGraph Studio
        new_state["messages"] = msgs + [AIMessage(content=spec_json)]

        return new_state

    return _node


def make_compile_export_node(out_dir: str, export_step: bool = True, export_stl: bool = True, ):
    """
    Calls your existing CAD toolchain (already implemented elsewhere):
      compile_and_export(parts_spec=<dict or PartSpec>, out_dir=..., export_step=..., export_stl=...)
    """

    def _node(state: GraphState) -> GraphState:
        spec = state.get("parts_spec")
        if not spec:
            raise ValueError("Missing state['parts_spec'] (run generate_partspec first).")

        # If clarifications are needed, you probably should NOT compile.
        # You can route around this node in the graph.
        if state.get("needs_clarification"):
            # No-op: return state unchanged (or raise if you prefer)
            return state

        try:
            result = compile_and_export(
                parts_spec=spec,
                out_dir=out_dir,
                export_step=export_step,
                export_stl=export_stl,
            )
        except CADCompileError as e:
            # The validator passed but CadQuery raised at compile time. Surface
            # this as a validation error so the repair loop can address it,
            # rather than crashing the graph.
            new_state: GraphState = dict(state)
            existing_errors = list(state.get("validation_errors") or [])
            existing_errors.append({
                "path": "compile",
                "message": str(e),
                "severity": "error",
            })
            new_state["validation_errors"] = existing_errors
            new_state["is_valid"] = False
            new_state["compile_failed"] = True
            return new_state

        new_state: GraphState = dict(state)
        new_state["compile_failed"] = False

        # Support either dict or tuple return from your existing function
        if isinstance(result, dict):
            if "step_path" in result and result["step_path"] is not None:
                new_state["step_path"] = str(result["step_path"])
            if "stl_path" in result and result["stl_path"] is not None:
                new_state["stl_path"] = str(result["stl_path"])
        else:
            # assume tuple: (step_path, stl_path)
            step_path, stl_path = result
            if step_path is not None:
                new_state["step_path"] = str(step_path)
            if stl_path is not None:
                new_state["stl_path"] = str(stl_path)

        return new_state

    return _node


def make_repair_partspec_node(llm):
    """
    Repairs PartSpec using validation errors + original user request.

    Uses function calling method to avoid OpenAI structured-output schema constraints
    (especially if your model includes Any/JSONValue types).
    """
    deterministic_llm = llm.bind(temperature=0)
    structured_llm = deterministic_llm.with_structured_output(PartSpec, method="function_calling")

    def _node(state):
        msgs = state.get("messages", [])
        user_request = latest_human_text(msgs)

        spec = state.get("parts_spec")
        errors = state.get("validation_errors", [])

        if not spec:
            raise ValueError("Missing state['parts_spec'] for repair.")
        if not errors:
            # Nothing to repair; no-op
            return state

        # Keep the input compact and deterministic
        repair_input = {
            "user_request": user_request,
            "current_parts_spec": spec,
            "validation_errors": errors,
            "repair_rules": {
                "minimize_changes": True,
                "prefer_clarifications_over_guessing": True
            }
        }

        llm_messages = [
            ("system", partspec_repair_prompt.PARTSPEC_REPAIR_SYSTEM_PROMPT),
            ("human", json.dumps(repair_input, sort_keys=True)),
        ]

        repaired: PartSpec = structured_llm.invoke(llm_messages)

        repaired_dict = repaired.model_dump()
        repaired_json = json.dumps(repaired_dict, sort_keys=True)

        new_state = dict(state)
        new_state["parts_spec_obj"] = repaired
        new_state["parts_spec"] = repaired_dict
        new_state["parts_spec_json"] = repaired_json

        # increment loop counter
        new_state["repair_attempts"] = int(state.get("repair_attempts", 0)) + 1

        # Optional: append for trace visibility
        new_state["messages"] = msgs + [AIMessage(content=repaired_json)]

        return new_state

    return _node
