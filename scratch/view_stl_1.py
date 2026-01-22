"""
STL Visualizer
Load an STL file and generate multi-view visualization.


Usage
------
- Interactive 3D (default): `python visualize_stl.py model.stl`
- Multi-view mode: `python visualize_stl.py model.stl -m multi`
- Multi-view with save: `python visualize_stl.py model.stl -m multi -o views.png`
- Custom color and no grid: `python visualize_stl.py model.stl --color lightgreen --no-grid`
- High-res output: `python visualize_stl.py model.stl -m multi -o views.png --dpi 200`


In Python code
---------------
```
from visualize_stl import visualize_stl

# Interactive 3D (default)
visualize_stl("model.stl")

# Multi-view with save
visualize_stl("model.stl", mode="multi", output_filepath="views.png")

# Custom styling
visualize_stl("model.stl", color='lightgreen', show_axes=False)

# High-res multi-view
visualize_stl("model.stl", mode="multi", output_filepath="high_res.png", dpi=200)
```
"""

from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import trimesh


def visualize_stl(
        stl_filepath: str,
        mode: str = "3d",
        output_filepath: Optional[str] = None,
        show_axes: bool = True,
        show_grid: bool = True,
        dpi: int = 100,
        fig_size: Tuple[int, int] = (10, 10),
        color: str = 'lightblue',
        edge_color: str = 'darkblue'
):
    """
    Visualize an STL file in 3D interactive mode or multi-view mode.

    Args:
        stl_filepath: Path to the STL file
        mode: "3d" for interactive single view or "multi" for 4-angle subplots
        output_filepath: Path to save image (only for multi mode)
        show_axes: Show axis labels
        show_grid: Show grid lines
        dpi: Output resolution (for saving)
        fig_size: Figure size as (width, height)
        color: Face color of the mesh
        edge_color: Edge color of the mesh

    Examples:
        # Interactive 3D view
        visualize_stl("model.stl")

        # 4-angle view and save
        visualize_stl("model.stl", mode="multi", output_filepath="views.png")

        # Custom styling
        visualize_stl("model.stl", color='lightgreen', show_grid=False)
    """
    # Validate file
    stl_path = Path(stl_filepath)
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_filepath}")

    # Load STL
    print(f"Loading {stl_filepath}...")
    mesh = trimesh.load(stl_filepath)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)

    # Calculate bounds
    max_range = np.ptp(mesh.vertices, axis=0).max() / 2
    mid = mesh.vertices.mean(axis=0)

    if mode.lower() == "3d":
        # Interactive 3D view
        _plot_3d_view(mesh, mid, max_range, fig_size, color, edge_color,
                      show_axes, show_grid)

    elif mode.lower() == "multi":
        # Multi-view subplots
        _plot_multi_view(mesh, mid, max_range, fig_size, color, edge_color,
                         output_filepath, dpi)

    else:
        raise ValueError(f"Invalid mode: {mode}. Choose '3d' or 'multi'")


def _plot_3d_view(mesh, mid, max_range, fig_size, color, edge_color,
                  show_axes, show_grid):
    """Plot interactive 3D view."""
    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor('white')
    ax = fig.add_subplot(111, projection='3d')

    # Plot mesh
    ax.plot_trisurf(
        mesh.vertices[:, 0],
        mesh.vertices[:, 1],
        mesh.vertices[:, 2],
        triangles=mesh.faces,
        color=color,
        edgecolor=edge_color,
        linewidth=0.1,
        alpha=0.9
    )

    # Set bounds
    ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
    ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
    ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

    # Set view angle (isometric)
    ax.view_init(elev=30, azim=45)

    # Styling
    ax.set_facecolor('white')

    if show_axes:
        ax.set_xlabel('X', fontsize=10)
        ax.set_ylabel('Y', fontsize=10)
        ax.set_zlabel('Z', fontsize=10)
    else:
        ax.axis('off')

    if show_grid:
        ax.grid(True, alpha=0.3)

    ax.set_title('Interactive 3D View (drag to rotate)', fontsize=12, fontweight='bold')

    plt.tight_layout()
    print("Displaying interactive 3D view. Use mouse to rotate.")
    plt.show()


def _plot_multi_view(mesh, mid, max_range, fig_size, color, edge_color,
                     output_filepath, dpi):
    """Plot 4-angle multi-view."""
    views = {
        "ISO": {"elev": 30, "azim": 45},
        "FRONT": {"elev": 0, "azim": 0},
        "TOP": {"elev": 90, "azim": 0},
        "SIDE": {"elev": 0, "azim": 90},
    }

    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor('white')

    for idx, (name, angles) in enumerate(views.items(), 1):
        ax = fig.add_subplot(2, 2, idx, projection='3d')

        # Plot mesh
        ax.plot_trisurf(
            mesh.vertices[:, 0],
            mesh.vertices[:, 1],
            mesh.vertices[:, 2],
            triangles=mesh.faces,
            color=color,
            edgecolor=edge_color,
            linewidth=0.1,
            alpha=0.9
        )

        # Set view and bounds
        ax.view_init(elev=angles["elev"], azim=angles["azim"])
        ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
        ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
        ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

        # Styling
        ax.set_facecolor('white')
        ax.axis('off')

        # Add label
        ax.text2D(0.05, 0.95, name, transform=ax.transAxes,
                  fontsize=16, fontweight='bold',
                  verticalalignment='top',
                  bbox=dict(boxstyle='round', facecolor='white',
                            edgecolor='black', alpha=0.8, linewidth=1.5))

    plt.tight_layout()

    if output_filepath:
        plt.savefig(output_filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        print(f"Saved to {output_filepath}")

    plt.show()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Visualize STL files')
    parser.add_argument('stl_file', help='Path to STL file')
    parser.add_argument('-m', '--mode', choices=['3d', 'multi'], default='3d',
                        help='Visualization mode: 3d (interactive) or multi (4 views)')
    parser.add_argument('-o', '--output', help='Output image path (multi mode only)')
    parser.add_argument('--dpi', type=int, default=100, help='DPI for output (default: 100)')
    parser.add_argument('--no-axes', action='store_true', help='Hide axes')
    parser.add_argument('--no-grid', action='store_true', help='Hide grid')
    parser.add_argument('--color', default='lightblue', help='Mesh color')

    args = parser.parse_args()

    try:
        visualize_stl(
            args.stl_file,
            mode=args.mode,
            output_filepath=args.output,
            show_axes=not args.no_axes,
            show_grid=not args.no_grid,
            dpi=args.dpi,
            color=args.color
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Example usage:
    # visualize_stl("model.stl")  # Interactive 3D
    # visualize_stl("model.stl", mode="multi", output_filepath="views.png")
    # visualize_stl("model.stl", color='lightgreen', show_grid=False)

    exit(main())
