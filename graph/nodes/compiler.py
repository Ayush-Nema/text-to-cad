from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cadquery as cq
from cadquery import exporters

# If you have your PartSpec Pydantic model available, import it.
# Otherwise, you can remove this import and keep dict-only.
try:
    from partspec import PartSpec  # adjust import path
except Exception:  # pragma: no cover
    PartSpec = None  # type: ignore


class CADCompileError(RuntimeError):
    """Raised for deterministic CAD compiler failures with helpful context."""


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise CADCompileError(msg)


# -----------------------
# Units / selectors
# -----------------------

def mm_scale(units: str) -> float:
    u = (units or "mm").lower()
    if u in ("mm", "millimeter", "millimeters"):
        return 1.0
    if u in ("cm", "centimeter", "centimeters"):
        return 10.0
    if u in ("m", "meter", "meters"):
        return 1000.0
    if u in ("in", "inch", "inches"):
        return 25.4
    raise CADCompileError(f"Unsupported units: {units}")


def face_selector(face: str) -> str:
    mapping = {
        "+Z": ">Z",
        "-Z": "<Z",
        "+X": ">X",
        "-X": "<X",
        "+Y": ">Y",
        "-Y": "<Y",
    }
    if face not in mapping:
        raise CADCompileError(f"Unsupported on_face: {face}. Use one of {list(mapping.keys())}")
    return mapping[face]


def face_workplane(wp: cq.Workplane, on_face: str) -> cq.Workplane:
    return wp.faces(face_selector(on_face)).workplane(centerOption="CenterOfMass")


# -----------------------
# Pattern point generation
# -----------------------

def _pattern_points(
        pattern: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float,
) -> List[Tuple[float, float]]:
    """
    Returns list of (x,y) points in the selected face workplane.
    Assumes base solid is centered at origin.
    """
    ptype = (pattern.get("type") or "single")
    x, y, z = base_bbox

    if ptype == "single":
        pos = pattern.get("position", {"x": 0.0, "y": 0.0})
        return [(float(pos.get("x", 0.0)) * scale, float(pos.get("y", 0.0)) * scale)]

    if ptype == "rectangular_4":
        eo = pattern.get("edge_offset", {})
        ox = float(eo.get("x", 0.0)) * scale
        oy = float(eo.get("y", 0.0)) * scale
        require(ox >= 0 and oy >= 0, "edge_offset must be non-negative")
        require(2 * ox < x, "edge_offset.x too large for part width")
        require(2 * oy < y, "edge_offset.y too large for part height")
        hx = (x / 2.0) - ox
        hy = (y / 2.0) - oy
        return [(-hx, -hy), (-hx, hy), (hx, -hy), (hx, hy)]

    if ptype == "linear":
        count = int(pattern.get("count", 0))
        spacing = float(pattern.get("spacing", 0.0)) * scale
        axis = (pattern.get("axis") or "x").lower()
        require(count >= 1, "linear.count must be >= 1")
        require(spacing > 0 or count == 1, "linear.spacing must be > 0 when count > 1")

        total = spacing * (count - 1)
        start = -total / 2.0
        pts: List[Tuple[float, float]] = []
        for i in range(count):
            t = start + i * spacing
            pts.append((t, 0.0) if axis == "x" else (0.0, t))
        return pts

    if ptype == "circular":
        count = int(pattern.get("count", 0))
        radius = float(pattern.get("radius", 0.0)) * scale
        start_deg = float(pattern.get("start_angle_deg", 0.0))
        require(count >= 1, "circular.count must be >= 1")
        require(radius >= 0, "circular.radius must be >= 0")

        pts: List[Tuple[float, float]] = []
        for i in range(count):
            ang = math.radians(start_deg + 360.0 * i / count)
            pts.append((radius * math.cos(ang), radius * math.sin(ang)))
        return pts

    raise CADCompileError(f"Unsupported pattern type: {ptype}")


# -----------------------
# Base creation
# -----------------------

