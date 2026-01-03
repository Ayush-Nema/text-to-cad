"""
- python -m graph.visualize
- python -m run

example_prompts:
1. screw 24mm long with circular top and threads
2. a car wheel with 250mm diameter and 5 spokes. There should a hole in the center with 15mm diameter
"""

from dotenv import load_dotenv
from graph.graph import build_graph
from langchain_core.messages import HumanMessage

load_dotenv(".env")

graph = build_graph()
state = {"messages": []}

while True:
    user = input("User: ")

    if user == "exit":
        break

    state["messages"] += [HumanMessage(content=user)]
    result = graph.invoke(state)

    # print(result.keys())
    print("▶︎ Design dimensions: \n", result.get("dimension_json"))
    print("-----------")
    print("▶︎ Design instructions: \n", result.get("design_instructions"))
    print("-----------")
    print("▶︎ Program: \n", result.get("cadquery_program"))
    print("\n")

    # state updates propagate automatically
    state = result
