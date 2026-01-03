"""
Simple Rectangular Plate
==========================
Just about the simplest possible example, a rectangular box
"""

import cadquery as cq

result = cq.Workplane("front").box(2.0, 2.0, 0.5)
