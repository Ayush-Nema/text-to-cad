import cadquery as cq

# Screw parameters
head_diameter = 10  # mm
head_height = 5     # mm
shaft_diameter = 5  # mm (nominal screw diameter)
shaft_length = 30   # mm
hex_flat = 6        # distance across flats of hex head

# Create the screw head (hex)
head = (
    cq.Workplane("XY")
    .polygon(6, hex_flat)  # hexagon
    .extrude(head_height)
)

# Create the shaft (cylindrical)
shaft = (
    cq.Workplane("XY")
    .workplane(offset=head_height)  # start at top of head
    .circle(shaft_diameter / 2)
    .extrude(shaft_length)
)

# Combine head and shaft
screw = head.union(shaft)

# Optional: add a simple thread representation (just for visualization)
# CadQuery doesn't create detailed threads easily; this is just a cylinder for now
# For realistic threads, use cq.Workplane().threadedHole or cadquery-assembly utilities

# Export as STL and STEP
cq.exporters.export(screw, "screw.stl")
cq.exporters.export(screw, "screw.step")

print("Exported: screw.stl and screw.step")
