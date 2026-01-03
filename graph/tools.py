from typing import List, Dict

from langchain_core.tools import tool

from manage_vector_db import CadQueryKnowledgeBase


# @tool
def retrieve_cadquery_context(design_instructions: List[str], k_docs: int = 2, k_examples: int = 2) -> Dict[str, str]:
    """
    Retrieve CadQuery documentation and examples to assist code generation.

    Returns formatted context suitable for LLM prompts.
    """

    kb = CadQueryKnowledgeBase()

    retrieved = kb.retrieve(
        design_instructions=design_instructions,
        k_docs=k_docs,
        k_examples=k_examples,
    )

    context = kb.format_context(retrieved)

    return {"rag_context": context}
