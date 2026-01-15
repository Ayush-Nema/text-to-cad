import ast
import os
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any

import cadquery as cq
from graph.data_models import DesignInstructions
from graph.state import CodeInsights
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from utils.utils import parse_json, strip_markdown_code_fences, load_and_format_prompt
from vector_db import setup_or_initialize_kb


# from rich.traceback import install
# install()

def extract_human_message(state):
    return state


def get_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = load_and_format_prompt("prompts/prompt_to_dims.md")

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("messages")  # pulls messages from state automatically
    ])
    chain = prompt | llm

    # invoke the chain with current messages
    response = chain.invoke({"messages": state["messages"]})
    # parse JSON output
    args = parse_json(response)

    print("Finished processing `get_dimensions` node")

    return {
        "dimensions": args,  # new field in state
        "messages": [AIMessage(content=str(args))]  # reducer will append this automatically
    }


def validate_dimensions(state):
    # todo: add more validation logics here
    # todo: ask LLM whether these dims looks realistic or not. extract dims if present in the prompt else generate
    data = state.get("dimensions", {})

    if "object_type" not in data:
        state["validation_status"] = "invalid"
        state["messages"] += [AIMessage(content="Missing object_type")]
        return state

    state["validation_status"] = "valid"
    return state


def get_design_instructions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    ).with_structured_output(DesignInstructions)

    system_prompt = load_and_format_prompt("prompts/design_instructions.md")

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("messages")  # pull prior messages from state
    ])

    chain = prompt | llm
    design_obj: DesignInstructions = chain.invoke({"messages": state["messages"]})

    return {
        "design_instructions": design_obj.design_instructions,
        "object_name": design_obj.object_name,
        "object_summary": design_obj.summary,
        "messages": [AIMessage(content=design_obj.model_dump_json())],  # reducer appends
    }


def retrieve_context(state):
    """
    Retrieve CadQuery documentation and examples to assist code generation.
    Returns formatted context suitable for LLM prompts.
    """
    # todo: [optional] create a "tool" for open internet search using Tavilly or SerpAPi API
    kb = setup_or_initialize_kb(examples_dir="../cadquery_info/cq_examples",
                                pdf_path="../cadquery_info/cadquery-readthedocs-io-en-latest.pdf",
                                force_reingest=False)

    k_docs, k_examples = 1, 1
    retrieved = kb.retrieve(
        design_instructions=state["design_instructions"],
        k_docs=k_docs,
        k_examples=k_examples,
    )

    context = kb.format_context(retrieved)
    return {"cadquery_context": context}


def generate_cad_program(state):
    llm = ChatOpenAI(model="gpt-4.1", temperature=0.0)

    # determine prompt and variables based on state
    if state.get('is_code_valid', None) is False:  # represents flow for Code failure
        prompt_path = "prompts/cad_code_validation.md"
        variables = {
            "cadquery_program": state["cadquery_program"],
            "error_stack": state["code_insights"]["error_stack"],
            "line_no": state["code_insights"]["line_no"],
            "warning_msgs": state["code_insights"]["warning_msgs"],
        }

    elif state.get('is_review_passed', None) is False:  # represents flow for Review failure
        prompt_path = "prompts/cad_review_fix.md"
        variables = {
            "previous_code": state["generated_code"],
            "review_feedback": state["review_feedback"],
            # todo: ... other variables for this case
        }

    else:
        prompt_path = "prompts/cad_generation.md"
        variables = {
            "docs_and_exs": state["cadquery_context"],
            "dimensions": state["dimensions"],
            "design_instructions": "\n".join(
                f"{i + 1}. {step}"
                for i, step in enumerate(state["design_instructions"])
            ),
        }

    # Single chain creation and invocation
    system_prompt = load_and_format_prompt(prompt_path)
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt)])
    chain = prompt | llm
    response = chain.invoke(variables)

    generated_prog: str = strip_markdown_code_fences(response.content)
    print(f"Exiting generated_cad_program node with this code: \n{generated_prog}", end="\n==============\n")

    return {

        "cadquery_program": generated_prog,
    }


