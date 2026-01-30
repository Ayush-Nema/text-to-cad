from graph.curate_nodes import (
    make_generate_partspec_node,
    make_repair_partspec_node,
    make_compile_export_node,
)
from graph.nodes.validate_dims_schema import make_validate_partspec_node
from graph.state import GraphState
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, END


def build_graph(
        llm: BaseChatModel,
        out_dir: str = "out",
        export_step: bool = True,
        export_stl: bool = True,
        max_repairs: int = 3,
):
    spec_node = make_generate_partspec_node(llm)
    validate_node = make_validate_partspec_node()
    repair_node = make_repair_partspec_node(llm)
    compile_node = make_compile_export_node(
        out_dir=out_dir,
        export_step=export_step,
        export_stl=export_stl,
    )

    builder = StateGraph(GraphState)  # noqa

    builder.add_node("spec", spec_node)
    builder.add_node("validate", validate_node)
    builder.add_node("repair", repair_node)
    builder.add_node("compile", compile_node)

    builder.set_entry_point("spec")

    builder.add_edge("spec", "validate")

    # Routing after validate
    def route_after_validate(state: GraphState) -> str:
        # If the model asked clarifying questions, stop (or route to a "clarify" node later)
        if state.get("needs_clarification"):
            return "end"

        # If valid, compile
        if state.get("is_valid"):
            return "compile"

        # If invalid and retries left, repair
        attempts = int(state.get("repair_attempts", 0))
        if attempts < max_repairs:
            return "repair"

        # Out of retries
        return "end"

    # IMPORTANT: provide a path_map so LangGraph knows which nodes exist.
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        path_map={
            "compile": "compile",
            "repair": "repair",
            "end": END,
        },
    )

    # Loop edge
    builder.add_edge("repair", "validate")

    # Finish
    builder.add_edge("compile", END)

    return builder.compile()
