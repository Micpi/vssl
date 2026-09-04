"""Tests for the shared capture parser."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.vssl.protocol import (
    KNOWN_HEADER_MEANINGS,
    build_discovery_request,
    parse_capture_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_synthetic_fixture_is_recognized() -> None:
    document = json.loads(
        (FIXTURES / "synthetic_capture.json").read_text(encoding="utf-8")
    )
    normalized = parse_capture_document(document)
    assert normalized["response_count"] == 1
    assert normalized["vssl_response_count"] == 1
    assert normalized["responses"][0]["identity"]["model"] == "MS.1"
    assert "usn" in normalized["header_names"]
    assert "usn" in KNOWN_HEADER_MEANINGS


def test_discovery_requests_are_non_destructive() -> None:
    for port in (1800, 1900):
        request = build_discovery_request(port).decode("ascii")
        assert request.startswith("M-SEARCH * HTTP/1.1")
        assert f":{port}" in request
        for forbidden in ("(QRY)", "reset", "firmware", "rename"):
            assert forbidden not in request.lower()
        assert "vssl" not in request.lower()
