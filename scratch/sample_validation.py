import ast
import os
import sys
import warnings
from typing import Dict, Any

import cadquery as cq


def validate_cadquery_code(code: str, *, expected_files=("object.stl", "object.step"), warning_free: bool = False,
) -> Dict[str, Any]:
    """
    Validates generated CadQuery Python code.

    Checks (in order):
    1. Python syntax (AST parse)
    2. CadQuery import presence (warning only)
    3. Runtime execution
    4. Presence of `model`
    5. STL / STEP export existence

    Returns a structured result for LangGraph branching.
    """

    # ----------------------------
    # 1. Syntax pre-check (FAST)
    # ----------------------------
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "is_code_valid": False,
            "error": f"SyntaxError at line {e.lineno}: {e.msg}",
            "line": e.lineno,
            "warnings": [],
        }

    # ----------------------------
    # 2. Soft CadQuery import check
    # ----------------------------
    warnings_list = []
    try:
        tree = ast.parse(code)
        has_cq_import = any(
            isinstance(node, (ast.Import, ast.ImportFrom)) and
            (
                    any(
                        alias.name.startswith("cadquery")
                        for alias in getattr(node, "names", [])
                    ) or
                    getattr(node, "module", "").startswith("cadquery")
            )
            for node in ast.walk(tree)
        )
        if not has_cq_import:
            warnings_list.append(
                "CadQuery import not found. Expected: import cadquery as cq"
            )
    except Exception:
        # AST already parsed successfully above; this is defensive
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

    with warnings.catch_warnings(record=True) as runtime_warnings:
        warnings.simplefilter("always")

        try:
            exec(code, exec_globals, exec_locals)
        except Exception as e:
            exc_type, _, exc_tb = sys.exc_info()
            return {
                "is_code_valid": False,
                "error": f"{exc_type.__name__} at line {exc_tb.tb_lineno}: {str(e)}",
                "line": exc_tb.tb_lineno if exc_tb else None,
                "warnings": warnings_list + [str(w.message) for w in runtime_warnings],
            }

    # ----------------------------
    # 5. Validate `model` contract
    # ----------------------------
    model = exec_locals.get("model") or exec_globals.get("model")
    if model is None:
        return {
            "is_code_valid": False,
            "error": "No `model` object was created. The final CAD object must be assigned to `model`.",
            "line": None,
            "warnings": warnings_list,
        }

    # Optional minimal geometry sanity check
    try:
        model.val()
    except Exception:
        return {
            "is_code_valid": False,
            "error": "`model` exists but does not contain valid geometry.",
            "line": None,
            "warnings": warnings_list,
        }

    # ----------------------------
    # 6. Validate exports
    # ----------------------------
    missing_files = [f for f in expected_files if not os.path.exists(f)]
    if missing_files:
        return {
            "is_code_valid": False,
            "error": f"Missing exported files: {missing_files}",
            "line": None,
            "warnings": warnings_list,
        }

    # ----------------------------
    # 7. Final success
    # ----------------------------
    runtime_warning_msgs = [str(w.message) for w in runtime_warnings]
    all_warnings = warnings_list + runtime_warning_msgs

    if warning_free and all_warnings:
        return {
            "is_code_valid": False,
            "error": "Warnings detected but warning_free=True",
            "line": None,
            "warnings": all_warnings,
        }

    return {
        "is_code_valid": True,
        "error": None,
        "line": None,
        "warnings": all_warnings,
    }
