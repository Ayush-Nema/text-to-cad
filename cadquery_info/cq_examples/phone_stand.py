"""
Building a Phone Stand
========================
A slightly more advanced example is making something useful like a phone stand.
"""

import cadquery as cq

# Parameters
stand_height = 80
stand_width = 60
stand_thickness = 4
angle = 15

stand = (
    cq.Workplane("XY")
    .rect(stand_width, stand_thickness)
    .extrude(stand_height)
    .rotate((0, 0, 0), (1, 0, 0), angle)  # tilt stand back
)

cq.exporters.export(stand, "phone_stand.stl")
