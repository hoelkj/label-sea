from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


class ValidationError(ValueError):
    pass


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "components.schema.json"
_SCHEMA_CACHE: dict[str, object] | None = None


TYPE_ALIASES = {
    "generator": "generator",
    "erzeuger": "generator",
    "consumer": "consumer",
    "verbraucher": "consumer",
    "distributor": "distributor",
    "verteiler": "distributor",
}


@dataclass(slots=True)
class Port:
    kind: str
    ampere: int
    style: str = "solid"

    @property
    def short_name(self) -> str:
        normalized_kind = self.kind.strip().lower()
        if normalized_kind == "schuko":
            return "Schuko"
        elif normalized_kind == "cee":
            kind_label = "CEE"
        else:
            kind_label = self.kind.strip()
        return f"{kind_label} {self.ampere}A"


@dataclass(slots=True)
class Component:
    key: str
    name: str
    type: str
    apparent_kva: float | None = None
    active_kw: float | None = None
    inputs: list[Port] = field(default_factory=list)
    outputs: list[Port] = field(default_factory=list)

    @property
    def type_label(self) -> str:
        return {
            "generator": "Erzeuger",
            "consumer": "Verbraucher",
            "distributor": "Verteiler",
        }[self.type]

    @property
    def power_label(self) -> str:
        parts: list[str] = []
        if self.apparent_kva is not None:
            parts.append(f"{self.apparent_kva:g} kVA")
        if self.active_kw is not None:
            parts.append(f"{self.active_kw:g} kW")
        return " | ".join(parts)


@dataclass(slots=True)
class Project:
    title: str
    components: list[Component]


@dataclass(slots=True)
class ConnectorDefinition:
    key: str
    kind: str
    ampere: int
    style: str = "solid"


def load_project(path: Path) -> Project:
    raw = load_project_data(path)
    validate_project_data(raw)

    title = str(raw.get("title") or "label-sea")
    connectors = parse_connectors(raw.get("connectors") or {})
    raw_components = raw.get("components")
    components = [
        parse_component(index, item, connectors)
        for index, item in enumerate(raw_components, start=1)
    ]
    return Project(title=title, components=components)


