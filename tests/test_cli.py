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
