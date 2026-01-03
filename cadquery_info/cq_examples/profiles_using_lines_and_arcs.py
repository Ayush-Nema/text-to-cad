"""
Building Profiles using lines and arcs
==========================================
Sometimes you need to build complex profiles using lines and arcs. This example builds a prismatic solid from 2D
operations.

2D operations maintain a current point, which is initially at the origin. Use close() to finish a closed curve.
"""

import cadquery as cq

result = (
    cq.Workplane("front")
    .lineTo(2.0, 0)
    .lineTo(2.0, 1.0)
    .threePointArc((1.0, 1.5), (0.0, 1.0))
    .close()
    .extrude(0.25)
)