def validate_program(state):
    prog = state.get("cadquery_program")

    expected_files = ("object.stl", "object.step")
    warning_msgs = []

    # ----------------------------
    # 1. Syntax pre-check
    # ----------------------------
    try:
        ast.parse(prog)
    except SyntaxError as e:
        print(f"SyntaxError at line {e.lineno}: {e.msg}")
        return {
            "is_code_valid": False,
            "code_insights": CodeInsights(
                error_stack=f"SyntaxError at line {e.lineno}: {e.msg}",
                line_no=e.lineno,
                warning_msgs=warning_msgs,
            )}

    # ----------------------------
    # 2. Soft CadQuery import check
    # ----------------------------
    try:
        tree = ast.parse(prog)
        has_cq_import = any(
            isinstance(node, (ast.Import, ast.ImportFrom)) and
            (
                    any(
                        getattr(alias, "name", "").startswith("cadquery")
                        for alias in getattr(node, "names", [])
                    ) or
                    getattr(node, "module", "").startswith("cadquery")
            )
            for node in ast.walk(tree)
        )
        if not has_cq_import:
            warning_msgs.append(
                "CadQuery import not found. Expected: import cadquery as cq"
            )
    except Exception:  # type: ignore
        # Defensive, ignore
        pass

    # ----------------------------
    # 3. Cleanup previous outputs
    # ----------------------------
    for f in expected_files:
        if os.path.exists(f):
            os.remove(f)

    # ----------------------------
    # 4. Execute code safely
    # ----------------------------
    exec_globals = {
        "__builtins__": __builtins__,
        "cq": cq,
    }
    exec_locals = {}

    runtime_warnings = []
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            exec(prog, exec_globals)
            runtime_warnings.extend([str(warn.message) for warn in w])
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            # Walk the traceback to the frame inside the executed code
            tb = exc_tb
            while tb.tb_next is not None:
                tb = tb.tb_next
            # Get the line number in the executed string
            lineno = tb.tb_lineno
            # Extract the actual line from the string
            line = prog.splitlines()[lineno - 1] if lineno <= len(prog.splitlines()) else "<line not found>"
            print(f"{exc_type.__name__} at line {lineno}: `{line.strip()}`\nError message: {exc_value}")
            return {
                "is_code_valid": False,
                "code_insights": CodeInsights(
                    error_stack=f"{exc_type.__name__} at line {lineno}: `{line.strip()}`\nError message: {exc_value}",
                    line_no=lineno,
                    warning_msgs=warning_msgs + runtime_warnings,
                )}

    # ----------------------------
    # 5. Validate `model` contract
    # ----------------------------
    model: Any = exec_locals.get("model") or exec_globals.get("model")
    if model is None:
        print("No `model` object was created. The final CAD object must be assigned to `model`.")
        return {
            "is_code_valid": False,
            "code_insights": CodeInsights(
                error_stack="No `model` object was created. The final CAD object must be assigned to `model`.",
                line_no=None,
                warning_msgs=warning_msgs + runtime_warnings,
            )}

    # Safe .val() geometry check
    if not hasattr(model, "val"):
        print("`model` exists but does not have a `.val()` method (invalid geometry).")
        return {
            "is_code_valid": False,
            "code_insights": CodeInsights(
                error_stack="`model` exists but does not have a `.val()` method (invalid geometry).",
                line_no=None,
                warning_msgs=warning_msgs + runtime_warnings,
            )}

    # Optional: trigger .val() to catch runtime CAD errors
    try:
        model.val()
    except Exception as e:
        print(f"Geometry error in `model.val()`: {str(e)}")
        return {
            "is_code_valid": False,
            "code_insights": CodeInsights(
                error_stack=f"Geometry error in `model.val()`: {str(e)}",
                line_no=None,
                warning_msgs=warning_msgs + runtime_warnings,
            )}

    # ----------------------------
    # 6. Validate exports
    # ----------------------------
    missing_files = [f for f in expected_files if not os.path.exists(f)]
    if missing_files:
        print(f"Missing exported files: {missing_files}")
        return {
            "is_code_valid": False,
            "code_insights": CodeInsights(
                error_stack=f"Missing exported files: {missing_files}",
                line_no=None,
                warning_msgs=warning_msgs + runtime_warnings,
            )
        }

    all_warnings = warning_msgs + runtime_warnings

    # Success
    return {
        "is_code_valid": True,
        "code_insights": CodeInsights(
            error_stack=None,
            line_no=None,
            warning_msgs=all_warnings,
        )
    }


def exporter():
    output_dir = "output"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    source_files = ["object.stl", "object.step"]
    exported_files = {}

    for filename in source_files:
        src = Path(filename)
        if src.exists():
            dest = output_path / filename
            shutil.move(src, dest)
            exported_files[src.suffix.lstrip(".")] = str(dest)

    return {"exported_files": exported_files}


def design_critique(state):
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

    return state
