"""
Generate screenshots of an object in STL file from 4 different angles
"""

from typing import Dict, Tuple, Optional
import base64
from io import BytesIO
from matplotlib.lines import Line2D
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


def generate_stl_screenshots(
        stl_filepath: str,
        output_filepath: Optional[str] = None,
        fig_size: Tuple[int, int] = (12, 12),
        dpi: int = 80,
        return_base64: bool = True
) -> Optional[str]:
    mesh = load_stl(stl_filepath)
    views = get_view_angles()
    max_range, mid = calculate_bounds(mesh)

    fig = plt.figure(figsize=fig_size, facecolor='white')

    # 4 subplots
    for idx, (name, angles) in enumerate(views.items(), 1):
        ax = fig.add_subplot(2, 2, idx, projection='3d')
        plot_mesh_view(ax, mesh, angles, max_range, mid, name)

    # Tight layout and separators
    fig.subplots_adjust(left=0.04, right=0.96, bottom=0.04, top=0.96, wspace=0.02, hspace=0.02)
    for x in [0.5]:  # vertical
        fig.add_artist(Line2D([x, x], [0.04, 0.96], transform=fig.transFigure, color='black'))
    for y in [0.5]:  # horizontal
        fig.add_artist(Line2D([0.04, 0.96], [y, y], transform=fig.transFigure, color='black'))

    # Save / return base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    if output_filepath:
        with open(output_filepath, 'wb') as f:
            f.write(buffer.getvalue())
        print(f"Screenshot saved as {output_filepath}")
    return base64.b64encode(buffer.getvalue()).decode('utf-8') if return_base64 else None


if __name__ == "__main__":
    # Generate screenshots
    generate_stl_screenshots("screw.stl", output_filepath="views.png", dpi=40)