def _make_base(base: Dict[str, Any], scale: float) -> Tuple[cq.Workplane, Tuple[float, float, float]]:
    btype = base.get("type")
    require(btype in ("box", "cylinder"), f"Unsupported base type: {btype}")

    if btype == "box":
        size = base.get("size", {})
        x = float(size.get("x", 0.0)) * scale
        y = float(size.get("y", 0.0)) * scale
        z = float(size.get("z", 0.0)) * scale
        require(x > 0 and y > 0 and z > 0, "Box size x,y,z must be > 0")
        wp = cq.Workplane("XY").box(x, y, z, centered=True)
        return wp, (x, y, z)

    # cylinder
    r = float(base.get("radius", 0.0)) * scale
    h = float(base.get("height", 0.0)) * scale
    require(r > 0 and h > 0, "Cylinder radius and height must be > 0")
    wp = cq.Workplane("XY").circle(r).extrude(h, both=True)
    return wp, (2 * r, 2 * r, h)


# -----------------------
# Feature application
# -----------------------

def _apply_hole_like(
        wp: cq.Workplane,
        feat: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float,
) -> cq.Workplane:
    ftype = feat["type"]
    on_face = feat.get("on_face", "+Z")
    diameter = float(feat.get("diameter", 0.0)) * scale
    require(diameter > 0, f"{ftype}: diameter must be > 0")

    pts = _pattern_points(feat.get("pattern", {"type": "single"}), base_bbox, scale)
    w = face_workplane(wp, on_face).pushPoints(pts)

    if ftype == "through_hole":
        return w.hole(diameter)

    if ftype == "blind_hole":
        depth = float(feat.get("depth", 0.0)) * scale
        require(depth > 0, "blind_hole: depth must be > 0")
        return w.hole(diameter, depth)

    if ftype == "counterbore":
        cbore_d = float(feat.get("cbore_diameter", 0.0)) * scale
        cbore_depth = float(feat.get("cbore_depth", 0.0)) * scale
        require(cbore_d > diameter, "counterbore: cbore_diameter must be > diameter")
        require(cbore_depth > 0, "counterbore: cbore_depth must be > 0")

        depth = feat.get("depth", 0.0)
        depth = float(depth) * scale if depth else None
        if depth:
            require(depth > 0, "counterbore: depth must be > 0 when provided")
            return w.cboreHole(diameter, cbore_d, cbore_depth, depth)
        return w.cboreHole(diameter, cbore_d, cbore_depth)

    if ftype == "countersink":
        csk_d = float(feat.get("csk_diameter", 0.0)) * scale
        csk_angle = float(feat.get("csk_angle_deg", 82.0))
        require(csk_d > diameter, "countersink: csk_diameter must be > diameter")
        require(0 < csk_angle < 180, "countersink: csk_angle_deg must be between 0 and 180")

        depth = feat.get("depth", 0.0)
        depth = float(depth) * scale if depth else None
        if depth:
            require(depth > 0, "countersink: depth must be > 0 when provided")
            return w.cskHole(diameter, csk_d, csk_angle, depth)
        return w.cskHole(diameter, csk_d, csk_angle)

    raise CADCompileError(f"Unsupported hole-like feature type: {ftype}")


def _apply_fillet(wp: cq.Workplane, feat: Dict[str, Any], scale: float) -> cq.Workplane:
    radius = float(feat.get("radius", 0.0)) * scale
    require(radius > 0, "fillet: radius must be > 0")
    edges = (feat.get("edges") or "vertical").lower()

    if edges == "all":
        return wp.edges().fillet(radius)
    if edges == "vertical":
        return wp.edges("|Z").fillet(radius)
    if edges == "top":
        return wp.edges(">Z").fillet(radius)
    if edges == "bottom":
        return wp.edges("<Z").fillet(radius)
    raise CADCompileError(f"fillet: unsupported edges selector '{edges}'")


def _apply_chamfer(wp: cq.Workplane, feat: Dict[str, Any], scale: float) -> cq.Workplane:
    # In your Pydantic model you used chamfer.distance (not radius)
    dist = float(feat.get("distance", 0.0)) * scale
    require(dist > 0, "chamfer: distance must be > 0")
    edges = (feat.get("edges") or "vertical").lower()

    if edges == "all":
        return wp.edges().chamfer(dist)
    if edges == "vertical":
        return wp.edges("|Z").chamfer(dist)
    if edges == "top":
        return wp.edges(">Z").chamfer(dist)
    if edges == "bottom":
        return wp.edges("<Z").chamfer(dist)
    raise CADCompileError(f"chamfer: unsupported edges selector '{edges}'")


