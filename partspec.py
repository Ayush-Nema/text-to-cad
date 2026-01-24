from __future__ import annotations

from typing import Any, List, Literal, Union
from pydantic import BaseModel, Field, ConfigDict

# ---- Enums / Literals ----
Face = Literal["+Z", "-Z", "+X", "-X", "+Y", "-Y"]
EdgeSet = Literal["all", "vertical", "top", "bottom"]

BaseType = Literal["box", "cylinder"]
FeatureType = Literal["through_hole", "blind_hole", "fillet", "chamfer", "pocket_rect", "counterbore", "countersink"]


# ---- Shared structs ----
class Size3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Position2(BaseModel):
    x: float = 0.0
    y: float = 0.0


class DistanceFromEdges(BaseModel):
    left: float = 0.0
    right: float = 0.0
    front: float = 0.0
    back: float = 0.0


class DefaultApplied(BaseModel):
    path: str
    value: Any
    reason: str


class ClarificationNeeded(BaseModel):
    question: str
    options: List[str] = Field(default_factory=list)
    blocking: bool = True


# ---- Base ----
class BaseSpec(BaseModel):
    type: BaseType
    # For box:
    size: Size3 = Field(default_factory=Size3)
    # For cylinder:
    radius: float = 0.0
    height: float = 0.0


# ---- Patterns ----
PatternType = Literal["single", "rectangular_4", "linear", "circular"]


class PatternSingle(BaseModel):
    type: Literal["single"] = "single"
    position: Position2 = Field(default_factory=Position2)


class PatternRectangular4(BaseModel):
    type: Literal["rectangular_4"] = "rectangular_4"
    edge_offset: Position2  # reuse Position2 as {x, y}


class PatternLinear(BaseModel):
    type: Literal["linear"] = "linear"
    count: int
    spacing: float
    axis: Literal["x", "y"] = "x"


class PatternCircular(BaseModel):
    type: Literal["circular"] = "circular"
    count: int
    radius: float
    start_angle_deg: float = 0.0


PatternSpec = Union[PatternSingle, PatternRectangular4, PatternLinear, PatternCircular]


# ---- Features ----
class FeatureBase(BaseModel):
    # Optional but HIGHLY recommended for debugging + repair loops
    id: str = ""
    type: FeatureType
    on_face: Face = "+Z"
    position: Position2 = Field(default_factory=Position2)
    distance_from_edges: DistanceFromEdges = Field(default_factory=DistanceFromEdges)
    pattern: PatternSpec = Field(default_factory=PatternSingle)


class ThroughHole(FeatureBase):
    type: Literal["through_hole"] = "through_hole"
    diameter: float


class BlindHole(FeatureBase):
    type: Literal["blind_hole"] = "blind_hole"
    diameter: float
    depth: float


class Counterbore(FeatureBase):
    type: Literal["counterbore"] = "counterbore"
    diameter: float
    cbore_diameter: float
    cbore_depth: float
    depth: float = 0.0  # optional through depth if you support it


class Countersink(FeatureBase):
    type: Literal["countersink"] = "countersink"
    diameter: float
    csk_diameter: float
    csk_angle_deg: float = 82.0
    depth: float = 0.0  # optional


class Fillet(BaseModel):
    id: str = ""
    type: Literal["fillet"] = "fillet"
    edges: EdgeSet = "vertical"
    radius: float


class Chamfer(BaseModel):
    id: str = ""
    type: Literal["chamfer"] = "chamfer"
    edges: EdgeSet = "vertical"
    distance: float


class PocketRect(BaseModel):
    id: str = ""
    type: Literal["pocket_rect"] = "pocket_rect"
    on_face: Face = "+Z"
    position: Position2 = Field(default_factory=Position2)
    size: Position2  # {x, y}
    depth: float
    corner_radius: float = 0.0


FeatureSpec = Union[
    ThroughHole,
    BlindHole,
    Counterbore,
    Countersink,
    Fillet,
    Chamfer,
    PocketRect,
]


# ---- PartSpec ----
class PartSpec(BaseModel):
    """
    This is the structured output target for the LLM.
    """
    model_config = ConfigDict(extra="forbid")  # catch hallucinated keys

    schema_version: str = "1.0"
    units: str = "mm"
    part_name: str

    base: BaseSpec
    features: List[FeatureSpec] = Field(default_factory=list)

    defaults_applied: List[DefaultApplied] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    clarifications_needed: List[ClarificationNeeded] = Field(default_factory=list)
