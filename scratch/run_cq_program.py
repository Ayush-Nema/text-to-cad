"""
CadQuery Code Visualizer
Paste your CadQuery code and visualize the result in 3D.
"""

import cadquery as cq
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import tempfile
import os


def visualize_cadquery_code(code: str, rotate: bool = True):
    """
    Execute CadQuery code and visualize the resulting model.

    Args:
        code: CadQuery Python code string
        rotate: If True, show interactive rotating view
    """
    # Execute the code
    exec_globals = {
        "__builtins__": __builtins__,
        "cq": cq,
    }

    try:
        exec(code, exec_globals)
    except Exception as e:
        print(f"Error executing code: {e}")
        return

    # Get the model object
    model = exec_globals.get("model")
    if model is None:
        print("Error: No 'model' variable found. Make sure you assign your final object to 'model'.")
        return

    # Export to temporary STL file
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        temp_stl = tmp.name

    try:
        cq.exporters.export(model, temp_stl)

        # Load and visualize
        import trimesh
        mesh = trimesh.load(temp_stl)

        # Create figure
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')

        # Plot mesh
        ax.plot_trisurf(
            mesh.vertices[:, 0],
            mesh.vertices[:, 1],
            mesh.vertices[:, 2],
            triangles=mesh.faces,
            color='lightblue',
            edgecolor='darkblue',
            linewidth=0.2,
            alpha=0.9
        )

        # Set equal aspect ratio
        max_range = np.ptp(mesh.vertices, axis=0).max() / 2
        mid = mesh.vertices.mean(axis=0)
        ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
        ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
        ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

        # Styling
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title('CadQuery Model Visualization')

        # Set view angle
        ax.view_init(elev=30, azim=45)

        if rotate:
            # Add rotation animation
            for angle in range(0, 360, 2):
                ax.view_init(elev=30, azim=angle)
                plt.draw()
                plt.pause(0.01)
        else:
            plt.show()

    finally:
        # Cleanup
        if os.path.exists(temp_stl):
            os.remove(temp_stl)


def main():
    print("=" * 60)
    print("CadQuery Code Visualizer")
    print("=" * 60)
    print("Paste your CadQuery code below.")
    print("The code must assign the final object to a variable named 'model'.")
    print("Type 'END' on a new line when finished.")
    print("=" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    code = "\n".join(lines)

    if not code.strip():
        print("No code provided.")
        return

    print("\nExecuting code...")
    visualize_cadquery_code(code, rotate=False)


if __name__ == "__main__":
    # Example usage - comment out main() and uncomment below to test
    # example_code = """
    # import cadquery as cq
    #
    # model = (
    #     cq.Workplane("XY")
    #     .box(10, 10, 10)
    #     .faces(">Z")
    #     .hole(3)
    # )
    # """
    # visualize_cadquery_code(example_code, rotate=False)

    main()
