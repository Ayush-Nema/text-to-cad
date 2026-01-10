import ast
import os
import sys
import warnings
from typing import Any

import cadquery as cq
from graph.data_models import DesignInstructions
from graph.state import CodeInsights
from graph.tools import retrieve_cadquery_context
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from utils.utils import load_md, parse_json, strip_markdown_code_fences


# from rich.traceback import install
# install()

def extract_human_message(state):
    return state


def get_dimensions(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    )

    system_prompt = load_md("prompts/prompt_to_dims.md")

    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    response = llm.invoke(input=messages)

    # Parse JSON output from LLM
    args = parse_json(response)

    print("Exiting `get_dimensions` node")
    return {
        **state,
        "dimensions": args,
        "messages": state["messages"] + [AIMessage(content=str(args))]
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
    """
    """
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0
    ).with_structured_output(DesignInstructions)

    system_prompt = load_md("prompts/design_instructions.md")
    messages = [{"role": "system", "content": system_prompt}]
    messages += state["messages"]

    # Invoke LLM — returns a DesignInstructions object, NOT a string
    # todo: currently, `messages` is a list of all messages. Undesirable. Format the prompt.
    # todo: `messages` should contain state.dimensions and state.humanMessages
    design_obj: DesignInstructions = llm.invoke(messages)

    # Update the state
    state["design_instructions"] = design_obj.design_instructions
    state["object_name"] = design_obj.object_name
    state["object_summary"] = design_obj.summary

    return {
        **state,
        "messages": state["messages"] + [AIMessage(content=design_obj.model_dump_json())],
    }


def generate_cad_program(state):
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0.0,
    )
    # llm_with_tools = llm.bind_tools([retrieve_cadquery_context])
    docs_and_exs = retrieve_cadquery_context(state["design_instructions"])

    system_prompt = load_md("prompts/cad_generation.md")
    prompt = system_prompt.format(
        docs_and_exs=docs_and_exs,
        dimensions=state["dimensions"],
        design_instructions="\n".join(
            f"{i + 1}. {step}"
            for i, step in enumerate(state["design_instructions"])
        ),
    )

    response = llm.invoke([{"role": "system", "content": prompt}])
    generated_prog: str = strip_markdown_code_fences(response.content)
    print(f"Exiting generated_cad_program node with this code: \n{generated_prog}", end="\n==============\n")

    return {
        **state,
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
            **state,
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
            exec(prog, exec_globals, exec_locals)
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
                **state,
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
            **state,
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
            **state,
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
            **state,
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
            **state,
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
        **state,
        "is_code_valid": True,
        "code_insights": CodeInsights(
            error_stack=None,
            line_no=None,
            warning_msgs=all_warnings,
        )
    }


def design_critique(state):
    return state
