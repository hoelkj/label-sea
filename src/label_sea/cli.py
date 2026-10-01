from __future__ import annotations

import argparse
import re
from pathlib import Path

from label_sea.models import ValidationError, load_project, load_project_data, validate_project_data
from label_sea.render import render_component_svg, render_pdf


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return build_command(args)
    if args.command == "validate":
        return validate_command(args)

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="label-sea")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser(
        "build",
        help="Render SVG labels from a YAML component file",
    )
    build_parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the YAML component file",
    )
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build"),
        help="Directory for generated files",
    )
    build_parser.add_argument(
        "--band-height",
        type=int,
        choices=(40, 50),
        default=50,
        help="Magnet band height in mm",
    )
    build_parser.add_argument(
        "--pdf",
        choices=("a4", "a3"),
        help="Optionally generate a combined PDF in the selected paper size",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a YAML component file",
    )
    validate_parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the YAML component file",
    )
    return parser


def build_command(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.input)
    except (OSError, ValidationError) as error:
        print(f"error: {error}")
        return 2

    output_dir: Path = args.output_dir
    svg_dir = output_dir / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    layouts = []
    for component in project.components:
        file_name = f"{slugify(component.key)}.svg"
        layout = render_component_svg(component, args.band_height, svg_dir / file_name)
        layouts.append(layout)

    if args.pdf:
        pdf_path = output_dir / f"labels-{args.pdf}.pdf"
        pdf_plan = render_pdf(layouts, args.pdf, pdf_path)

    print(f"Generated {len(layouts)} SVG label(s) in {svg_dir}")
    if args.pdf:
        print(f"Generated PDF layout: {output_dir / ('labels-' + args.pdf + '.pdf')}")
        if pdf_plan.warning:
            print(f"warning: {pdf_plan.warning}")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    try:
        raw = load_project_data(args.input)
        validate_project_data(raw)
        project = load_project(args.input)
    except (OSError, ValidationError) as error:
        print(f"error: {error}")
        return 2

    print(f"Valid YAML: {args.input}")
    print(f"Components: {len(project.components)}")
    for component in project.components:
        print(
            f"- {component.key}: {component.type_label} "
            f"({len(component.inputs)} in / {len(component.outputs)} out)"
        )
    return 0


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return normalized.lower() or "component"
