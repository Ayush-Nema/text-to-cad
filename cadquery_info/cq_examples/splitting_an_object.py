"""
Splitting an Object
====================
You can split an object using a workplane, and retain either or both halves
"""

import cadquery as cq

c = cq.Workplane("XY").box(1, 1, 1).faces(">Z").workplane().circle(0.25).cutThruAll()

# now cut it in half sideways
result = c.faces(">Y").workplane(-0.5).split(keepTop=True)
