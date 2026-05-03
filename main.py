from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from graph.graph import build_graph

load_dotenv()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Text-to-CAD: prompt -> deterministic PartSpec -> STEP/STL")
    p.add_argument("--model", default="gpt-4.1-mini",
                   help="OpenAI chat model (default: gpt-4.1-mini)")
    p.add_argument("--seed", type=int, default=0,
                   help="Sampling seed forwarded to OpenAI for reproducibility (default: 0)")
    p.add_argument("--prompt", default=None,
                   help="CAD prompt. If omitted, reads one line from stdin.")
    p.add_argument("--out-dir", default="output",
                   help="Where STEP/STL exports are written (default: output)")
    p.add_argument("--no-step", action="store_true", help="Skip STEP export")
    p.add_argument("--no-stl", action="store_true", help="Skip STL export")
    p.add_argument("--print-spec", action="store_true", default=True,
                   help="Print the generated PartSpec JSON")
    p.add_argument("--no-print-spec", dest="print_spec", action="store_false")
    return p.parse_args()


def _print_failure(result: dict) -> None:
    """Pretty-print scope/clarification/repair-failure states uniformly."""
    unsupported = result.get("unsupported_aspects") or []
    alternatives = result.get("suggested_alternatives") or []
    clarifications = result.get("clarification_questions") or []

    if unsupported:
        print("\n=== Cannot fulfill this request ===")
        print("What's outside the supported set:")
        for item in unsupported:
            print(f"  - {item}")
        if alternatives:
            print("\nWhat I can produce instead:")
            for item in alternatives:
                print(f"  - {item}")

    if clarifications:
        print("\n=== Clarifications needed before I can proceed ===")
        for q in clarifications:
            print(f"  - {q.get('question')}")
            opts = q.get("options") or []
            if opts:
                print(f"    options: {opts}")


def main() -> None:
    args = _parse_args()

    if args.prompt is not None:
        prompt = args.prompt.strip()
    else:
        prompt = input("Enter CAD prompt: ").strip()
    if not prompt:
        print("No prompt provided. Exiting.")
        return

    # `seed` is forwarded by langchain-openai to OpenAI's `seed` request param.
    # Combined with temperature=0 (pinned in graph/curate_nodes.py) this gives
    # repeatable PartSpec output for the benchmark harness.
    llm = ChatOpenAI(model=args.model, seed=args.seed)
    graph = build_graph(
        llm=llm,
        out_dir=args.out_dir,
        export_step=not args.no_step,
        export_stl=not args.no_stl,
    )

    state = {"messages": [HumanMessage(content=prompt)]}
    result = graph.invoke(state)

    if args.print_spec and "parts_spec" in result:
        print("\n=== PartSpec ===")
        print(json.dumps(result["parts_spec"], indent=2))

    _print_failure(result)

    print("\n=== Output ===")
    print("STEP:", result.get("step_path"))
    print("STL :", result.get("stl_path"))

    # Non-zero exit if no artifact was produced (so benchmark/runner can detect failures).
    if result.get("step_path") is None and result.get("stl_path") is None:
        sys.exit(2)


if __name__ == "__main__":
    main()
