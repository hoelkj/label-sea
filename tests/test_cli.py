from pathlib import Path

from label_sea.cli import main


def test_validate_command_reports_component_summary(capsys) -> None:
    exit_code = main(["validate", "--input", "examples/template.yaml"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Valid YAML" in output
    assert "sea-125: Erzeuger" in output


def test_build_command_writes_svg_and_pdf(tmp_path: Path) -> None:
    exit_code = main(
        [
            "build",
            "--input",
            "examples/template.yaml",
            "--output-dir",
            str(tmp_path),
            "--band-height",
            "50",
            "--pdf",
            "a4",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "svg" / "sea-125.svg").exists()
    assert (tmp_path / "labels-a4.pdf").exists()


def test_build_command_warns_when_a4_escalates_to_a3(tmp_path: Path, capsys) -> None:
    yaml_file = tmp_path / "wide.yaml"
    yaml_file.write_text(
        """
components:
  - key: extra-wide
    name: Sehr breiter Erzeuger
    type: erzeuger
    outputs:
""".strip()
        + "\n"
        + "\n".join("      - kind: CEE\n        ampere: 63" for _ in range(24)),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "build",
            "--input",
            str(yaml_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--band-height",
            "50",
            "--pdf",
            "a4",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "warning: Requested A4 PDF was too narrow; using A3 landscape instead." in output
