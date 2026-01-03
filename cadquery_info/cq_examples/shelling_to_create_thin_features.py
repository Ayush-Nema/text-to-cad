"""
Shelling To Create Thin features
==================================
Shelling converts a solid object into a shell of uniform thickness.

To shell an object and ‘hollow out’ the inside pass a negative thickness parameter to the Workplane.shell() method of
a shape.
"""

import cadquery as cq

result = cq.Workplane("front").box(2, 2, 2).shell(-0.1)

# A positive thickness parameter wraps an object with filleted outside edges and the original object will be the
# ‘hollowed out’ portion.
result = cq.Workplane("front").box(2, 2, 2).shell(0.1)

# Use face selectors to select a face to be removed from the resulting hollow shape.
result = cq.Workplane("front").box(2, 2, 2).faces("+Z").shell(0.1)

# Multiple faces can be removed using more complex selectors.
result = cq.Workplane("front").box(2, 2, 2).faces("+Z or -X or +X").shell(0.1)