def load_project_data(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValidationError("Root YAML node must be a mapping.")

    return raw


def validate_project_data(raw: dict[str, object]) -> None:
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(raw), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(format_schema_error(error) for error in errors[:5])
        raise ValidationError(f"Schema validation failed: {details}")

    raw_components = raw.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise ValidationError("YAML must contain a non-empty 'components' list.")

    keys_seen: set[str] = set()
    for index, item in enumerate(raw_components, start=1):
        if not isinstance(item, dict):
            continue
        raw_key = item.get("key")
        if raw_key is None:
            continue
        key = str(raw_key)
        if key in keys_seen:
            raise ValidationError(f"Duplicate component key '{key}' at position {index}.")
        keys_seen.add(key)


def load_schema() -> dict[str, object]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
            _SCHEMA_CACHE = json.load(handle)
    return _SCHEMA_CACHE


def format_schema_error(error: object) -> str:
    path = ".".join(str(part) for part in error.path) or "<root>"
    return f"{path}: {error.message}"


def parse_component(
    index: int,
    raw: object,
    connectors: dict[str, ConnectorDefinition],
) -> Component:
    if not isinstance(raw, dict):
        raise ValidationError(f"Component #{index} must be a mapping.")

    key = str(raw.get("key") or f"component-{index}")
    name = str(raw.get("name") or "")
    if not name:
        raise ValidationError(f"Component '{key}' is missing a name.")

    raw_type = str(raw.get("type") or "").strip().lower()
    normalized_type = TYPE_ALIASES.get(raw_type)
    if normalized_type is None:
        raise ValidationError(
            f"Component '{key}' has invalid type '{raw_type}'. "
            "Use generator/consumer/distributor or erzeuger/verbraucher/verteiler."
        )

    inputs = parse_ports(key, "inputs", raw.get("inputs") or [], connectors)
    outputs = parse_ports(key, "outputs", raw.get("outputs") or [], connectors)

    if normalized_type == "generator" and not outputs:
        raise ValidationError(f"Generator '{key}' must define at least one output.")
    if normalized_type == "consumer" and not inputs:
        raise ValidationError(f"Consumer '{key}' must define at least one input.")
    if normalized_type == "distributor" and not (inputs and outputs):
        raise ValidationError(f"Distributor '{key}' must define at least one input and one output.")

    power = raw.get("power") or {}
    if power and not isinstance(power, dict):
        raise ValidationError(f"Component '{key}' field 'power' must be a mapping.")

    apparent_kva = (
        optional_number(power, "apparent_kva", f"{key}.power.apparent_kva")
        if power
        else None
    )
    active_kw = optional_number(power, "active_kw", f"{key}.power.active_kw") if power else None

    return Component(
        key=key,
        name=name,
        type=normalized_type,
        apparent_kva=apparent_kva,
        active_kw=active_kw,
        inputs=inputs,
        outputs=outputs,
    )


def parse_connectors(raw: object) -> dict[str, ConnectorDefinition]:
    if not isinstance(raw, dict):
        raise ValidationError("Field 'connectors' must be a mapping.")

    connectors: dict[str, ConnectorDefinition] = {}
    for key, item in raw.items():
        if not isinstance(item, dict):
            raise ValidationError(f"Connector '{key}' must be a mapping.")
        kind = str(item.get("kind") or "").strip()
        if not kind:
            raise ValidationError(f"Connector '{key}' is missing 'kind'.")
        ampere = item.get("ampere")
        if not isinstance(ampere, int) or ampere <= 0:
            raise ValidationError(f"Connector '{key}' needs a positive integer 'ampere'.")
        style = normalize_style(item.get("style"), f"connectors.{key}")
        validate_connector(kind, ampere, f"connectors.{key}")
        connectors[key] = ConnectorDefinition(
            key=key,
            kind=kind,
            ampere=ampere,
            style=style,
        )
    return connectors


def parse_ports(
    component_key: str,
    field_name: str,
    raw: object,
    connectors: dict[str, ConnectorDefinition],
) -> list[Port]:
    if not isinstance(raw, list):
        raise ValidationError(f"Component '{component_key}' field '{field_name}' must be a list.")

    ports: list[Port] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValidationError(
                f"Component '{component_key}' field '{field_name}' entry #{index} "
                "must be a mapping."
            )
        if "ref" in item:
            ports.extend(parse_port_reference(component_key, field_name, index, item, connectors))
            continue

        kind = str(item.get("kind") or "").strip()
        if not kind:
            raise ValidationError(
                f"Component '{component_key}' field '{field_name}' entry #{index} "
                "is missing 'kind'."
            )
        ampere = item.get("ampere")
        if not isinstance(ampere, int) or ampere <= 0:
            raise ValidationError(
                f"Component '{component_key}' field '{field_name}' entry #{index} needs "
                "a positive integer 'ampere'."
            )
        count = parse_port_count(component_key, field_name, index, item)
        style = normalize_style(item.get("style"), f"{component_key}.{field_name}[{index}]")
        validate_connector(kind, ampere, f"{component_key}.{field_name}[{index}]")
        ports.extend(Port(kind=kind, ampere=ampere, style=style) for _ in range(count))
    return ports


def parse_port_reference(
    component_key: str,
    field_name: str,
    index: int,
    raw: dict[str, object],
    connectors: dict[str, ConnectorDefinition],
) -> list[Port]:
    ref = str(raw.get("ref") or "").strip()
    if not ref:
        raise ValidationError(
            f"Component '{component_key}' field '{field_name}' entry #{index} is missing 'ref'."
        )
    if ref not in connectors:
        raise ValidationError(
            f"Component '{component_key}' field '{field_name}' entry #{index} references "
            f"unknown connector '{ref}'."
        )

    count = parse_port_count(component_key, field_name, index, raw)
    connector = connectors[ref]
    return [
        Port(
            kind=connector.kind,
            ampere=connector.ampere,
            style=connector.style,
        )
        for _ in range(count)
    ]


def parse_port_count(
    component_key: str,
    field_name: str,
    index: int,
    raw: dict[str, object],
) -> int:
    count = raw.get("count", 1)
    if not isinstance(count, int) or count <= 0:
        raise ValidationError(
            f"Component '{component_key}' field '{field_name}' entry #{index} needs "
            "a positive integer 'count'."
        )
    return count


def validate_connector(kind: str, ampere: int, path: str) -> None:
    normalized_kind = kind.strip().lower()
    if normalized_kind == "cee" and ampere not in {16, 32, 63, 125}:
        raise ValidationError(
            f"Field '{path}' uses unsupported CEE ampere '{ampere}'. "
            "Allowed values are 16, 32, 63, 125."
        )
    if normalized_kind == "schuko" and ampere != 16:
        raise ValidationError(
            f"Field '{path}' uses unsupported Schuko ampere '{ampere}'. "
            "Schuko must be defined as 16A."
        )


def normalize_style(value: object, path: str) -> str:
    if value is None:
        return "solid"
    style = str(value).strip().lower()
    if style not in {"solid", "dashed", "fine-dashed"}:
        raise ValidationError(
            f"Field '{path}' uses unsupported style '{style}'. "
            "Allowed values are solid, dashed, fine-dashed."
        )
    return style


def coerce_number(value: object, path: str) -> float:
    if value is None:
        raise ValidationError(f"Missing numeric value for '{path}'.")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValidationError(f"Field '{path}' must be numeric.")


def optional_number(raw: dict[str, object], key: str, path: str) -> float | None:
    if key not in raw or raw[key] is None:
        return None
    return coerce_number(raw[key], path)
