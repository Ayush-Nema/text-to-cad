"""
Simple script to visualize the object in STL file
"""

import pyvista as pv

mesh = pv.read("cylinder.stl")

plotter = pv.Plotter()
plotter.add_mesh(mesh, color="lightgray", show_edges=True)
plotter.show()
