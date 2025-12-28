import subprocess

from langchain_core.runnables.graph import MermaidDrawMethod

from graph.graph import build_graph

graph = build_graph()

# Generate the PNG image bytes
img_bytes = graph.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)

# Save the image to a file
with open('graph.png', 'wb') as f:
    f.write(img_bytes)

# Optionally, open the image using the default image viewer (macOS)
subprocess.run(['open', 'graph.png'])
