from langgraph.graph import StateGraph, END

from graph.nodes import (
    generate_dimensions,
    validate_dimensions,
    cad_generator,
    refine_dimensions
)
from graph.state import CADState


def build_graph():
    workflow = StateGraph(CADState)

    workflow.add_node("generate", generate_dimensions)
    workflow.add_node("validate", validate_dimensions)
    workflow.add_node("cad", cad_generator)
    workflow.add_node("refine", refine_dimensions)

    workflow.set_entry_point("generate")

    workflow.add_edge("generate", "validate")

    workflow.add_conditional_edges(
        "validate",
        lambda s: "ok" if s["validation_status"] == "valid" else "fix",
        {
            "ok": "cad",
            "fix": "generate"
        }
    )

    workflow.add_conditional_edges(
        "cad",
        lambda s: "refine" if "refine" in s["messages"][-1].content.lower() else "end",
        {
            "refine": "refine",
            "end": END
        }
    )

    workflow.add_edge("refine", "cad")

    return workflow.compile()
