"""Auto-generate a concise capability summary of PartSpec for use in prompts.

The full Pydantic JSON schema is already passed to the LLM via OpenAI
function-calling, so the prompt does NOT need to repeat every field. Instead
we expose a short, human-readable capability list — one line per base type
and feature type — so the system message and the schema-from-function-calling
can never drift.
"""
from __future__ import annotations

from typing import Iterable, List, Type, get_args

from pydantic import BaseModel

from graph.nodes.partspec import (
    BaseSpec,
    FeatureSpec,
    PartSpec,
    PatternSpec,
)


def _required_field_names(model: Type[BaseModel]) -> List[str]:
    """Field names with no default value (i.e. required by the model)."""
    out: List[str] = []
    for name, field in model.model_fields.items():
        if field.is_required():
            out.append(name)
    return out


def _typed_field_summary(model: Type[BaseModel], skip_const_type: bool = True) -> str:
    """Render `name(type)` for every field, hiding the const `type` literal."""
    parts: List[str] = []
    for name, field in model.model_fields.items():
        if skip_const_type and name == "type":
            continue
        ann = field.annotation
        ann_name = getattr(ann, "__name__", str(ann))
        # tidy up nested generics for readability
        ann_name = (
            ann_name.replace("typing.", "")
                    .replace("Optional", "Opt")
                    .replace("List", "list")
        )
        req = "" if field.is_required() else "?"
        parts.append(f"{name}{req}({ann_name})")
    return ", ".join(parts)


def _union_variant_models(union_type) -> List[Type[BaseModel]]:
    """Extract the concrete BaseModel classes from a Union[...] alias."""
    return [t for t in get_args(union_type) if isinstance(t, type) and issubclass(t, BaseModel)]


def _enum_summary(model: Type[BaseModel], field_name: str) -> str:
    """Return comma-joined Literal values for the given field."""
    field = model.model_fields[field_name]
    values = get_args(field.annotation)
    return ", ".join(repr(v) for v in values)


def supported_capabilities() -> str:
    """Render the concise capability list for inclusion in system prompts."""
    lines: List[str] = []

    # Bases
    lines.append("Supported BASE types (pick exactly one):")
    base_types = get_args(BaseSpec.model_fields["type"].annotation)
    for bt in base_types:
        lines.append(f"  - {bt}")
    lines.append("    (See the function-calling schema for required fields per base type.)")

    # Features
    lines.append("")
    lines.append("Supported FEATURE types (zero or more, applied in spec order):")
    feature_models = _union_variant_models(FeatureSpec)
    for fm in feature_models:
        type_value = get_args(fm.model_fields["type"].annotation)[0]
        summary = _typed_field_summary(fm)
        lines.append(f"  - {type_value}: {summary}")

    # Patterns
    lines.append("")
    lines.append("Supported PATTERN types (used inside hole-like features):")
    pattern_models = _union_variant_models(PatternSpec)
    for pm in pattern_models:
        type_value = get_args(pm.model_fields["type"].annotation)[0]
        summary = _typed_field_summary(pm)
        lines.append(f"  - {type_value}: {summary}")

    # Faces & edges
    lines.append("")
    # FeatureBase pulls Face from feature subclasses; sample from ThroughHole.
    th = next(m for m in feature_models if get_args(m.model_fields["type"].annotation)[0] == "through_hole")
    lines.append(f"  on_face accepts: {_enum_summary(th, 'on_face')}")
    fillet = next(m for m in feature_models if get_args(m.model_fields["type"].annotation)[0] == "fillet")
    lines.append(f"  edges accepts:   {_enum_summary(fillet, 'edges')}")

    return "\n".join(lines)


CAPABILITIES_BLOCK = supported_capabilities()


__all__ = ["supported_capabilities", "CAPABILITIES_BLOCK"]
