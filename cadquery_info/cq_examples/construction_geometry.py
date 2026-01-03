"""
Using construction Geometry
=============================
You can draw shapes to use the vertices as points to locate other features. Features that are used to locate other
features, rather than to create them, are called Construction Geometry

In the example below, a rectangle is drawn, and its vertices are used to locate a set of holes.
"""

import cadquery as cq

result = (
    cq.Workplane("front")
    .box(2, 2, 0.5)
    .faces(">Z")
    .workplane()
    .rect(1.5, 1.5, forConstruction=True)
    .vertices()
    .hole(0.125)
)
