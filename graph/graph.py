from __future__ import annotations

from graph.nodes import (
    GraphState,
    make_generate_partspec_node,
    make_compile_export_node,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, END


def build_graph(
        llm: BaseChatModel,
        out_dir: str,
        export_step: bool = True,
        export_stl: bool = True,
):
    """
    Build and compile the LangGraph pipeline:

      Human prompt -> PartSpec (structured) -> compile_and_export -> paths

    Returns:
      compiled graph callable
    """
    spec_node = make_generate_partspec_node(llm)
    compile_node = make_compile_export_node(
        out_dir=out_dir,
        export_step=export_step,
        export_stl=export_stl,
    )

    builder = StateGraph(GraphState)
    builder.add_node("spec", spec_node)
    builder.add_node("compile", compile_node)

    builder.set_entry_point("spec")
    builder.add_edge("spec", "compile")
    builder.add_edge("compile", END)

    return builder.compile()
