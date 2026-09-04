"""Tests for deterministic capture anonymization."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from sanitize_capture import sanitize_document


def test_sanitizer_removes_originals_and_rebuilds_base64() -> None:
    payload = (
        "HTTP/1.1 200 OK\r\nLOCATION: http://10.23.45.67/device.xml\r\n"
        "X-Device-Name: Living Room\r\nUSN: uuid:abc123::device\r\n"
        "X-MAC: AA:BB:CC:DD:EE:FF\r\nSERVER: VSSL/MS.1\r\n\r\n"
    )
    document = {
        "probe": {
            "hostname": "private-pc",
            "target": "10.23.45.67",
            "interfaces": [{"address": "fd12:3456::20"}],
        },
        "responses": [
            {
                "source_address": "10.23.45.67",
                "decoded_text": payload,
                "raw_base64": base64.b64encode(payload.encode()).decode(),
                "parsed_headers": [
                    {
                        "name": "X-Device-Name",
                        "name_normalized": "x-device-name",
                        "value": "Living Room",
                    }
                ],
            },
            {
                "source_address": "10.23.45.67",
                "decoded_text": payload,
                "raw_base64": base64.b64encode(payload.encode()).decode(),
            },
        ],
    }
    clean = sanitize_document(document)
    serialized = str(clean)
    for original in (
        "10.23.45.67",
        "Living Room",
        "private-pc",
        "AA:BB:CC:DD:EE:FF",
        "abc123",
        "fd12:3456::20",
    ):
        assert original not in serialized
    assert (
        clean["responses"][0]["source_address"]
        == clean["responses"][1]["source_address"]
    )
    decoded = base64.b64decode(clean["responses"][0]["raw_base64"]).decode()
    assert "Living Room" not in decoded
    assert "DEVICE-NAME-" in decoded
