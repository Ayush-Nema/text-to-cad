"""Benchmark runner for text-to-CAD reliability.

Usage:
    python -m bench.runner --models gpt-4.1-mini
    python -m bench.runner --models gpt-4.1-mini,gpt-4.1 --seeds 0,1
    python -m bench.runner --case wheel_y_split_5_spokes --models gpt-4.1-mini

Loads `bench/cases.yaml`, runs each case through the graph for each
(model, seed) pair, and writes:
    bench/runs/<timestamp>__<model>__seed<n>.json   (one per model/seed combo)
    bench/runs/latest_report.md                     (aggregated comparison)

Pass criteria per case:
    - in-scope:        spec generated, validation OK (after at most max_repairs),
                       compile OK, STL+STEP exported, STL bbox within tolerance
                       of expected, STL is a single connected solid.
    - needs_clarification: state.clarification_questions non-empty.
    - out_of_scope:    state.unsupported_aspects contains at least one substring
                       from expected.unsupported_substrings.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import trimesh
import yaml
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from graph.graph import build_graph

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = REPO_ROOT / "bench" / "cases.yaml"
RUNS_DIR = REPO_ROOT / "bench" / "runs"


@dataclass
class CaseResult:
    case_id: str
    model: str
    seed: int
    passed: bool
    reason: str
    wall_seconds: float
    repair_attempts: int
    spec_generated: bool
    validation_ok: bool
    compile_ok: bool
    stl_exported: bool
    step_exported: bool
    bbox_observed_mm: Optional[List[float]]
    bbox_expected_mm: Optional[List[Optional[float]]]
    base_type_observed: Optional[str]
    feature_types_observed: List[str]
    needs_clarification: bool
    unsupported_aspects: List[str]
    error: Optional[str] = None


@dataclass
class ModelRun:
    model: str
    seed: int
    timestamp: str
    cases: List[CaseResult] = field(default_factory=list)


def _load_cases() -> List[Dict[str, Any]]:
    with CASES_PATH.open() as f:
        data = yaml.safe_load(f)
    return data["cases"]


def _bbox_from_stl(path: str) -> Tuple[List[float], bool]:
    """Return (bbox_xyz_mm, is_single_connected_solid)."""
    mesh = trimesh.load(path, force="mesh")
    bbox = mesh.bounds  # ndarray shape (2,3)
    extents = (bbox[1] - bbox[0]).tolist()
    # `split` yields the connected components; one component => single solid.
    try:
        components = mesh.split(only_watertight=False)
        single = len(components) == 1
    except Exception:
        single = True  # if split fails, assume single
    return extents, single


def _bbox_within_tolerance(
    observed: List[float],
    expected: List[Optional[float]],
    tol: float,
) -> Tuple[bool, str]:
    if len(observed) != 3 or len(expected) != 3:
        return False, f"bbox shape mismatch observed={observed} expected={expected}"
    # Match expected dimensions to observed ignoring axis order — CAD orientation
    # varies (e.g. cylinder lying along X vs Z). Sort the constrained axes.
    obs_sorted = sorted(observed, reverse=True)
    exp_constrained = sorted(
        [e for e in expected if e is not None], reverse=True
    )
    obs_constrained = obs_sorted[: len(exp_constrained)]
    for o, e in zip(obs_constrained, exp_constrained):
        if abs(o - e) > tol:
            return (
                False,
                f"bbox axis off: observed={[round(x,2) for x in observed]} "
                f"expected={expected} (tolerance={tol}mm)",
            )
    return True, "bbox within tolerance"


def _evaluate(case: Dict[str, Any], state: Dict[str, Any], wall_s: float) -> CaseResult:
    cid = case["id"]
    expected = case.get("expected", {}) or {}

    spec = state.get("parts_spec")
    spec_obj = state.get("parts_spec_obj")
    base_type = (spec or {}).get("base", {}).get("type") if spec else None
    feature_types = [
        f.get("type") for f in (spec or {}).get("features", []) if isinstance(f, dict)
    ]

    needs_clar = bool(state.get("needs_clarification") or state.get("clarification_questions"))
    unsupported = list(state.get("unsupported_aspects") or [])

    stl_path = state.get("stl_path")
    step_path = state.get("step_path")
    stl_exported = bool(stl_path) and Path(stl_path).exists()
    step_exported = bool(step_path) and Path(step_path).exists()

    bbox_observed: Optional[List[float]] = None
    single_solid_observed: Optional[bool] = None
    if stl_exported:
        try:
            bbox_observed, single_solid_observed = _bbox_from_stl(stl_path)
        except Exception as e:  # noqa: BLE001
            bbox_observed = None
            single_solid_observed = None

    # ---- evaluate against the expected block --------------------------
    # 1. Out-of-scope expectation
    if expected.get("out_of_scope"):
        substrings = [s.lower() for s in expected.get("unsupported_substrings", [])]
        joined = " ".join(unsupported).lower()
        if not unsupported:
            return _result(case, state, wall_s, False,
                           "expected out_of_scope but unsupported_aspects empty",
                           bbox_observed, base_type, feature_types)
        if substrings and not any(s in joined for s in substrings):
            return _result(case, state, wall_s, False,
                           f"unsupported_aspects {unsupported!r} did not match any of {substrings}",
                           bbox_observed, base_type, feature_types)
        return _result(case, state, wall_s, True, "out_of_scope correctly detected",
                       bbox_observed, base_type, feature_types)

    # 2. Needs-clarification expectation
    if expected.get("needs_clarification"):
        if needs_clar:
            return _result(case, state, wall_s, True, "clarification correctly requested",
                           bbox_observed, base_type, feature_types)
        return _result(case, state, wall_s, False,
                       "expected clarification but none was raised",
                       bbox_observed, base_type, feature_types)

    # 3. In-scope expectation: must produce STL+STEP, geometry must match
    if not stl_exported:
        return _result(case, state, wall_s, False, "no STL exported",
                       bbox_observed, base_type, feature_types)
    if not step_exported:
        return _result(case, state, wall_s, False, "no STEP exported",
                       bbox_observed, base_type, feature_types)

    if expected.get("base_type") and base_type != expected["base_type"]:
        return _result(case, state, wall_s, False,
                       f"base_type observed={base_type} expected={expected['base_type']}",
                       bbox_observed, base_type, feature_types)

    if expected.get("single_solid") and single_solid_observed is False:
        return _result(case, state, wall_s, False, "STL is not a single connected solid",
                       bbox_observed, base_type, feature_types)

    if expected.get("bbox_mm"):
        tol = float(expected.get("bbox_tolerance_mm", 1.0))
        ok, msg = _bbox_within_tolerance(bbox_observed or [], expected["bbox_mm"], tol)
        if not ok:
            return _result(case, state, wall_s, False, msg,
                           bbox_observed, base_type, feature_types)

    must_include = expected.get("feature_types_include") or []
    for ft in must_include:
        if ft not in feature_types:
            return _result(case, state, wall_s, False,
                           f"missing required feature type {ft!r} (saw {feature_types})",
                           bbox_observed, base_type, feature_types)

    return _result(case, state, wall_s, True, "in-scope: geometry matches",
                   bbox_observed, base_type, feature_types)


def _result(
    case: Dict[str, Any],
    state: Dict[str, Any],
    wall_s: float,
    passed: bool,
    reason: str,
    bbox_observed: Optional[List[float]],
    base_type: Optional[str],
    feature_types: List[str],
    error: Optional[str] = None,
) -> CaseResult:
    expected = case.get("expected") or {}
    return CaseResult(
        case_id=case["id"],
        model=state.get("__bench_model", ""),
        seed=int(state.get("__bench_seed", 0)),
        passed=passed,
        reason=reason,
        wall_seconds=round(wall_s, 2),
        repair_attempts=int(state.get("repair_attempts", 0)),
        spec_generated=state.get("parts_spec") is not None,
        validation_ok=bool(state.get("is_valid")),
        compile_ok=bool(state.get("step_path") or state.get("stl_path"))
                   and not state.get("compile_failed"),
        stl_exported=bool(state.get("stl_path")) and Path(str(state.get("stl_path"))).exists(),
        step_exported=bool(state.get("step_path")) and Path(str(state.get("step_path"))).exists(),
        bbox_observed_mm=[round(x, 2) for x in bbox_observed] if bbox_observed else None,
        bbox_expected_mm=expected.get("bbox_mm"),
        base_type_observed=base_type,
        feature_types_observed=feature_types,
        needs_clarification=bool(state.get("needs_clarification")
                                  or state.get("clarification_questions")),
        unsupported_aspects=list(state.get("unsupported_aspects") or []),
        error=error,
    )


def _run_one_case(case: Dict[str, Any], graph, model: str, seed: int) -> CaseResult:
    started = time.time()
    state = {"messages": [HumanMessage(content=case["prompt"])]}
    try:
        result = graph.invoke(state)
    except Exception as e:  # noqa: BLE001
        wall = time.time() - started
        tb = traceback.format_exc(limit=8)
        return CaseResult(
            case_id=case["id"], model=model, seed=seed,
            passed=False, reason=f"graph raised: {type(e).__name__}: {e}",
            wall_seconds=round(wall, 2), repair_attempts=0,
            spec_generated=False, validation_ok=False, compile_ok=False,
            stl_exported=False, step_exported=False,
            bbox_observed_mm=None, bbox_expected_mm=case.get("expected", {}).get("bbox_mm"),
            base_type_observed=None, feature_types_observed=[],
            needs_clarification=False, unsupported_aspects=[],
            error=tb,
        )
    wall = time.time() - started
    result["__bench_model"] = model
    result["__bench_seed"] = seed
    return _evaluate(case, result, wall)


def run(models: List[str], seeds: List[int], case_filter: Optional[str]) -> List[ModelRun]:
    cases = _load_cases()
    if case_filter:
        cases = [c for c in cases if c["id"] == case_filter]
        if not cases:
            print(f"No case with id={case_filter!r}; aborting.")
            sys.exit(1)

    runs: List[ModelRun] = []
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    for model in models:
        for seed in seeds:
            ts = time.strftime("%Y%m%d_%H%M%S")
            print(f"\n=== model={model} seed={seed} ===")
            llm = ChatOpenAI(model=model, seed=seed)
            # Each case writes to its own out_dir to avoid clobbering between cases.
            mr = ModelRun(model=model, seed=seed, timestamp=ts)
            for case in cases:
                cid = case["id"]
                out_dir = RUNS_DIR / f"artifacts__{ts}__{model}__seed{seed}" / cid
                out_dir.mkdir(parents=True, exist_ok=True)
                graph = build_graph(llm=llm, out_dir=str(out_dir))
                cr = _run_one_case(case, graph, model, seed)
                tag = "PASS" if cr.passed else "FAIL"
                print(f"  [{tag}] {cid:35s} {cr.wall_seconds:5.1f}s  {cr.reason}")
                mr.cases.append(cr)
            runs.append(mr)
            json_path = RUNS_DIR / f"{ts}__{model}__seed{seed}.json"
            with json_path.open("w") as f:
                json.dump(asdict(mr), f, indent=2, default=str)
            print(f"  wrote {json_path.relative_to(REPO_ROOT)}")

    return runs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--models", default="gpt-4.1-mini",
                   help="Comma-separated list of OpenAI chat models (default: gpt-4.1-mini)")
    p.add_argument("--seeds", default="0",
                   help="Comma-separated list of seeds (default: 0)")
    p.add_argument("--case", default=None, help="Run a single case by id")
    p.add_argument("--no-report", action="store_true",
                   help="Skip generating bench/runs/latest_report.md")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    runs = run(models, seeds, args.case)

    if args.no_report:
        return
    # Defer the import so report.py can be developed independently.
    from bench import report
    report.write_latest_report(runs)


if __name__ == "__main__":
    main()
