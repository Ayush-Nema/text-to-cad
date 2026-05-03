from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cadquery as cq
from cadquery import exporters

from graph.nodes.partspec import PartSpec


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
    supported = (
        "box", "cylinder", "revolve_profile",
        "cone", "sphere", "polygon_prism", "extrude_2d", "torus",
    )
    require(btype in supported, f"Unsupported base type: {btype}")

    if btype == "revolve_profile":
        prof = base.get("profile", [])
        require(isinstance(prof, list) and len(prof) >= 2, "revolve_profile: profile must have >=2 points")

        pts = []
        for i, p in enumerate(prof):
            r = float(p.get("r", 0.0)) * scale
            z = float(p.get("z", 0.0)) * scale
            require(r >= 0, f"revolve_profile: profile[{i}].r must be >= 0")
            pts.append((r, z))

        # Must include r=0 at ends for a closed solid, or we force closure by adding it.
        if pts[0][0] != 0.0:
            pts = [(0.0, pts[0][1])] + pts
        if pts[-1][0] != 0.0:
            pts = pts + [(0.0, pts[-1][1])]

        # CadQuery's revolve degenerates to a flat shape when the wire lies in a
        # plane containing the revolve axis (the canonical "RZ in the XZ plane,
        # revolve around Z" recipe yields volume=0). The reliable recipe is to
        # build the wire in XY (treating profile (r, z) as (x, y)), revolve
        # around the Y axis, then rotate the result so the part's long axis is
        # global Z — matching the box/cylinder convention.
        wp = (
            cq.Workplane("XY")
            .polyline(pts)
            .close()
            .revolve(360, (0, 0, 0), (0, 1, 0))
            .rotate((0, 0, 0), (1, 0, 0), 90)
        )

        # bbox in (X, Y, Z) after the +90deg-about-X rotation: long axis is Z.
        rmax = max(r for r, _ in pts)
        zmin = min(z for _, z in pts)
        zmax = max(z for _, z in pts)
        bbox = (2 * rmax, 2 * rmax, (zmax - zmin))

        return wp, bbox

    if btype == "box":
        size = base.get("size", {})
        x = float(size.get("x", 0.0)) * scale
        y = float(size.get("y", 0.0)) * scale
        z = float(size.get("z", 0.0)) * scale
        require(x > 0 and y > 0 and z > 0, "Box size x,y,z must be > 0")
        wp = cq.Workplane("XY").box(x, y, z, centered=True)
        return wp, (x, y, z)

    if btype == "cylinder":
        # centered on origin so total Z extent = h
        r = float(base.get("radius", 0.0)) * scale
        h = float(base.get("height", 0.0)) * scale
        require(r > 0 and h > 0, "Cylinder radius and height must be > 0")
        wp = cq.Workplane("XY").circle(r).extrude(h / 2.0, both=True)
        return wp, (2 * r, 2 * r, h)

    if btype == "cone":
        # Frustum (or full cone if top_radius==0). Centered on origin in Z.
        r_bot = float(base.get("radius", 0.0)) * scale
        r_top = float(base.get("top_radius", 0.0)) * scale
        h = float(base.get("height", 0.0)) * scale
        require(r_bot > 0, "Cone bottom radius (radius) must be > 0")
        require(h > 0, "Cone height must be > 0")
        require(r_top >= 0, "Cone top_radius must be >= 0")
        # Lift bottom face by h/2 below origin and stack the top h/2 above so the
        # part is centered on Z — matches the box/cylinder convention.
        wp = (
            cq.Workplane("XY")
            .workplane(offset=-h / 2.0)
            .circle(r_bot)
            .workplane(offset=h)
            .circle(r_top if r_top > 0 else 1e-3)
            .loft(combine=True)
        )
        rmax = max(r_bot, r_top)
        return wp, (2 * rmax, 2 * rmax, h)

    if btype == "sphere":
        r = float(base.get("radius", 0.0)) * scale
        require(r > 0, "Sphere radius must be > 0")
        wp = cq.Workplane("XY").sphere(r)
        return wp, (2 * r, 2 * r, 2 * r)

    if btype == "polygon_prism":
        n = int(base.get("n_sides", 0))
        r = float(base.get("radius", 0.0)) * scale
        h = float(base.get("height", 0.0)) * scale
        require(n >= 3, f"polygon_prism: n_sides must be >= 3 (got {n})")
        require(r > 0, "polygon_prism: radius must be > 0")
        require(h > 0, "polygon_prism: height must be > 0")
        # cq.polygon takes circumscribed-circle diameter
        wp = cq.Workplane("XY").polygon(n, 2 * r).extrude(h / 2.0, both=True)
        return wp, (2 * r, 2 * r, h)

    if btype == "extrude_2d":
        prof = base.get("profile_2d", []) or []
        h = float(base.get("height", 0.0)) * scale
        require(isinstance(prof, list) and len(prof) >= 3,
                "extrude_2d: profile_2d must have >= 3 points")
        require(h > 0, "extrude_2d: height must be > 0")
        pts = [(float(p.get("x", 0.0)) * scale, float(p.get("y", 0.0)) * scale) for p in prof]
        # Reject self-intersecting profile via shoelace area > 0 (signed area).
        area = 0.5 * abs(sum(
            pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts))
        ))
        require(area > 0, "extrude_2d: profile_2d has zero/degenerate area")
        wp = cq.Workplane("XY").polyline(pts).close().extrude(h / 2.0, both=True)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return wp, (max(xs) - min(xs), max(ys) - min(ys), h)

    if btype == "torus":
        R = float(base.get("major_radius", 0.0)) * scale
        r = float(base.get("minor_radius", 0.0)) * scale
        require(R > 0 and r > 0, "torus: major_radius and minor_radius must be > 0")
        require(r < R, f"torus: minor_radius ({r}) must be < major_radius ({R})")
        # Use OCCT's primitive directly — manual revolve recipes degenerate
        # when the wire plane contains the revolve axis.
        torus = cq.Solid.makeTorus(R, r)
        wp = cq.Workplane("XY").add(torus)
        return wp, (2 * (R + r), 2 * (R + r), 2 * r)

    # Fallthrough should not happen because of the `require` at the top.
    raise CADCompileError(f"Unsupported base type after dispatch: {btype}")


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
            elif ftype == "cut_annular_sector":
                wp = _apply_cut_annular_sector(wp, feat, base_bbox, scale)
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
    if isinstance(parts_spec, PartSpec):
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


