from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_badge(output_dir: Path, name: str, label: str, message: str, color: str) -> None:
    payload = {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color,
    }
    (output_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--quality", required=True)
    parser.add_argument("--image-size", required=True)
    parser.add_argument("--sbom-packages", required=True)
    parser.add_argument("--critical", required=True)
    parser.add_argument("--high", required=True)
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_badge(output_dir, "tests", "tests", args.tests, "brightgreen")
    write_badge(output_dir, "coverage", "coverage", args.coverage, coverage_color(args.coverage))
    write_badge(output_dir, "quality", "quality", args.quality, "brightgreen")
    write_badge(output_dir, "image-size", "image size", args.image_size, "blue")
    write_badge(output_dir, "sbom", "SBOM", args.sbom_packages, "informational")
    write_badge(
        output_dir,
        "critical-cves",
        "critical CVEs",
        args.critical,
        severity_color(args.critical),
    )
    write_badge(output_dir, "high-cves", "high CVEs", args.high, severity_color(args.high))
    return 0


def coverage_color(coverage: str) -> str:
    value = int(coverage.rstrip("%"))
    if value >= 90:
        return "brightgreen"
    if value >= 80:
        return "green"
    if value >= 70:
        return "yellow"
    return "red"


def severity_color(count: str) -> str:
    value = int(count)
    if value == 0:
        return "brightgreen"
    if value <= 3:
        return "yellow"
    return "red"


if __name__ == "__main__":
    raise SystemExit(main())