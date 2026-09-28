from pathlib import Path

import pytest

from label_sea.models import ValidationError, load_project, load_project_data, validate_project_data


def test_load_project_from_example() -> None:
    project = load_project(Path("examples/template.yaml"))

    assert project.title == "Beispiel Aufbau"
    assert len(project.components) == 3
    assert project.components[0].outputs[0].short_name == "CEE 125A"
    assert project.components[1].outputs[-1].short_name == "Schuko"


def test_count_expands_ports(tmp_path: Path) -> None:
    yaml_file = tmp_path / "count.yaml"
    yaml_file.write_text(
        """
connectors:
  cee63:
    kind: CEE
    ampere: 63
components:
  - name: Verteiler A
    type: verteiler
    inputs:
      - ref: cee63
    outputs:
      - ref: cee63
        count: 3
""".strip(),
        encoding="utf-8",
    )

    project = load_project(yaml_file)

    assert len(project.components[0].outputs) == 3
    assert all(port.short_name == "CEE 63A" for port in project.components[0].outputs)


def test_duplicate_component_key_fails(tmp_path: Path) -> None:
    yaml_file = tmp_path / "duplicate.yaml"
    yaml_file.write_text(
        """
title: Demo
connectors:
  cee32:
    kind: CEE
    ampere: 32
components:
  - key: same
    name: A
    type: erzeuger
    outputs:
      - ref: cee32
  - key: same
    name: B
    type: verbraucher
    inputs:
      - ref: cee32
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Duplicate component key 'same'"):
        load_project(yaml_file)


def test_schema_validation_reports_unknown_field(tmp_path: Path) -> None:
    yaml_file = tmp_path / "unknown-field.yaml"
    yaml_file.write_text(
        """
components:
  - name: SEA 1
    type: erzeuger
    color: blue
    outputs:
      - kind: CEE
        ampere: 63
""".strip(),
        encoding="utf-8",
    )

    raw = load_project_data(yaml_file)

    with pytest.raises(ValidationError, match="Schema validation failed"):
        validate_project_data(raw)


def test_unknown_connector_reference_fails(tmp_path: Path) -> None:
    yaml_file = tmp_path / "unknown-ref.yaml"
    yaml_file.write_text(
        """
components:
  - name: SEA 1
    type: erzeuger
    outputs:
      - ref: cee63
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unknown connector 'cee63'"):
        load_project(yaml_file)


def test_invalid_cee_ampere_fails(tmp_path: Path) -> None:
    yaml_file = tmp_path / "invalid-cee.yaml"
    yaml_file.write_text(
        """
connectors:
  cee50:
    kind: CEE
    ampere: 50
components:
  - name: SEA 1
    type: erzeuger
    outputs:
      - ref: cee50
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Allowed values are 16, 32, 63, 125"):
        load_project(yaml_file)


def test_label_field_is_rejected_by_schema(tmp_path: Path) -> None:
    yaml_file = tmp_path / "label.yaml"
    yaml_file.write_text(
        """
connectors:
  cee63:
    kind: CEE
    ampere: 63
components:
  - name: SEA 1
    type: erzeuger
    outputs:
      - ref: cee63
        label: Reserve
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Schema validation failed"):
        load_project(yaml_file)
