import cadquery as cq

# =========================
# Parameters
# =========================
diameter = 10.0
height = 30.0

# =========================
# Create a cylinder
# =========================
cylinder = cq.Workplane("XY").circle(diameter / 2).extrude(height)

# =========================
# Export STL and STEP
# =========================
cq.exporters.export(cylinder, "cylinder.stl")
cq.exporters.export(cylinder, "cylinder.step")

print("Exported: cylinder.stl and cylinder.step")
