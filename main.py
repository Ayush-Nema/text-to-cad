"""
- python -m graph.visualize
- python -m main

example_prompt: screw 24mm long with circular top and threads
"""

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph.graph import build_graph

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
    print("▶︎ Design dimensions: ", result.get("dimension_json"))
    print("▶︎ Design instructions: ", result.get("design_instructions"))
    print("\n")

    # state updates propagate automatically
    state = result
