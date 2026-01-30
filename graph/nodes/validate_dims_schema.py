from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


def _bbox_from_base(spec: Dict[str, Any]) -> Tuple[float, float, float]:
    base = spec.get("base", {})
    btype = base.get("type")

    if btype == "box":
        size = base.get("size", {}) or {}
        x, y, z = float(size.get("x", 0)), float(size.get("y", 0)), float(size.get("z", 0))
        return x, y, z

    if btype == "cylinder":
        r, h = float(base.get("radius", 0)), float(base.get("height", 0))
        # bbox in XY is diameter
        return 2 * r, 2 * r, h

    return 0.0, 0.0, 0.0


def _add_err(errs: List[Dict[str, Any]], path: str, msg: str, severity: str = "error") -> None:
    errs.append({"path": path, "message": msg, "severity": severity})


def make_validate_partspec_node():
    """
    Rigid semantic validation for dimensions / geometry feasibility.
    Produces:
      state["is_valid"] (bool)
      state["validation_errors"] (list)
    """

    def _node(state: Dict[str, Any]) -> Dict[str, Any]:
        spec = state.get("parts_spec")
        if not spec:
            raise ValueError("Missing state['parts_spec'] (run spec node first).")

        errs: List[Dict[str, Any]] = []

        # ---- Base validation ----
        base = spec.get("base", {})
        btype = base.get("type")
        if btype not in ("box", "cylinder"):
            _add_err(errs, "base.type", f"Unsupported base.type='{btype}'. Must be 'box' or 'cylinder'.")
        else:
            if btype == "box":
                size = base.get("size", {}) or {}
                for k in ("x", "y", "z"):
                    v = float(size.get(k, 0))
                    if v <= 0:
                        _add_err(errs, f"base.size.{k}", f"Box dimension {k} must be > 0 (got {v}).")
                # forbid cylinder fields
                if float(base.get("radius", 0)) != 0 or float(base.get("height", 0)) != 0:
                    _add_err(errs, "base.radius|base.height",
                             "For box base, radius and height should be 0.", severity="warning")

            if btype == "cylinder":
                r = float(base.get("radius", 0))
                h = float(base.get("height", 0))
                if r <= 0:
                    _add_err(errs, "base.radius", f"Cylinder radius must be > 0 (got {r}).")
                if h <= 0:
                    _add_err(errs, "base.height", f"Cylinder height must be > 0 (got {h}).")
                # forbid box fields
                size = base.get("size", {}) or {}
                if any(float(size.get(k, 0)) != 0 for k in ("x", "y", "z")):
                    _add_err(errs, "base.size",
                             "For cylinder base, size.x/y/z should be 0.", severity="warning")

        # Bounding box (in same units as spec; compiler later scales)
        bx, by, bz = _bbox_from_base(spec)
        if bx <= 0 or by <= 0 or bz <= 0:
            _add_err(errs, "base", "Base bounding box invalid; cannot validate feature placement.")

        # ---- Feature validation ----
        features = spec.get("features", []) or []
        for i, f in enumerate(features):
            ftype = f.get("type")
            fid = f.get("id", "")
            prefix = f"features[{i}]" + (f"(id={fid})" if fid else "")
            path_base = f"features[{i}]"

            if not ftype:
                _add_err(errs, f"{path_base}.type", f"{prefix}: missing type")
                continue

            # Common fields
            on_face = f.get("on_face", "+Z")
            if on_face not in ("+Z", "-Z", "+X", "-X", "+Y", "-Y"):
                _add_err(errs, f"{path_base}.on_face", f"{prefix}: invalid on_face '{on_face}'")

            # Helper: get pattern points if present (in face plane coords)
            pattern = f.get("pattern") or {"type": "single"}
            ptype = pattern.get("type", "single")

            def points_from_pattern() -> List[Tuple[float, float]]:
                if ptype == "single":
                    pos = pattern.get("position", f.get("position", {"x": 0, "y": 0})) or {"x": 0, "y": 0}
                    return [(float(pos.get("x", 0)), float(pos.get("y", 0)))]

                if ptype == "rectangular_4":
                    eo = pattern.get("edge_offset", {}) or {}
                    ox, oy = float(eo.get("x", 0)), float(eo.get("y", 0))
                    if ox < 0 or oy < 0:
                        _add_err(errs, f"{path_base}.pattern.edge_offset", f"{prefix}: edge_offset must be >=0")
                        return []
                    if bx > 0 and by > 0:
                        if 2 * ox >= bx:
                            _add_err(errs, f"{path_base}.pattern.edge_offset.x", f"{prefix}: edge_offset.x too large")
                        if 2 * oy >= by:
                            _add_err(errs, f"{path_base}.pattern.edge_offset.y", f"{prefix}: edge_offset.y too large")
                        hx, hy = (bx / 2) - ox, (by / 2) - oy
                        return [(-hx, -hy), (-hx, hy), (hx, -hy), (hx, hy)]
                    return []

                if ptype == "linear":
                    n = int(pattern.get("count", 0))
                    spacing = float(pattern.get("spacing", 0))
                    axis = (pattern.get("axis") or "x").lower()
                    if n < 1:
                        _add_err(errs, f"{path_base}.pattern.count", f"{prefix}: linear.count must be >= 1")
                        return []
                    if n > 1 and spacing <= 0:
                        _add_err(errs, f"{path_base}.pattern.spacing", f"{prefix}: linear.spacing must be > 0")
                        return []
                    total = spacing * (n - 1)
                    start = -total / 2
                    pts = []
                    for k in range(n):
                        t = start + k * spacing
                        pts.append((t, 0.0) if axis == "x" else (0.0, t))
                    return pts

                if ptype == "circular":
                    n = int(pattern.get("count", 0))
                    r = float(pattern.get("radius", 0))
                    start = float(pattern.get("start_angle_deg", 0))
                    if n < 1:
                        _add_err(errs, f"{path_base}.pattern.count", f"{prefix}: circular.count must be >= 1")
                        return []
                    if r < 0:
                        _add_err(errs, f"{path_base}.pattern.radius", f"{prefix}: circular.radius must be >= 0")
                        return []
                    pts = []
                    for k in range(n):
                        ang = math.radians(start + 360.0 * k / n)
                        pts.append((r * math.cos(ang), r * math.sin(ang)))
                    return pts

                _add_err(errs, f"{path_base}.pattern.type", f"{prefix}: unsupported pattern.type '{ptype}'")
                return []

            # Dimension checks by feature type
            if ftype in ("through_hole", "blind_hole", "counterbore", "countersink"):
                d = float(f.get("diameter", 0))
                if d <= 0:
                    _add_err(errs, f"{path_base}.diameter", f"{prefix}: diameter must be > 0")

                if ftype == "blind_hole":
                    depth = float(f.get("depth", 0))
                    if depth <= 0:
                        _add_err(errs, f"{path_base}.depth", f"{prefix}: blind_hole depth must be > 0")
                    # if drilling from top/bottom of box/cyl, depth should not exceed thickness/height
                    if bz > 0 and depth > bz:
                        _add_err(errs, f"{path_base}.depth",
                                 f"{prefix}: depth ({depth}) exceeds part thickness/height ({bz})")

                if ftype == "counterbore":
                    cb_d = float(f.get("cbore_diameter", 0))
                    cb_depth = float(f.get("cbore_depth", 0))
                    if cb_d <= d:
                        _add_err(errs, f"{path_base}.cbore_diameter", f"{prefix}: cbore_diameter must be > diameter")
                    if cb_depth <= 0:
                        _add_err(errs, f"{path_base}.cbore_depth", f"{prefix}: cbore_depth must be > 0")
                    if bz > 0 and cb_depth > bz:
                        _add_err(errs, f"{path_base}.cbore_depth", f"{prefix}: cbore_depth exceeds thickness/height")

                if ftype == "countersink":
                    csk_d = float(f.get("csk_diameter", 0))
                    ang = float(f.get("csk_angle_deg", 82))
                    if csk_d <= d:
                        _add_err(errs, f"{path_base}.csk_diameter", f"{prefix}: csk_diameter must be > diameter")
                    if not (0 < ang < 180):
                        _add_err(errs, f"{path_base}.csk_angle_deg", f"{prefix}: angle must be between 0 and 180")

                # Placement sanity: points should lie within face bounds (box-only robust check)
                pts = points_from_pattern()
                if btype == "box" and bx > 0 and by > 0:
                    for (px, py) in pts:
                        if abs(px) > bx / 2 or abs(py) > by / 2:
                            _add_err(errs, f"{path_base}.pattern", f"{prefix}: point ({px},{py}) outside face bounds")

            elif ftype == "pocket_rect":
                size = f.get("size", {}) or {}
                sx, sy = float(size.get("x", 0)), float(size.get("y", 0))
                depth = float(f.get("depth", 0))
                cr = float(f.get("corner_radius", 0))
                if sx <= 0 or sy <= 0:
                    _add_err(errs, f"{path_base}.size", f"{prefix}: pocket size x/y must be > 0")
                if depth <= 0:
                    _add_err(errs, f"{path_base}.depth", f"{prefix}: pocket depth must be > 0")
                if bz > 0 and depth >= bz:
                    _add_err(errs, f"{path_base}.depth", f"{prefix}: pocket depth must be < thickness/height ({bz})")
                if cr < 0:
                    _add_err(errs, f"{path_base}.corner_radius", f"{prefix}: corner_radius must be >= 0")
                if cr > 0 and 2 * cr > min(sx, sy):
                    _add_err(errs, f"{path_base}.corner_radius", f"{prefix}: corner_radius too large for pocket")

                # Pocket placement within face (box check)
                pos = f.get("position", {"x": 0, "y": 0}) or {"x": 0, "y": 0}
                px, py = float(pos.get("x", 0)), float(pos.get("y", 0))
                if btype == "box" and bx > 0 and by > 0:
                    if abs(px) + sx / 2 > bx / 2:
                        _add_err(errs, f"{path_base}.position.x", f"{prefix}: pocket exceeds X bounds")
                    if abs(py) + sy / 2 > by / 2:
                        _add_err(errs, f"{path_base}.position.y", f"{prefix}: pocket exceeds Y bounds")

            elif ftype == "fillet":
                r = float(f.get("radius", 0))
                if r <= 0:
                    _add_err(errs, f"{path_base}.radius", f"{prefix}: fillet radius must be > 0")
                # heuristic: radius shouldn’t exceed half smallest dimension
                if bx > 0 and by > 0 and bz > 0 and r > min(bx, by, bz) / 2:
                    _add_err(errs, f"{path_base}.radius", f"{prefix}: fillet radius too large for part")

            elif ftype == "chamfer":
                dist = float(f.get("distance", 0))
                if dist <= 0:
                    _add_err(errs, f"{path_base}.distance", f"{prefix}: chamfer distance must be > 0")
                if bx > 0 and by > 0 and bz > 0 and dist > min(bx, by, bz) / 2:
                    _add_err(errs, f"{path_base}.distance", f"{prefix}: chamfer distance too large for part")

            else:
                _add_err(errs, f"{path_base}.type", f"{prefix}: unsupported feature type '{ftype}'")

        # Decide validity: treat "error" as blocking, "warning" as non-blocking
        blocking = [e for e in errs if e.get("severity") == "error"]
        is_valid = len(blocking) == 0

        new_state = dict(state)
        new_state["validation_errors"] = errs
        new_state["is_valid"] = is_valid
        return new_state

    return _node
