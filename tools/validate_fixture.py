#!/usr/bin/env python3
"""Validate a capture fixture with the integration's real parser."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_ROOT / "custom_components" / "vssl"))
from protocol import KNOWN_HEADER_MEANINGS, parse_capture_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Capture or fixture JSON")
    parser.add_argument("--output", type=Path, help="Optional normalized JSON output")
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Optional baseline fixture used to list new and missing headers",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.fixture.is_file():
        print(f"Fixture does not exist: {args.fixture}", file=sys.stderr)
        return 3
    try:
        document = json.loads(args.fixture.read_text(encoding="utf-8"))
        normalized = parse_capture_document(document)
        normalized["header_analysis"] = {
            "known_meanings": {
                name: KNOWN_HEADER_MEANINGS[name]
                for name in normalized["header_names"]
                if name in KNOWN_HEADER_MEANINGS
            },
            "unknown_meaning": sorted(
                set(normalized["header_names"]) - set(KNOWN_HEADER_MEANINGS)
            ),
        }
        if args.baseline:
            baseline_document = json.loads(args.baseline.read_text(encoding="utf-8"))
            baseline = parse_capture_document(baseline_document)
            current_headers = set(normalized["header_names"])
            baseline_headers = set(baseline["header_names"])
            normalized["baseline_comparison"] = {
                "baseline": str(args.baseline),
                "new_headers": sorted(current_headers - baseline_headers),
                "missing_headers": sorted(baseline_headers - current_headers),
            }
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Fixture validation failed: {exc}", file=sys.stderr)
        return 3
    output = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
    print(output, end="")
    if args.output:
        if args.output.exists():
            print(f"Refusing to overwrite: {args.output}", file=sys.stderr)
            return 3
        args.output.write_text(output, encoding="utf-8")
    return 0 if normalized["vssl_response_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
