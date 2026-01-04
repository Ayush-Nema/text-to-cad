import ast
import os
import sys
import warnings
from typing import Any

import cadquery as cq
from graph.state import CodeInsights


def validate_cadquery_code(code: str) -> CodeInsights:
    """
    Validates LLM-generated CadQuery Python code.

    Checks:
    1. Python syntax (AST parse)
    2. CadQuery import presence (warning only)
    3. Runtime execution
    4. Presence of `model`
    5. `.val()` geometry sanity check
    6. STL / STEP file existence

    Returns a structured dict with keys:
    is_code_valid, error_stack, line_no, warning_msgs
    """

    expected_files = ("object.stl", "object.step")
    warning_msgs = []

    # ----------------------------
    # 1. Syntax pre-check
    # ----------------------------
    try:
        ast.parse(code)
    except SyntaxError as e:
        return CodeInsights(
            is_code_valid=False,
            error_stack=f"SyntaxError at line {e.lineno}: {e.msg}",
            line_no=e.lineno,
            warning_msgs=warning_msgs,
        )

    # ----------------------------
    # 2. Soft CadQuery import check
    # ----------------------------
    try:
        tree = ast.parse(code)
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
            exec(code, exec_globals, exec_locals)
            runtime_warnings.extend([str(warn.message) for warn in w])
        except Exception as e:
            exc_type, _, exc_tb = sys.exc_info()
            return CodeInsights(
                is_code_valid=False,
                error_stack=f"{exc_type.__name__} at line {exc_tb.tb_lineno}: {str(e)}",
                line_no=exc_tb.tb_lineno if exc_tb else None,
                warning_msgs=warning_msgs + runtime_warnings,
            )

    # ----------------------------
    # 5. Validate `model` contract
    # ----------------------------
    model: Any = exec_locals.get("model") or exec_globals.get("model")
    if model is None:
        return CodeInsights(
            is_code_valid=False,
            error_stack="No `model` object was created. The final CAD object must be assigned to `model`.",
            line_no=None,
            warning_msgs=warning_msgs + runtime_warnings,
        )

    # Safe .val() geometry check
    if not hasattr(model, "val"):
        return CodeInsights(
            is_code_valid=False,
            error_stack="`model` exists but does not have a `.val()` method (invalid geometry).",
            line_no=None,
            warning_msgs=warning_msgs + runtime_warnings,
        )

    # Optional: trigger .val() to catch runtime CAD errors
    try:
        model.val()
    except Exception as e:
        return CodeInsights(
            is_code_valid=False,
            error_stack=f"Geometry error in `model.val()`: {str(e)}",
            line_no=None,
            warning_msgs=warning_msgs + runtime_warnings,
        )

    # ----------------------------
    # 6. Validate exports
    # ----------------------------
    missing_files = [f for f in expected_files if not os.path.exists(f)]
    if missing_files:
        return CodeInsights(
            is_code_valid=False,
            error_stack=f"Missing exported files: {missing_files}",
            line_no=None,
            warning_msgs=warning_msgs + runtime_warnings,
        )

    all_warnings = warning_msgs + runtime_warnings

    # ----------------------------
    # Success
    # ----------------------------
    # return {
    #     "is_code_valid": True,
    #     "error_stack": None,
    #     "line_no": None,
    #     "warning_msgs": all_warnings,
    # }
    return CodeInsights(
        is_code_valid=True,
        error_stack=None,
        line_no=None,
        warning_msgs=all_warnings,
    )
