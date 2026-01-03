"""
Making Lofts
===============
A loft is a solid swept through a set of wires. This example creates lofted section between a rectangle and a
circular section.
"""

import cadquery as cq

result = (
    cq.Workplane("front")
    .box(4.0, 4.0, 0.25)
    .faces(">Z")
    .circle(1.5)
    .workplane(offset=3.0)
    .rect(0.75, 0.5)
    .loft(combine=True)
)
