"""
Rounding Corners with Fillet
==============================
Filleting is done by selecting the edges of a solid, and using the fillet function.

Here we fillet all of the edges of a simple plate.
"""

import cadquery as cq

result = cq.Workplane("XY").box(3, 3, 0.5).edges("|Z").fillet(0.125)
