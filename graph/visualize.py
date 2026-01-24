import subprocess

from dotenv import load_dotenv
from graph.graph import build_graph
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_openai import ChatOpenAI

load_dotenv()


def main():
    # only need these to CONSTRUCT the graph (not run it).
    llm = ChatOpenAI(model="gpt-4.1-mini")
    out_dir = "output"

    graph = build_graph(
        llm=llm,
        out_dir=out_dir,
        export_step=True,
        export_stl=True,
    )

    img_bytes = graph.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)

    with open("graph.png", "wb") as f:
        f.write(img_bytes)

    subprocess.run(["open", "graph.png"])  # macOS


if __name__ == "__main__":
    main()
