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

    tests = normalize_text(args.tests)
    coverage = normalize_text(args.coverage)
    quality = normalize_text(args.quality)
    image_size = normalize_text(args.image_size)
    sbom_packages = normalize_text(args.sbom_packages)
    critical = normalize_number_text(args.critical)
    high = normalize_number_text(args.high)

    write_badge(output_dir, "tests", "tests", tests, status_color(tests))
    write_badge(output_dir, "coverage", "coverage", coverage, coverage_color(coverage))
    write_badge(output_dir, "quality", "quality", quality, status_color(quality))
    write_badge(output_dir, "image-size", "image size", image_size, "blue")
    write_badge(output_dir, "sbom", "SBOM", sbom_packages, "informational")
    write_badge(
        output_dir,
        "critical-cves",
        "critical CVEs",
        critical,
        severity_color(critical),
    )
    write_badge(output_dir, "high-cves", "high CVEs", high, severity_color(high))
    return 0


def coverage_color(coverage: str) -> str:
    if not coverage.endswith("%"):
        return "lightgrey"

    try:
        value = int(coverage.rstrip("%"))
    except ValueError:
        return "lightgrey"

    if value >= 90:
        return "brightgreen"
    if value >= 80:
        return "green"
    if value >= 70:
        return "yellow"
    return "red"


def severity_color(count: str) -> str:
    try:
        value = int(count)
    except ValueError:
        return "lightgrey"

    if value == 0:
        return "brightgreen"
    if value <= 3:
        return "yellow"
    return "red"


def status_color(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"unknown", "n/a", ""}:
        return "lightgrey"
    return "brightgreen"


def normalize_text(value: str) -> str:
    stripped = value.strip()
    return stripped or "unknown"


def normalize_number_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "unknown"
    return stripped


if __name__ == "__main__":
    raise SystemExit(main())