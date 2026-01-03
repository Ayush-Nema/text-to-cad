"""
Locating a Workplane on a vertex
==================================
Normally, the Workplane.workplane() method requires a face to be selected. But if a vertex is selected immediately
after a face, Workplane.workplane() with the centerOption argument set to CenterOfMass will locate the workplane on
the face, with the origin at the vertex instead of at the center of the face

The example also introduces Workplane.cutThruAll(), which makes a cut through the entire part, no matter how deep the
part is.
"""

import cadquery as cq

result = cq.Workplane("front").box(3, 2, 0.5)  # make a basic prism
result = (
    result.faces(">Z").vertices("<XY").workplane(centerOption="CenterOfMass")
)  # select the lower left vertex and make a workplane
result = result.circle(1.0).cutThruAll()  # cut the corner out

