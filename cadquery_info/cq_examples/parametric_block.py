"""
A Parametric Block
===================
Here’s a quick example using CadQuery. It creates a block with a hole through it
"""

import cadquery as cq

# Parameters
length = 40
width = 20
height = 10
hole_diameter = 5

# Build model
block = (
    cq.Workplane("XY")
    .box(length, width, height)
    .faces(">Z")
    .workplane()
    .hole(hole_diameter)
)

# Export to STL
cq.exporters.export(block, "block_with_hole.stl")
