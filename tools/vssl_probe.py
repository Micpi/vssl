#!/usr/bin/env python3
"""Safe standalone VSSL MS.1 field probe (Python 3.11+, no HA required)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import platform
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_ROOT / "custom_components" / "vssl"))
from protocol import (
    DISCOVERY_PORTS,
    SSDP_MULTICAST_HOST,
    build_discovery_request,
    parse_datagram,
)
from sanitize_capture import sanitize_document

VERSION = "0.1.0"
TCP_PORTS = (80, 443, 7777, 8009, 50002, 50006)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def marker(message: str) -> None:
    print(f"[{utc_now()}] {message}", flush=True)


def valid_target(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target must be an IPv4 address") from exc
    if address.version != 4 or address.is_multicast or address.is_unspecified:
        raise argparse.ArgumentTypeError("target must be a unicast IPv4 address")
    return str(address)


def available_output_dir(requested: Path) -> Path:
    if not requested.exists():
        return requested
    for index in range(1, 1000):
        candidate = requested.with_name(f"{requested.name}-{index:03d}")
        if not candidate.exists():
            return candidate
    raise OSError("No unused output directory suffix available")


def local_interfaces() -> list[dict[str, str]]:
    """Collect useful addresses with stdlib only; interface labels may be unavailable."""
    records: list[dict[str, str]] = []
    seen: set[tuple[int, str]] = set()
    hostname = socket.gethostname()
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_DGRAM)
    except OSError:
        infos = []
    for family, _socktype, _proto, _canonname, sockaddr in infos:
        address = sockaddr[0]
        key = (family, address)
        if key in seen or address.startswith("127.") or address == "::1":
            continue
        seen.add(key)
        records.append(
            {
                "interface": "name-unavailable-via-stdlib",
                "family": "IPv6" if family == socket.AF_INET6 else "IPv4",
                "address": address,
            }
        )
    return records


def collect_udp(
    port: int, target: str | None, timeout: float
) -> tuple[list[dict[str, Any]], str | None]:
    destination = target or SSDP_MULTICAST_HOST
    request = build_discovery_request(port)
    marker(f"UDP/{port} send start destination={destination}:{port}")
    records: list[dict[str, Any]] = []
    error: str | None = None
    started = time.monotonic()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind(("", 0))
            sock.sendto(request, (destination, port))
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    payload, source = sock.recvfrom(65535)
                except TimeoutError:
                    break
                received_at = utc_now()
                parsed = parse_datagram(payload)
                records.append(
                    {
                        "received_at": received_at,
                        "source_address": source[0],
                        "source_port": source[1],
                        "destination_port": port,
                        "raw_base64": base64.b64encode(payload).decode("ascii"),
                        "decoded_text": payload.decode("utf-8", errors="replace"),
                        "parsed_headers": parsed["headers"],
                        "parsed": parsed,
                    }
                )
                marker(f"UDP/{port} datagram received source={source[0]}:{source[1]}")
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"
        marker(f"UDP/{port} error={error}")
    marker(
        f"UDP/{port} complete responses={len(records)} duration_ms={(time.monotonic() - started) * 1000:.1f}"
    )
    return records, error


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for record in records:
        digest = hashlib.sha256(base64.b64decode(record["raw_base64"])).hexdigest()
        key = (
            digest,
            record["source_address"],
            record["source_port"],
            record["destination_port"],
        )
        if key not in unique:
            item = dict(record)
            item["occurrence_count"] = 1
            item["occurrence_times"] = [record["received_at"]]
            unique[key] = item
        else:
            unique[key]["occurrence_count"] += 1
            unique[key]["occurrence_times"].append(record["received_at"])
    return list(unique.values())


def tcp_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    marker(f"TCP/{port} connect-only start target={host}")
    started = time.monotonic()
    status = "network_error"
    detail: str | None = None
    try:
        with socket.create_connection((host, port), timeout=timeout):
            status = "success"
    except ConnectionRefusedError as exc:
        status, detail = "refused", str(exc)
    except TimeoutError as exc:
        status, detail = "timeout", str(exc)
    except OSError as exc:
        status, detail = "network_error", f"{type(exc).__name__}: {exc}"
    duration = round((time.monotonic() - started) * 1000, 1)
    marker(f"TCP/{port} complete status={status} duration_ms={duration}")
    return {
        "host": host,
        "port": port,
        "status": status,
        "detail": detail,
        "duration_ms": duration,
    }


def mdns_googlecast(timeout: float) -> dict[str, Any]:
    """Browse Google Cast only when zeroconf is already installed."""
    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    except ImportError:
        return {
            "status": "not_available",
            "instruction": "Install zeroconf, then run: python -m zeroconf _googlecast._tcp.local.",
        }

    found: list[dict[str, Any]] = []

    class Listener(ServiceListener):
        def add_service(self, zeroconf: Any, service_type: str, name: str) -> None:
            info = zeroconf.get_service_info(service_type, name, timeout=1000)
            if info:
                found.append(
                    {
                        "name": name,
                        "addresses": info.parsed_addresses(),
                        "port": info.port,
                    }
                )

        def update_service(self, zeroconf: Any, service_type: str, name: str) -> None:
            self.add_service(zeroconf, service_type, name)

        def remove_service(self, zeroconf: Any, service_type: str, name: str) -> None:
            return None

    zc = Zeroconf()
    try:
        browser = ServiceBrowser(zc, "_googlecast._tcp.local.", Listener())
        time.sleep(timeout)
        browser.cancel()
    finally:
        zc.close()
    return {"status": "completed", "services": found}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Exit codes: 0=complete, 1=partial/no VSSL reply, 2=arguments, 3=fatal artifact error.",
    )
    parser.add_argument(
        "--target", type=valid_target, help="Known MS.1 unicast IPv4 address"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New directory for capture artifacts",
    )
    parser.add_argument(
        "--udp-timeout",
        type=float,
        default=3.0,
        help="Seconds to collect replies per UDP request",
    )
    parser.add_argument(
        "--tcp-timeout",
        type=float,
        default=1.5,
        help="Seconds per connect-only TCP test",
    )
    parser.add_argument(
        "--mdns-timeout",
        type=float,
        default=3.0,
        help="Seconds to browse Google Cast when zeroconf exists",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def positive_timeout(value: float, label: str) -> None:
    if value <= 0 or value > 30:
        raise ValueError(f"{label} must be greater than 0 and no more than 30 seconds")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        positive_timeout(args.udp_timeout, "--udp-timeout")
        positive_timeout(args.tcp_timeout, "--tcp-timeout")
        positive_timeout(args.mdns_timeout, "--mdns-timeout")
    except ValueError as exc:
        parser.error(str(exc))

    try:
        output_dir = available_output_dir(args.output_dir.resolve())
        output_dir.mkdir(parents=True)
    except OSError as exc:
        print(f"Cannot create output directory: {exc}", file=sys.stderr)
        return 3

    started_at = utc_now()
    marker(f"VSSL probe {VERSION} session start output={output_dir}")
    all_records: list[dict[str, Any]] = []
    udp_errors: dict[str, str] = {}
    for port in DISCOVERY_PORTS:
        records, error = collect_udp(port, args.target, args.udp_timeout)
        all_records.extend(records)
        if error:
            udp_errors[str(port)] = error
    responses = deduplicate(all_records)
    discovered = sorted(
        {
            record["source_address"]
            for record in responses
            if record["parsed"]["is_vssl"]
        }
    )
    targets = sorted(set(discovered + ([args.target] if args.target else [])))

    tcp_results = [
        tcp_probe(host, port, args.tcp_timeout)
        for host in targets
        for port in TCP_PORTS
    ]
    marker("mDNS _googlecast._tcp.local. browse start")
    mdns_result = mdns_googlecast(args.mdns_timeout)
    marker(f"mDNS browse complete status={mdns_result['status']}")

    capture: dict[str, Any] = {
        "schema_version": 1,
        "sensitivity": "SENSITIVE_RAW_LOCAL_ONLY",
        "probe": {
            "version": VERSION,
            "started_at": started_at,
            "completed_at": utc_now(),
            "python": sys.version,
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
            "interfaces": local_interfaces(),
            "target": args.target,
        },
        "requests": [
            {
                "destination_address": args.target or SSDP_MULTICAST_HOST,
                "destination_port": port,
                "payload_base64": base64.b64encode(
                    build_discovery_request(port)
                ).decode("ascii"),
            }
            for port in DISCOVERY_PORTS
        ],
        "responses": responses,
        "tcp_connect_only": tcp_results,
        "googlecast_mdns": mdns_result,
        "errors": {"udp": udp_errors},
    }
    sanitized = sanitize_document(capture)
    summary = {
        "schema_version": 1,
        "started_at": started_at,
        "completed_at": capture["probe"]["completed_at"],
        "probe_version": VERSION,
        "unique_response_count": len(responses),
        "occurrence_count": sum(record["occurrence_count"] for record in responses),
        "vssl_response_count": sum(
            1 for record in responses if record["parsed"]["is_vssl"]
        ),
        "tested_target_count": len(targets),
        "tcp_status_counts": {
            status: sum(1 for item in tcp_results if item["status"] == status)
            for status in ("success", "refused", "timeout", "network_error")
        },
        "mdns_status": mdns_result["status"],
        "partial_errors": bool(udp_errors),
        "artifacts": [
            "capture.raw.SENSITIVE.json",
            "capture.sanitized.json",
            "summary.json",
        ],
    }
    try:
        (output_dir / "capture.raw.SENSITIVE.json").write_text(
            json.dumps(capture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (output_dir / "capture.sanitized.json").write_text(
            json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        print(f"Cannot write capture artifacts: {exc}", file=sys.stderr)
        return 3
    marker(f"session complete responses={len(responses)} targets={len(targets)}")
    return 0 if responses and not udp_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
