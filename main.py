from __future__ import annotations

import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from graph.graph import build_graph

load_dotenv()


def main() -> None:
    # ---- Minimal config ----------------------
    model = "gpt-4.1-mini"
    out_dir = "output"
    export_step = True
    export_stl = True
    print_spec = True
    # ------------------------------------------

    prompt = input("Enter CAD prompt: ").strip()
    if not prompt:
        print("No prompt provided. Exiting.")
        return

    llm = ChatOpenAI(model=model)
    graph = build_graph(
        llm=llm,
        out_dir=out_dir,
        export_step=export_step,
        export_stl=export_stl,
    )

    state = {"messages": [HumanMessage(content=prompt)]}
    result = graph.invoke(state)

    if print_spec and "parts_spec" in result:
        print("\n=== PartSpec ===")
        print(json.dumps(result["parts_spec"], indent=2))

    if result.get("needs_clarification"):
        print("\n=== Clarifications Needed ===")
        for q in result.get("clarification_questions", []):
            print(f"- {q.get('question')}")
            opts = q.get("options") or []
            if opts:
                print("  options:", opts)

    print("\n=== Output ===")
    print("STEP:", result.get("step_path"))
    print("STL :", result.get("stl_path"))


if __name__ == "__main__":
    main()
