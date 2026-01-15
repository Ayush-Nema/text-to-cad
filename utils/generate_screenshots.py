"""
Generate screenshots of an object in STL file from 4 different angles.
Optionally return as base64 encoded string.
"""

import base64
from io import BytesIO
from typing import Dict, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from trimesh import Trimesh


def load_stl(filepath: str) -> Trimesh:
    """Load STL file and return trimesh object."""
    mesh = trimesh.load(filepath)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
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

    ax.view_init(elev=angles["elev"], azim=angles["azim"])

    ax.set_xlim(mid[0] - max_range, mid[0] + max_range)
    ax.set_ylim(mid[1] - max_range, mid[1] + max_range)
    ax.set_zlim(mid[2] - max_range, mid[2] + max_range)

    ax.set_facecolor('white')
    ax.axis('off')

    ax.text2D(0.05, 0.95, view_name, transform=ax.transAxes,
              fontsize=18, fontweight='bold',
              verticalalignment='top',
              bbox=dict(boxstyle='round', facecolor='white',
                        edgecolor='black', alpha=0.8, linewidth=1.5))


def generate_stl_screenshots(
        stl_filepath: str,
        output_filepath: Optional[str] = None,
        fig_size: Tuple[int, int] = (12, 12),
        dpi: int = 150,
        return_base64: bool = True
) -> Optional[str]:
    """
    Generate a composite image with 4 different views of an STL file.

    Args:
        stl_filepath: Path to the STL file
        output_filepath: Path for the output image (optional if return_base64=True)
        fig_size: Figure size as (width, height)
        dpi: Resolution of the output image
        return_base64: If True, return base64 encoded string

    Returns:
        Base64 encoded string if return_base64=True, else None
    """
    mesh = load_stl(stl_filepath)
    views = get_view_angles()
    max_range, mid = calculate_bounds(mesh)

    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor('white')

    for idx, (name, angles) in enumerate(views.items(), 1):
        ax = fig.add_subplot(2, 2, idx, projection='3d')
        plot_mesh_view(ax, mesh, angles, max_range, mid, name)

    plt.tight_layout()

    result = None

    if return_base64:
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        result = base64.b64encode(buffer.read()).decode('utf-8')

    if output_filepath:
        plt.savefig(output_filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        print(f"Screenshot saved as {output_filepath}")

    plt.close()
    return result


if __name__ == "__main__":
    # Save to file
    generate_stl_screenshots("cylinder.stl", output_filepath="stl_views.png", dpi=80)

    # Or get base64
    b64 = generate_stl_screenshots("cylinder.stl", return_base64=True, dpi=80)
