"""
Scratch code to identify whether `cadquery` is importable
"""

try:
    import cadquery as cq
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs

    CADQUERY_AVAILABLE = True
    print("CadQuery available")
except ImportError:
    CADQUERY_AVAILABLE = False
    print("Warning: CadQuery not installed. Install with: pip install cadquery")
