import cadquery as cq
import warnings
import sys

prog = """
import cadquery as cq

# Dimensions
shaft_diameter = 4      # mm
shaft_length = 20       # mm
head_diameter = 8       # mm
head_height = 4         # mm
overall_length = 24     # mm
thread_pitch = 1.0      # mm (typical for M4 screw)
thread_depth = 0.5      # mm (approximate, for visual thread)

def build():
    # 1. Create shaft base circle
    screw = (
        cq.Workplane("XY")
        .circle(shaft_diameter / 2)
        .extrude(shaft_length)
    )

    # 2. Apply helical thread (visual, not functional)
    # Create a helix path for the thread
    helix = (
        cq.Workplane("XY")
        .workplane(offset=0)
        .parametricCurve(
            lambda t: (
                (shaft_diameter / 2 + thread_depth) * cq.cos(2 * cq.pi * t * shaft_length / thread_pitch),
                (shaft_diameter / 2 + thread_depth) * cq.sin(2 * cq.pi * t * shaft_length / thread_pitch),
                t * shaft_length
            ),
            start=0,
            stop=1,
            N=shaft_length * 10  # Sufficient points for smoothness
        )
    )

    # Create thread profile (triangle)
    thread_profile = (
        cq.Workplane("XZ")
        .moveTo(0, 0)
        .lineTo(thread_pitch / 2, thread_depth)
        .lineTo(thread_pitch, 0)
        .close()
    )

    # Sweep thread profile along helix
    thread = (
        thread_profile
        .sweep(helix.vals()[0], isFrenet=True)
    )

    # Union thread with shaft
    screw = screw.union(thread)

    # 3. Add screw head
    screw = (
        screw
        .faces(">Z")
        .workplane()
        .circle(head_diameter / 2)
        .extrude(head_height)
    )

    return screw

model = build()

# Export
cq.exporters.export(model, "object.stl")
cq.exporters.export(model, "object.step")
"""

if __name__ == '__main__':
    exec_globals = {
        "__builtins__": __builtins__,
        "cq": cq,
        # "math": math
    }
    # exec_locals = {}

    runtime_warnings = []
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            exec(prog, exec_globals)
            runtime_warnings.extend([str(warn.message) for warn in w])
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()
            # Walk the traceback to the frame inside the executed code
            tb = exc_tb
            while tb.tb_next is not None:
                tb = tb.tb_next
            # Get the line number in the executed string
            lineno = tb.tb_lineno
            # Extract the actual line from the string
            line = prog.splitlines()[lineno-1] if lineno <= len(prog.splitlines()) else "<line not found>"
            print(f"{exc_type.__name__} at line {lineno}: `{line.strip()}`")
            print(f"Error message: {exc_value}")
            print("=========old msg======")
            print(f"{exc_type.__name__} at line {exc_tb.tb_lineno}: {str(e)}")
