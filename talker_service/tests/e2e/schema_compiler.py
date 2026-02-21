"""Compile docs/zmq-api.yaml into JSON Schema dicts for validation.

Public API
----------
compile_schema(yaml_path) -> dict[str, TopicSchema]

``TopicSchema`` is a ``TypedDict`` with optional keys ``payload``,
``request``, ``response`` — each a standard JSON Schema dict ready
for use with ``jsonschema.validate()``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


# ── Primitive type mapping ──────────────────────────────────────

_PRIMITIVE_MAP: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "int": {"type": "integer"},
    "float": {"type": "number"},
    "bool": {"type": "boolean"},
    "object": {"type": "object"},
    "any": {},  # no type constraint
}


# ── Internal helpers ────────────────────────────────────────────

def _compile_field(field_def: dict[str, Any]) -> dict[str, Any]:
    """Translate a single YAML field definition to a JSON Schema property."""
    # $ref shorthand  →  {"$ref": "#/$defs/TypeName"}
    if "$ref" in field_def:
        schema: dict[str, Any] = {"$ref": f"#/$defs/{field_def['$ref']}"}
        if "description" in field_def:
            # Wrap in allOf so description is preserved alongside $ref
            schema = {"allOf": [schema], "description": field_def["description"]}
        return schema

    field_type = field_def.get("type", "any")

    # Array with items
    if field_type == "array":
        items_def = field_def.get("items", {})
        items_schema = _compile_field(items_def) if items_def else {}
        schema = {"type": "array", "items": items_schema}
    else:
        schema = dict(_PRIMITIVE_MAP.get(field_type, {}))

    # nullable — allow null alongside the declared type
    if field_def.get("nullable"):
        existing_type = schema.get("type")
        if existing_type:
            schema["type"] = [existing_type, "null"]

    # enum
    if "enum" in field_def:
        schema["enum"] = field_def["enum"]

    # default
    if "default" in field_def:
        schema["default"] = field_def["default"]

    # description
    if "description" in field_def:
        schema["description"] = field_def["description"]

    return schema


def _compile_type(type_name: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Translate a YAML ``types`` entry to a JSON Schema object definition."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_def in fields.items():
        if not isinstance(field_def, dict):
            continue
        properties[field_name] = _compile_field(field_def)
        if field_def.get("required"):
            required.append(field_name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        schema["required"] = required
    return schema


def _compile_payload_section(
    section: dict[str, Any],
    defs: dict[str, Any],
) -> dict[str, Any]:
    """Compile a ``payload``, ``request``, or ``response`` section.

    Handles three shapes:
    1. ``{field: {type: ...}, ...}``  – object with properties
    2. ``{$ref: TypeName}``           – reference to a shared type
    3. ``{}``                         – empty (no constraints)
    """
    if not section:
        return {"type": "object", "additionalProperties": True, "$defs": defs}

    # Direct $ref at section level  (e.g. response: {$ref: SceneContext})
    if "$ref" in section and len([k for k in section if k not in ("$ref", "description", "type")]) == 0:
        ref_target = section["$ref"]
        return {
            "allOf": [{"$ref": f"#/$defs/{ref_target}"}],
            "additionalProperties": True,
            "$defs": defs,
        }

    # Special: section-level type/description with no field properties
    # (e.g. characters_alive response is a flat object)
    if "type" in section and not any(
        isinstance(v, dict) and ("type" in v or "$ref" in v)
        for k, v in section.items()
        if k not in ("type", "description")
    ):
        schema: dict[str, Any] = dict(_PRIMITIVE_MAP.get(section["type"], {}))
        if "description" in section:
            schema["description"] = section["description"]
        schema["additionalProperties"] = True
        schema["$defs"] = defs
        return schema

    # Standard: object with properties
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_def in section.items():
        if not isinstance(field_def, dict):
            continue
        properties[field_name] = _compile_field(field_def)
        if field_def.get("required"):
            required.append(field_name)

    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
        "$defs": defs,
    }
    if required:
        schema["required"] = required
    return schema


# ── Public API ──────────────────────────────────────────────────

def compile_schema(yaml_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load ``docs/zmq-api.yaml`` and compile to JSON Schema dicts.

    Parameters
    ----------
    yaml_path : path-like, optional
        Explicit path.  Defaults to ``<project_root>/docs/zmq-api.yaml``.

    Returns
    -------
    dict[str, dict[str, Any]]
        Keyed by topic name (e.g. ``"game.event"``).  Each value is a dict
        with optional keys ``"payload"``, ``"request"``, ``"response"`` — each
        a valid JSON Schema dict.
    """
    if yaml_path is None:
        # Walk up from this file to find project root (contains docs/)
        here = Path(__file__).resolve()
        project_root = here
        for _ in range(10):
            if (project_root / "docs" / "zmq-api.yaml").exists():
                break
            project_root = project_root.parent
        yaml_path = project_root / "docs" / "zmq-api.yaml"

    yaml_path = Path(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 1. Compile shared type definitions → JSON Schema $defs
    defs: dict[str, Any] = {}
    for type_name, fields in (spec.get("types") or {}).items():
        defs[type_name] = _compile_type(type_name, fields)

    # 2. Compile each message
    result: dict[str, dict[str, Any]] = {}
    for topic, msg_def in (spec.get("messages") or {}).items():
        topic_schemas: dict[str, Any] = {}

        if "payload" in msg_def:
            topic_schemas["payload"] = _compile_payload_section(msg_def["payload"], defs)

        if "request" in msg_def:
            topic_schemas["request"] = _compile_payload_section(msg_def["request"], defs)

        if "response" in msg_def:
            topic_schemas["response"] = _compile_payload_section(msg_def["response"], defs)

        result[topic] = topic_schemas

    return result
