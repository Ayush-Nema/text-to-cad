"""
Generate screenshots of an object in STL file from 4 different angles
"""

from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from trimesh import Trimesh


def load_stl(filepath: str) -> Trimesh:
    """Load STL file and return trimesh object."""
    mesh: Trimesh = trimesh.load(filepath)
    return mesh


def get_view_angles() -> Dict[str, Dict[str, float]]:
    """Define camera positions for different views."""
    return {
        "ISO": {"elev": 30, "azim": 45},
        "FRONT": {"elev": 0, "azim": 0},
        "TOP": {"elev": 90, "azim": 0},
        "SIDE": {"elev": 0, "azim": 90},
    }


def calculate_bounds(mesh: Trimesh) -> Tuple[float, np.ndarray]:
    """Calculate equal aspect ratio limits for the mesh."""
    max_range = np.ptp(mesh.vertices, axis=0).max() / 2
    mid = mesh.vertices.mean(axis=0)
    return max_range, mid


def plot_mesh_view(ax, mesh: Trimesh, angles: Dict[str, float],
                   max_range: float, mid: np.ndarray, view_name: str):
    """Plot a single mesh view on the given axes."""
    # Plot the mesh
    ax.plot_trisurf(
        mesh.vertices[:, 0],
        mesh.vertices[:, 1],
        mesh.vertices[:, 2],
        triangles=mesh.faces,
        color='lightgray',
        edgecolor='black',
        linewidth=0.1,
        alpha=0.9
    )

    # Set view angle
    ax.view_init(elev=angles["elev"], azim=angles["azim"])

    # Set equal aspect ratio
    ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
    ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
    ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

    # Set background
    ax.set_facecolor('white')

    # Remove axes
    ax.axis('off')

    # Add border around subplot
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_edgecolor('black')

    # Add text label inside the subplot (top-left corner)
    ax.text2D(0.05, 0.95, view_name, transform=ax.transAxes,
              fontsize=18, fontweight='bold',
              verticalalignment='top',
              bbox=dict(boxstyle='round', facecolor='white',
                        edgecolor='black', alpha=0.8, linewidth=1.5))


def generate_stl_screenshots(stl_filepath: str, output_filepath: str = "stl_views.png",
                             fig_size: Tuple[int, int] = (12, 12), dpi: int = 150):
    """
    Generate a composite image with 4 different views of an STL file.

    Args:
        stl_filepath: Path to the STL file
        output_filepath: Path for the output image
        fig_size: Figure size as (width, height)
        dpi: Resolution of the output image
    """
    # Load STL
    mesh = load_stl(stl_filepath)

    # Get view configurations
    views = get_view_angles()

    # Calculate bounds
    max_range, mid = calculate_bounds(mesh)

    # Create figure with 2x2 subplots
    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor('white')

    # Plot each view
    for idx, (name, angles) in enumerate(views.items(), 1):
        ax = fig.add_subplot(2, 2, idx, projection='3d')
        plot_mesh_view(ax, mesh, angles, max_range, mid, name)

    # Adjust layout to prevent overlap
    plt.tight_layout()

    # Save the combined image
    plt.savefig(output_filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"Screenshot saved as {output_filepath}")


if __name__ == "__main__":
    # Generate screenshots
    generate_stl_screenshots("cylinder.stl", dpi=80)
