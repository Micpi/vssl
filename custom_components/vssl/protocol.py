"""Pure-Python VSSL/SSDP discovery protocol helpers.

This module deliberately has no Home Assistant dependency. The field tools import
this exact file so captures and the integration cannot silently develop different
parsers.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

SSDP_MULTICAST_HOST = "239.255.255.250"
DISCOVERY_PORTS = (1800, 1900)
KNOWN_HEADER_MEANINGS = {
    "cache-control": "SSDP cache lifetime",
    "ext": "SSDP extension marker",
    "location": "UPnP description URL",
    "server": "product/protocol identification",
    "st": "SSDP search target",
    "usn": "UPnP unique service name",
    "x-device-name": "provisional device label from synthetic fixture",
    "x-model": "provisional model field from synthetic fixture",
    "x-serial": "provisional serial field from synthetic fixture",
}

_HEADER_RE = re.compile(r"^([^:\s][^:]*):\s*(.*)$")
_MODEL_KEYS = ("model", "x-model", "modelname", "model-name")
_NAME_KEYS = ("friendlyname", "friendly-name", "x-device-name", "name")
_SERIAL_KEYS = ("serial", "serialnumber", "serial-number", "x-serial")


def build_discovery_request(port: int) -> bytes:
    """Build the non-destructive discovery request used on a UDP port."""
    if port not in DISCOVERY_PORTS:
        raise ValueError(f"Unsupported VSSL discovery port: {port}")
    # SSDP's HOST header names the multicast endpoint even when this request is
    # sent by unicast to a user-provided target for focused troubleshooting.
    host = SSDP_MULTICAST_HOST
    lines = (
        "M-SEARCH * HTTP/1.1",
        f"HOST: {host}:{port}",
        'MAN: "ssdp:discover"',
        "MX: 2",
        "ST: ssdp:all",
        "USER-AGENT: ms1-field-probe/0.1",
        "",
        "",
    )
    return "\r\n".join(lines).encode("ascii")


def _header_map(headers: Iterable[Mapping[str, str]]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for header in headers:
        key = header["name_normalized"]
        values.setdefault(key, []).append(header["value"])
    return values


def _first(headers: Mapping[str, list[str]], keys: Iterable[str]) -> str | None:
    for key in keys:
        values = headers.get(key)
        if values:
            return values[0]
    return None


def parse_datagram(payload: bytes) -> dict[str, Any]:
    """Parse one discovery datagram into a stable, JSON-compatible structure."""
    text = payload.decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start_line = lines[0].strip() if lines else ""
    headers: list[dict[str, str]] = []
    body_lines: list[str] = []
    in_body = False
    for line in lines[1:]:
        if in_body:
            body_lines.append(line)
            continue
        if not line:
            in_body = True
            continue
        match = _HEADER_RE.match(line)
        if match:
            name = match.group(1).strip()
            headers.append(
                {
                    "name": name,
                    "name_normalized": name.lower(),
                    "value": match.group(2).strip(),
                }
            )
        else:
            body_lines.append(line)

    header_values = _header_map(headers)
    body = "\n".join(body_lines).strip()
    json_body: Any = None
    if body:
        try:
            json_body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass
    elif text.lstrip().startswith(("{", "[")):
        try:
            json_body = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

    searchable = text.lower()
    is_vssl = "vssl" in searchable
    protocol = (
        "ssdp" if start_line.startswith(("HTTP/", "M-SEARCH", "NOTIFY")) else "text"
    )
    if json_body is not None:
        protocol = "json"

    model = _first(header_values, _MODEL_KEYS)
    name = _first(header_values, _NAME_KEYS)
    serial = _first(header_values, _SERIAL_KEYS)
    if isinstance(json_body, Mapping):
        lowered = {str(key).lower(): value for key, value in json_body.items()}
        model = model or next(
            (str(lowered[key]) for key in _MODEL_KEYS if key in lowered), None
        )
        name = name or next(
            (str(lowered[key]) for key in _NAME_KEYS if key in lowered), None
        )
        serial = serial or next(
            (str(lowered[key]) for key in _SERIAL_KEYS if key in lowered), None
        )
        is_vssl = is_vssl or str(lowered.get("manufacturer", "")).lower().startswith(
            "vssl"
        )

    return {
        "protocol": protocol,
        "start_line": start_line,
        "headers": headers,
        "header_names": sorted(header_values),
        "body": body,
        "json_body": json_body,
        "is_vssl": is_vssl,
        "identity": {
            "model": model,
            "name": name,
            "serial": serial,
            "usn": _first(header_values, ("usn",)),
            "location": _first(header_values, ("location",)),
            "server": _first(header_values, ("server",)),
        },
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }


def parse_capture_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Run all captured responses through the real datagram parser."""
    responses = document.get("responses", [])
    normalized: list[dict[str, Any]] = []
    all_headers: set[str] = set()
    for index, response in enumerate(responses):
        if not isinstance(response, Mapping):
            continue
        raw_b64 = response.get("raw_base64")
        if isinstance(raw_b64, str):
            try:
                payload = base64.b64decode(raw_b64, validate=True)
            except (ValueError, TypeError):
                payload = str(response.get("decoded_text", "")).encode("utf-8")
        else:
            payload = str(response.get("decoded_text", "")).encode("utf-8")
        parsed = parse_datagram(payload)
        parsed["capture_index"] = index
        parsed["source_port"] = response.get("source_port")
        parsed["destination_port"] = response.get("destination_port")
        parsed["occurrence_count"] = response.get("occurrence_count", 1)
        normalized.append(parsed)
        all_headers.update(parsed["header_names"])
    return {
        "schema_version": 1,
        "response_count": len(normalized),
        "vssl_response_count": sum(1 for item in normalized if item["is_vssl"]),
        "header_names": sorted(all_headers),
        "responses": normalized,
    }


def diagnostics_view(parsed: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a privacy-conscious diagnostic view of parsed discovery data."""
    if not parsed:
        return {}
    identity = (
        parsed.get("identity") if isinstance(parsed.get("identity"), Mapping) else {}
    )
    return {
        "protocol": parsed.get("protocol"),
        "is_vssl": parsed.get("is_vssl"),
        "header_names": list(parsed.get("header_names", [])),
        "model": identity.get("model"),
        "has_name": bool(identity.get("name")),
        "has_serial": bool(identity.get("serial") or identity.get("usn")),
        "has_location": bool(identity.get("location")),
    }
