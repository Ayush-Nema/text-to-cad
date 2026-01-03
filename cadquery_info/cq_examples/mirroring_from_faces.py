"""
Mirroring From Faces
======================
This example shows how you can mirror about a selected face. It also shows how the resulting mirrored object can be
unioned immediately with the referenced mirror geometry.
"""

import cadquery as cq

result = cq.Workplane("XY").line(0, 1).line(1, 0).line(0, -0.5).close().extrude(1)

result = result.mirror(result.faces(">X"), union=True)
