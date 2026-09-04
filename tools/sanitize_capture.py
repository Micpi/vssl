#!/usr/bin/env python3
"""Deterministically anonymize a VSSL field capture for sharing."""

from __future__ import annotations

import argparse
import base64
import copy
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any

IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6_RE = re.compile(
    r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?:%[\w.-]+)?(?![\w:])"
)
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")
UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
USN_RE = re.compile(r"(?i)(uuid:)([^:\s]+)")
SENSITIVE_KEYS = {
    "hostname",
    "host_name",
    "friendlyname",
    "friendly-name",
    "device_name",
    "device-name",
    "x-device-name",
    "name",
    "serial",
    "serialnumber",
    "serial-number",
    "x-serial",
    "usn",
    "deviceid",
    "device_id",
    "device-id",
    "fn",
    "room",
    "zone-name",
}


class Sanitizer:
    """Keep stable relationships while replacing private values."""

    def __init__(self) -> None:
        self.maps: dict[str, dict[str, str]] = {
            "ipv4": {},
            "ipv6": {},
            "mac": {},
            "uuid": {},
            "name": {},
            "serial": {},
        }

    def _token(self, kind: str, original: str) -> str:
        values = self.maps[kind]
        if original not in values:
            index = len(values) + 1
            if kind == "ipv4":
                values[original] = f"192.0.2.{min(index + 9, 254)}"
            elif kind == "ipv6":
                values[original] = f"2001:db8::{index}"
            elif kind == "mac":
                values[original] = f"02:00:00:00:00:{index:02x}"
            elif kind == "uuid":
                values[original] = f"00000000-0000-4000-8000-{index:012d}"
            elif kind == "serial":
                values[original] = f"SERIAL-{index:03d}"
            else:
                values[original] = f"DEVICE-NAME-{index:03d}"
        return values[original]

    def _generic_text(self, value: str) -> str:
        """Replace recognizable identifiers in otherwise unstructured text."""

        def replace_ipv6(match: re.Match[str]) -> str:
            candidate = match.group(0)
            address_text = candidate.split("%", 1)[0]
            try:
                address = ipaddress.ip_address(address_text)
            except ValueError:
                return candidate
            if address.is_multicast or address.is_unspecified or address.is_loopback:
                return candidate
            return self._token("ipv6", candidate.lower())

        result = IPV6_RE.sub(replace_ipv6, value)
        result = MAC_RE.sub(
            lambda match: self._token("mac", match.group(0).lower()), result
        )

        def replace_ipv4(match: re.Match[str]) -> str:
            candidate = match.group(0)
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                return candidate
            if address.is_multicast or address.is_unspecified or address.is_loopback:
                return candidate
            return self._token("ipv4", candidate)

        result = IPV4_RE.sub(replace_ipv4, result)
        result = UUID_RE.sub(
            lambda match: self._token("uuid", match.group(0).lower()), result
        )
        return USN_RE.sub(
            lambda match: match.group(1) + self._token("serial", match.group(2)), result
        )

    def text(self, value: str, key: str | None = None) -> str:
        """Sanitize structured text, URLs, and free-form protocol payloads."""
        key_normalized = (key or "").lower().replace("_", "-")
        if key_normalized in SENSITIVE_KEYS and value:
            kind = (
                "serial"
                if "serial" in key_normalized or key_normalized == "usn"
                else "name"
            )
            if key_normalized == "usn":
                sanitized_usn = USN_RE.sub(
                    lambda match: (
                        match.group(1) + self._token("serial", match.group(2))
                    ),
                    value,
                )
                return (
                    sanitized_usn
                    if sanitized_usn != value
                    else self._token("serial", value)
                )
            return self._token(kind, value)

        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed_json = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                return json.dumps(self.value(parsed_json), ensure_ascii=False)

        lines: list[str] = []
        in_body = False
        body_lines: list[str] = []
        for line in value.replace("\r\n", "\n").split("\n"):
            if in_body:
                body_lines.append(line)
                continue
            if line == "":
                in_body = True
                lines.append(line)
                continue
            if ":" in line:
                header, header_value = line.split(":", 1)
                normalized = header.strip().lower()
                if normalized in SENSITIVE_KEYS and header_value.strip():
                    header_value = " " + self.text(header_value.strip(), normalized)
                line = f"{header}:{header_value}"
            lines.append(self._generic_text(line))
        newline = "\r\n" if "\r\n" in value else "\n"
        if body_lines:
            body = newline.join(body_lines)
            stripped_body = body.strip()
            if stripped_body.startswith(("{", "[")):
                try:
                    parsed_body = json.loads(body)
                except json.JSONDecodeError:
                    clean_body = self._generic_text(body)
                else:
                    clean_body = json.dumps(self.value(parsed_body), ensure_ascii=False)
            else:
                clean_body = self._generic_text(body)
            lines.extend(clean_body.split(newline))
        return newline.join(lines)

    def value(self, value: Any, key: str | None = None) -> Any:
        """Recursively sanitize JSON-compatible data."""
        if isinstance(value, dict):
            if "name_normalized" in value and "value" in value:
                # A parsed protocol header: keep its structural name and apply
                # sensitivity rules using that header name to its value.
                return {
                    item_key: (
                        self.text(str(item_value), str(value["name_normalized"]))
                        if item_key == "value"
                        else self.value(item_value, None)
                    )
                    for item_key, item_value in value.items()
                }
            return {
                item_key: self.value(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [self.value(item, key) for item in value]
        if isinstance(value, str):
            return self.text(value, key)
        return value


def sanitize_document(document: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a capture and rebuild raw Base64 from sanitized text."""
    sanitizer = Sanitizer()
    sanitized = sanitizer.value(copy.deepcopy(document))
    sanitized["sensitivity"] = "SANITIZED_SHAREABLE"
    sanitized.pop("sanitization_map", None)
    for index, response in enumerate(sanitized.get("responses", [])):
        if not isinstance(response, dict):
            continue
        original_response = document.get("responses", [])[index]
        original_text = (
            original_response.get("decoded_text", "")
            if isinstance(original_response, dict)
            else ""
        )
        clean_text = sanitizer.text(str(original_text))
        response["decoded_text"] = clean_text
        response["raw_base64"] = base64.b64encode(clean_text.encode("utf-8")).decode(
            "ascii"
        )
        response["raw_reconstructed_from_sanitized_text"] = True
    for index, request in enumerate(sanitized.get("requests", [])):
        if not isinstance(request, dict) or "payload_base64" not in request:
            continue
        original_request = document.get("requests", [])[index]
        try:
            original_payload = base64.b64decode(
                original_request["payload_base64"], validate=True
            )
            clean_payload = sanitizer.text(
                original_payload.decode("utf-8", errors="replace")
            )
            request["payload_base64"] = base64.b64encode(
                clean_payload.encode("utf-8")
            ).decode("ascii")
            request["payload_reconstructed_from_sanitized_text"] = True
        except (KeyError, TypeError, ValueError):
            request.pop("payload_base64", None)
            request["payload_removed_during_sanitization"] = True
    sanitized["anonymization"] = {
        "deterministic_within_capture": True,
        "raw_bytes_reconstructed": True,
        "replacement_counts": {
            key: len(value) for key, value in sanitizer.maps.items()
        },
    }
    return sanitized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw capture JSON")
    parser.add_argument(
        "output", type=Path, help="Shareable sanitized JSON (must not exist)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.is_file():
        print(f"Input does not exist: {args.input}", file=sys.stderr)
        return 3
    if args.output.exists():
        print(f"Refusing to overwrite: {args.output}", file=sys.stderr)
        return 3
    try:
        document = json.loads(args.input.read_text(encoding="utf-8"))
        sanitized = sanitize_document(document)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Sanitization failed: {exc}", file=sys.stderr)
        return 3
    print(f"Shareable capture written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
