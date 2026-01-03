"""
Generate screenshots of an object in STL file from 4 different angles
"""

import pyvista as pv

# Load STL
mesh = pv.read("cylinder.stl")

# Create plotter (off-screen rendering)
plotter = pv.Plotter(off_screen=True)
plotter.add_mesh(mesh, color="lightgray", show_edges=True)
plotter.set_background("white")

# Views to capture
views = {
    "iso": plotter.view_isometric,
    "front": plotter.view_xy,
    "top": plotter.view_xz,
    "side": plotter.view_yz,
}

for name, view_func in views.items():
    view_func()

    # Add title to the image and store the actor
    text_actor = plotter.add_text(name.upper(), position='upper_edge', font_size=24, color='black')

    # Take screenshot
    plotter.screenshot(f"{name}.png")

    # Remove text actor before next screenshot
    plotter.remove_actor(text_actor)

# Close plotter
plotter.close()