def _apply_cut_annular_sector(
        wp: cq.Workplane,
        feat: Dict[str, Any],
        base_bbox: Tuple[float, float, float],
        scale: float,
) -> cq.Workplane:
    r_in = float(feat.get("r_inner", 0.0)) * scale
    r_out = float(feat.get("r_outer", 0.0)) * scale
    ang = float(feat.get("angle_deg", 0.0))
    rot = float(feat.get("rotate_deg", 0.0))

    require(r_in >= 0 and r_out > 0 and r_out > r_in, "cut_annular_sector: require 0 <= r_inner < r_outer")
    require(0 < ang < 360, "cut_annular_sector: angle_deg must be between 0 and 360")

    depth = float(feat.get("depth", 0.0)) * scale
    through = (depth == 0.0)

    # Pattern points: use your existing pattern generator to place repeated sectors.
    # We'll interpret pattern.circular(count=N) by rotating each sector around Z.
    pattern = feat.get("pattern", {"type": "single"})
    ptype = pattern.get("type", "single")

    if ptype == "single":
        angles = [rot]
    elif ptype == "circular":
        n = int(pattern.get("count", 0))
        start = float(pattern.get("start_angle_deg", 0.0))
        require(n >= 1, "cut_annular_sector: circular.count must be >=1")
        angles = [rot + start + 360.0 * i / n for i in range(n)]
    else:
        raise CADCompileError(f"cut_annular_sector: only supports pattern.type 'single' or 'circular' (got {ptype})")

    # Build a "sector sketch" on +Z face (XY plane), then cut.
    # Sector is a closed wire bounded by two arcs and two radial edges.
    # Drawing the sector on the *active* workplane (rather than constructing
    # a separate Wire and `add(...)`-ing it) keeps the wire registered as
    # pending, which is what `cutThruAll` / `cutBlind` need.

    def pol(r: float, deg: float) -> Tuple[float, float]:
        rad = math.radians(deg)
        return (r * math.cos(rad), r * math.sin(rad))

    for a0 in angles:
        a1 = a0 + ang
        p0 = pol(r_out, a0)
        p1 = pol(r_out, a1)
        p2 = pol(r_in, a1)
        p3 = pol(r_in, a0)
        p_mid_outer = pol(r_out, (a0 + a1) / 2.0)
        p_mid_inner = pol(r_in, (a0 + a1) / 2.0)

        sector_wp = (
            wp.faces(">Z").workplane(centerOption="CenterOfMass")
            .moveTo(*p0)
            .threePointArc(p_mid_outer, p1)
            .lineTo(*p2)
            .threePointArc(p_mid_inner, p3)
            .close()
        )

        if through:
            wp = sector_wp.cutThruAll()
        else:
            wp = sector_wp.cutBlind(-depth)

    return wp
