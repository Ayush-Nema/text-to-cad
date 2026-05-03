"""Aggregate bench/runs/*.json into a markdown comparison table."""
from __future__ import annotations

import json
from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "bench" / "runs"
LATEST_REPORT = RUNS_DIR / "latest_report.md"


def _load_run_jsons() -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    for p in sorted(RUNS_DIR.glob("*.json")):
        with p.open() as f:
            runs.append(json.load(f))
    return runs


def write_latest_report(runs_in: Any = None) -> Path:
    """Write a markdown comparison table.

    Pulls the most recent run per (model, seed) combo from `bench/runs/*.json`
    so that re-runs of a single model don't lose comparison context with prior
    runs of other models. If `runs_in` is provided (list of ModelRun
    dataclasses or dicts), include those in the aggregation as well.
    """
    runs: List[Dict[str, Any]] = _load_run_jsons()
    if runs_in:
        runs.extend([asdict(r) if is_dataclass(r) else r for r in runs_in])

    # Keep only the most recent run per (model, seed)
    latest: Dict[tuple, Dict[str, Any]] = {}
    for r in runs:
        key = (r["model"], r["seed"])
        prev = latest.get(key)
        if prev is None or r["timestamp"] > prev["timestamp"]:
            latest[key] = r

    if not latest:
        LATEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
        LATEST_REPORT.write_text("No bench runs found.\n")
        return LATEST_REPORT

    # Collect the case ids in stable order from any one run
    columns = sorted(latest.keys(), key=lambda k: (k[0], k[1]))
    case_order: List[str] = []
    seen = set()
    for col in columns:
        for c in latest[col]["cases"]:
            if c["case_id"] not in seen:
                seen.add(c["case_id"])
                case_order.append(c["case_id"])

    # Build table
    lines: List[str] = []
    lines.append("# Text-to-CAD Benchmark — latest results\n")
    lines.append("Cell format: `PASS/FAIL  Ns  rN`  (wall seconds, repair attempts).\n")
    lines.append("")

    # Header
    header = ["Case"] + [f"{m} (seed {s})" for m, s in columns]
    sep = ["---"] * len(header)
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    # Body
    totals: Dict[tuple, Dict[str, int]] = {col: {"pass": 0, "total": 0} for col in columns}
    for cid in case_order:
        row = [cid]
        for col in columns:
            run = latest[col]
            cell_case = next((c for c in run["cases"] if c["case_id"] == cid), None)
            if cell_case is None:
                row.append("—")
                continue
            tag = "✅PASS" if cell_case["passed"] else "❌FAIL"
            row.append(f"{tag}  {cell_case['wall_seconds']}s  r{cell_case['repair_attempts']}")
            totals[col]["total"] += 1
            if cell_case["passed"]:
                totals[col]["pass"] += 1
        lines.append("| " + " | ".join(row) + " |")

    # Totals row
    totals_row = ["**TOTAL**"]
    for col in columns:
        t = totals[col]
        rate = (100.0 * t["pass"] / t["total"]) if t["total"] else 0.0
        totals_row.append(f"**{t['pass']}/{t['total']} ({rate:.0f}%)**")
    lines.append("| " + " | ".join(totals_row) + " |")

    # Failure detail section
    lines.append("")
    lines.append("## Failure details")
    lines.append("")
    any_failures = False
    for col in columns:
        run = latest[col]
        fails = [c for c in run["cases"] if not c["passed"]]
        if not fails:
            continue
        any_failures = True
        lines.append(f"### {col[0]} (seed {col[1]})")
        for c in fails:
            lines.append(f"- **{c['case_id']}** — {c['reason']}")
            if c.get("error"):
                lines.append("  ```")
                for ln in str(c["error"]).splitlines()[:6]:
                    lines.append(f"  {ln}")
                lines.append("  ```")
        lines.append("")
    if not any_failures:
        lines.append("None — all passing.\n")

    LATEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LATEST_REPORT.write_text("\n".join(lines))
    print(f"\nReport written to {LATEST_REPORT.relative_to(REPO_ROOT)}")
    return LATEST_REPORT


if __name__ == "__main__":
    write_latest_report()
