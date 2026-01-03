"""
An extruded prismatic solid
=============================
Build a prismatic solid using extrusion. After a drawing operation, the center of the previous object is placed on
the stack, and is the reference for the next operation. So in this case, the rect() is drawn centered on the
previously draw circle.

By default, rectangles and circles are centered around the previous working point.
"""

import cadquery as cq

result = cq.Workplane("front").circle(2.0).rect(0.5, 0.75).extrude(0.5)
