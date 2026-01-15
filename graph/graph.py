from graph.nodes import (
    extract_human_message,
    get_dimensions,
    validate_dimensions,
    get_design_instructions,
    retrieve_context,
    generate_cad_program,
    validate_program,
    design_critique
)
from graph.state import CADState
from langgraph.graph import StateGraph, END, START


def build_graph():
    workflow = StateGraph(CADState)

    workflow.add_node("extract_human_msg", extract_human_message)
    workflow.add_node("get_dimensions", get_dimensions)
    workflow.add_node("validate_dimensions", validate_dimensions)
    workflow.add_node("get_design_instructions", get_design_instructions)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_cad_program", generate_cad_program)
    workflow.add_node("validate_program", validate_program)
    workflow.add_node("design_critique", design_critique)

    # workflow.set_entry_point("get_dimensions")
    workflow.add_edge(START, "get_dimensions")
    workflow.add_edge(START, "extract_human_msg")

    workflow.add_edge("get_dimensions", "validate_dimensions")

    workflow.add_conditional_edges(
        "validate_dimensions",
        lambda s: "ok" if s["validation_status"] == "valid" else "fix",
        {
            "ok": "get_design_instructions",
            "fix": "get_dimensions"
        }
    )

    workflow.add_edge("get_design_instructions", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_cad_program")
    workflow.add_edge("generate_cad_program", "validate_program")

    workflow.add_conditional_edges(
        "validate_program",
        lambda s: "ok" if s["is_code_valid"] else "feedback",
        {
            "ok": "design_critique",
            "feedback": "generate_cad_program"
        }
    )

    workflow.add_conditional_edges(
        "design_critique",
        lambda s: "ok" if s["design_review_status"] == "valid" else "feedback",
        {
            "ok": END,
            "feedback": "generate_cad_program"
        }
    )

    return workflow.compile()


class BuildGraph:
    def __init__(self, state):
        self.workflow = StateGraph(state)

        self.workflow.add_node("get_dimensions", get_dimensions)
        self.workflow.add_node("validate_dimensions", validate_dimensions)
        self.workflow.add_node("get_design_instructions", get_design_instructions)
        self.workflow.add_node("refine", validate_program)

        self.workflow.set_entry_point("get_dimensions")

    def build_graph_1(self):
        self.workflow.add_edge("get_dimensions", "validate_dimensions")

        self.workflow.add_conditional_edges(
            "validate_dimensions",
            lambda s: "ok" if s["validation_status"] == "valid" else "fix",
            {
                "ok": "get_design_instructions",
                "fix": "get_dimensions"
            }
        )

        self.workflow.add_conditional_edges(
            "get_design_instructions",
            lambda s: "refine" if "refine" in s["messages"][-1].content.lower() else "end",
            {
                "refine": "refine",
                "end": END
            }
        )

        self.workflow.add_edge("refine", "get_design_instructions")

        return self.workflow.compile()
