"""
Polygons
==========
You can create polygons for each stack point if you would like. Useful in 3d printers whose firmware does not correct
for small hole sizes.
"""

import cadquery as cq

result = (
    cq.Workplane("front")
    .box(3.0, 4.0, 0.25)
    .pushPoints([(0, 0.75), (0, -0.75)])
    .polygon(6, 1.0)
    .cutThruAll()
)
