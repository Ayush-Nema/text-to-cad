#!/usr/bin/env python3
"""
Deterministic CAD compiler: PartSpec JSON -> CadQuery solid -> STEP/STL

Install:
  pip install cadquery

Usage:
  python cad_compiler.py examples/plate_4holes.json --out out/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cadquery as cq
from cadquery import exporters


# ---------------------------
# Utilities
# ---------------------------

class CompileError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise CompileError(msg)


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
    raise CompileError(f"Unsupported units: {units}")


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
        raise CompileError(f"Unsupported on_face: {face}. Use one of {list(mapping.keys())}")
    return mapping[face]


def to_float(d: Dict[str, Any], key: str, default: Optional[float] = None) -> float:
    if key not in d:
        if default is None:
            raise CompileError(f"Missing required key '{key}'")
        return float(default)
    return float(d[key])


def scaled(value: float, scale: float) -> float:
    return float(value) * scale


# ---------------------------
# Patterns (return point lists)
# ---------------------------

def pattern_points(
        pattern: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float
) -> List[Tuple[float, float]]:
    """
    Produce XY points on the selected face's workplane.

    Conventions:
      - Base is centered at origin.
      - Face workplane uses the face as sketch plane; points are in that plane's XY.
      - For +Z / -Z faces, plane XY corresponds to global X/Y.
    """
    ptype = pattern.get("type")
    require(ptype is not None, "Pattern missing 'type'")

    x, y, z = base_bbox

    if ptype == "single":
        pos = pattern.get("position", {"x": 0, "y": 0})
        return [(scaled(pos.get("x", 0), scale), scaled(pos.get("y", 0), scale))]

    if ptype == "rectangular_4":
        eo = pattern.get("edge_offset", {})
        ox = scaled(to_float(eo, "x"), scale)
        oy = scaled(to_float(eo, "y"), scale)
        require(2 * ox < x, "edge_offset.x too large for part width")
        require(2 * oy < y, "edge_offset.y too large for part height")
        hx = (x / 2.0) - ox
        hy = (y / 2.0) - oy
        return [(-hx, -hy), (-hx, hy), (hx, -hy), (hx, hy)]

    if ptype == "linear":
        # Along X axis of the workplane by default; set axis to "x" or "y".
        n = int(pattern.get("count", 0))
        spacing = scaled(to_float(pattern, "spacing"), scale)
        axis = (pattern.get("axis") or "x").lower()
        require(n >= 1, "linear pattern count must be >= 1")
        require(spacing > 0 or n == 1, "linear spacing must be > 0 when count > 1")

        # center the pattern around origin
        total = spacing * (n - 1)
        start = -total / 2.0
        pts = []
        for i in range(n):
            t = start + i * spacing
            pts.append((t, 0.0) if axis == "x" else (0.0, t))
        return pts

    if ptype == "circular":
        # Points on a circle centered at origin
        import math
        n = int(pattern.get("count", 0))
        radius = scaled(to_float(pattern, "radius"), scale)
        start_deg = float(pattern.get("start_angle_deg", 0.0))
        require(n >= 1, "circular pattern count must be >= 1")
        require(radius >= 0, "circular pattern radius must be >= 0")

        pts = []
        for i in range(n):
            ang = math.radians(start_deg + (360.0 * i / n if n > 0 else 0))
            pts.append((radius * math.cos(ang), radius * math.sin(ang)))
        return pts

    raise CompileError(f"Unsupported pattern type: {ptype}")


# ---------------------------
# Base primitives
# ---------------------------

def make_base(base: Dict[str, Any], scale: float) -> Tuple[cq.Workplane, Tuple[float, float, float]]:
    btype = base.get("type")
    require(btype in ("box", "cylinder"), f"Unsupported base type: {btype}")

    if btype == "box":
        size = base.get("size", {})
        x = scaled(to_float(size, "x"), scale)
        y = scaled(to_float(size, "y"), scale)
        z = scaled(to_float(size, "z"), scale)
        require(x > 0 and y > 0 and z > 0, "Box size x,y,z must all be > 0")
        wp = cq.Workplane("XY").box(x, y, z, centered=True)
        return wp, (x, y, z)

    # cylinder
    r = scaled(to_float(base, "radius"), scale)
    h = scaled(to_float(base, "height"), scale)
    require(r > 0 and h > 0, "Cylinder radius and height must be > 0")
    wp = cq.Workplane("XY").circle(r).extrude(h, both=True)
    return wp, (2 * r, 2 * r, h)


# ---------------------------
# Feature application
# ---------------------------

def face_workplane(wp: cq.Workplane, on_face: str) -> cq.Workplane:
    sel = face_selector(on_face)
    return wp.faces(sel).workplane(centerOption="CenterOfMass")


def apply_holes(
        wp: cq.Workplane,
        feature: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float,
) -> cq.Workplane:
    ftype = feature.get("type")
    on_face = feature.get("on_face", "+Z")
    diameter = scaled(to_float(feature, "diameter"), scale)
    require(diameter > 0, "Hole diameter must be > 0")

    pts = pattern_points(feature.get("pattern", {"type": "single"}), base_bbox, scale)

    w = face_workplane(wp, on_face).pushPoints(pts)

    if ftype == "through_hole":
        return w.hole(diameter)

    if ftype == "blind_hole":
        depth = scaled(to_float(feature, "depth"), scale)
        require(depth > 0, "Blind hole depth must be > 0")
        # CadQuery: hole(diameter, depth)
        return w.hole(diameter, depth)

    if ftype == "counterbore":
        # Required: diameter, cbore_diameter, cbore_depth
        cbore_d = scaled(to_float(feature, "cbore_diameter"), scale)
        cbore_depth = scaled(to_float(feature, "cbore_depth"), scale)
        require(cbore_d > diameter, "Counterbore diameter must be > hole diameter")
        require(cbore_depth > 0, "Counterbore depth must be > 0")
        # cadquery has cboreHole(d, cboreD, cboreDepth, depth=None)
        depth = feature.get("depth")
        if depth is not None:
            depth = scaled(float(depth), scale)
            require(depth > 0, "Hole depth must be > 0 when provided")
            return w.cboreHole(diameter, cbore_d, cbore_depth, depth)
        return w.cboreHole(diameter, cbore_d, cbore_depth)

    if ftype == "countersink":
        # Required: diameter, csk_diameter, csk_angle_deg
        csk_d = scaled(to_float(feature, "csk_diameter"), scale)
        csk_angle = float(feature.get("csk_angle_deg", 82.0))
        require(csk_d > diameter, "Countersink diameter must be > hole diameter")
        require(0 < csk_angle < 180, "Countersink angle must be between 0 and 180")
        depth = feature.get("depth")
        if depth is not None:
            depth = scaled(float(depth), scale)
            require(depth > 0, "Hole depth must be > 0 when provided")
            return w.cskHole(diameter, csk_d, csk_angle, depth)
        return w.cskHole(diameter, csk_d, csk_angle)

    raise CompileError(f"Unsupported hole feature type: {ftype}")


def apply_fillet(wp: cq.Workplane, feature: Dict[str, Any], scale: float) -> cq.Workplane:
    radius = scaled(to_float(feature, "radius"), scale)
    require(radius > 0, "Fillet radius must be > 0")
    edges = (feature.get("edges") or "vertical").lower()

    if edges == "all":
        return wp.edges().fillet(radius)
    if edges == "vertical":
        return wp.edges("|Z").fillet(radius)
    if edges == "top":
        return wp.edges(">Z").fillet(radius)
    if edges == "bottom":
        return wp.edges("<Z").fillet(radius)

    raise CompileError(f"Unsupported fillet edges: {edges}")


def apply_chamfer(wp: cq.Workplane, feature: Dict[str, Any], scale: float) -> cq.Workplane:
    dist = scaled(to_float(feature, "distance"), scale)
    require(dist > 0, "Chamfer distance must be > 0")
    edges = (feature.get("edges") or "vertical").lower()

    if edges == "all":
        return wp.edges().chamfer(dist)
    if edges == "vertical":
        return wp.edges("|Z").chamfer(dist)
    if edges == "top":
        return wp.edges(">Z").chamfer(dist)
    if edges == "bottom":
        return wp.edges("<Z").chamfer(dist)

    raise CompileError(f"Unsupported chamfer edges: {edges}")


def apply_pocket_rect(
        wp: cq.Workplane,
        feature: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float,
) -> cq.Workplane:
    """
    Rectangular pocket cut into a face, with optional corner fillet
    applied as a 3D fillet on vertical pocket edges.
    """
    on_face = feature.get("on_face", "+Z")
    size = feature.get("size", {})
    sx = scaled(to_float(size, "x"), scale)
    sy = scaled(to_float(size, "y"), scale)
    depth = scaled(to_float(feature, "depth"), scale)

    require(sx > 0 and sy > 0 and depth > 0, "Pocket size and depth must be > 0")

    pos = feature.get("position", {"x": 0, "y": 0})
    px = scaled(float(pos.get("x", 0.0)), scale)
    py = scaled(float(pos.get("y", 0.0)), scale)

    corner_r = scaled(float(feature.get("corner_radius", 0.0)), scale)
    require(corner_r >= 0, "corner_radius must be >= 0")

    w = face_workplane(wp, on_face).center(px, py)

    # 1) Cut sharp pocket
    wp2 = w.rect(sx, sy).cutBlind(depth)

    # 2) Apply fillet to vertical edges of the pocket only
    if corner_r > 0:
        # Vertical edges parallel to Z inside the pocket
        wp2 = wp2.edges("|Z").fillet(corner_r)

    return wp2


def compile_partspec(spec: Dict[str, Any]) -> cq.Workplane:
    units = spec.get("units", "mm")
    scale = mm_scale(units)

    wp, base_bbox = make_base(spec.get("base", {}), scale)

    for feat in spec.get("features", []):
        ftype = feat.get("type")
        require(ftype is not None, "Feature missing 'type'")

        if ftype in ("through_hole", "blind_hole", "counterbore", "countersink"):
            wp = apply_holes(wp, feat, base_bbox, scale)
        elif ftype == "fillet":
            wp = apply_fillet(wp, feat, scale)
        elif ftype == "chamfer":
            wp = apply_chamfer(wp, feat, scale)
        elif ftype == "pocket_rect":
            wp = apply_pocket_rect(wp, feat, base_bbox, scale)
        else:
            raise CompileError(f"Unsupported feature type: {ftype}")

    return wp


def export_model(wp: cq.Workplane, out_dir: Path, name: str) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    step_path = out_dir / f"{name}.step"
    stl_path = out_dir / f"{name}.stl"
    solid = wp.val()

    exporters.export(solid, str(step_path))
    exporters.export(solid, str(stl_path))
    return step_path, stl_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path", help="Path to PartSpec JSON")
    ap.add_argument("--out", default="out", help="Output directory")
    args = ap.parse_args()

    json_path = Path(args.json_path)
    require(json_path.exists(), f"JSON not found: {json_path}")

    spec = json.loads(json_path.read_text())
    name = spec.get("part_name", json_path.stem)

    try:
        wp = compile_partspec(spec)
        step_path, stl_path = export_model(wp, Path(args.out), name)
        print("OK")
        print("STEP:", step_path)
        print("STL :", stl_path)
    except Exception as e:
        # Helpful for LangGraph repair loops: include the failing feature if you store an "id"
        raise


if __name__ == "__main__":
    main()