def _apply_pocket_rect(
        wp: cq.Workplane,
        feat: Dict[str, Any],
        scale: float,
) -> cq.Workplane:
    """
    Pocket is cut as sharp rectangle first, then optional 3D fillet is applied.
    This avoids 'vertices().fillet()' selection issues and doesn't rely on fillet2D().
    """
    on_face = feat.get("on_face", "+Z")
    pos = feat.get("position", {"x": 0.0, "y": 0.0})
    px = float(pos.get("x", 0.0)) * scale
    py = float(pos.get("y", 0.0)) * scale

    size = feat.get("size", {"x": 0.0, "y": 0.0})
    sx = float(size.get("x", 0.0)) * scale
    sy = float(size.get("y", 0.0)) * scale
    depth = float(feat.get("depth", 0.0)) * scale
    require(sx > 0 and sy > 0 and depth > 0, "pocket_rect: size.x, size.y, depth must be > 0")

    corner_r = float(feat.get("corner_radius", 0.0)) * scale
    require(corner_r >= 0, "pocket_rect: corner_radius must be >= 0")
    if corner_r > 0:
        # Clamp to be more kernel-safe
        corner_r = min(corner_r, min(sx, sy) / 4.0)

    # 1) cut pocket
    wp2 = (
        face_workplane(wp, on_face)
        .center(px, py)
        .rect(sx, sy)
        .cutBlind(depth)
    )

    # 2) optional fillet (applies to vertical edges; stable across CQ builds)
    if corner_r > 0:
        wp2 = wp2.edges("|Z").fillet(corner_r)

    return wp2


def compile_partspec(partspec: Dict[str, Any]) -> cq.Workplane:
    units = partspec.get("units", "mm")
    scale = mm_scale(units)

    wp, base_bbox = _make_base(partspec.get("base", {}), scale)

    for feat in partspec.get("features", []):
        if not isinstance(feat, dict) or "type" not in feat:
            raise CADCompileError(f"Feature missing 'type': {feat}")

        ftype = feat["type"]

        try:
            if ftype in ("through_hole", "blind_hole", "counterbore", "countersink"):
                wp = _apply_hole_like(wp, feat, base_bbox, scale)
            elif ftype == "pocket_rect":
                wp = _apply_pocket_rect(wp, feat, scale)
            elif ftype == "fillet":
                wp = _apply_fillet(wp, feat, scale)
            elif ftype == "chamfer":
                wp = _apply_chamfer(wp, feat, scale)
            else:
                raise CADCompileError(f"Unsupported feature type: {ftype}")
        except Exception as e:
            fid = feat.get("id", "")
            prefix = f"[feature type={ftype}" + (f" id={fid}]" if fid else "]")
            raise CADCompileError(f"{prefix} {e}") from e

    return wp


def compile_and_export(
        parts_spec: Union[Dict[str, Any], "PartSpec"],
        out_dir: str,
        export_step: bool = True,
        export_stl: bool = True,
        step_name: Optional[str] = None,
        stl_name: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Deterministic compiler entrypoint.

    Returns:
      {"step_path": ".../name.step" or None, "stl_path": ".../name.stl" or None}
    """
    # Normalize to dict
    if PartSpec is not None and isinstance(parts_spec, PartSpec):
        spec_dict = parts_spec.model_dump()
    elif isinstance(parts_spec, dict):
        spec_dict = parts_spec
    else:
        raise TypeError(f"parts_spec must be dict or PartSpec, got {type(parts_spec)}")

    part_name = spec_dict.get("part_name", "part")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    wp = compile_partspec(spec_dict)
    solid = wp.val()

    step_path: Optional[str] = None
    stl_path: Optional[str] = None

    if export_step:
        fname = step_name or f"{part_name}.step"
        step_file = out / fname
        exporters.export(solid, str(step_file))
        step_path = str(step_file)

    if export_stl:
        fname = stl_name or f"{part_name}.stl"
        stl_file = out / fname
        exporters.export(solid, str(stl_file))
        stl_path = str(stl_file)

    return {"step_path": step_path, "stl_path": stl_path}
