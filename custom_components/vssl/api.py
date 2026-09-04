"""Non-destructive UDP discovery client for VSSL devices."""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .const import DEFAULT_TIMEOUT
from .protocol import DISCOVERY_PORTS, build_discovery_request, parse_datagram

_LOGGER = logging.getLogger(__name__)


class VsslError(Exception):
    """Base VSSL error."""


class VsslConnectionError(VsslError):
    """Raised when no usable discovery response is returned."""


@dataclass(slots=True)
class DiscoveryResult:
    """Result of one complete two-port refresh."""

    responses: list[dict[str, Any]] = field(default_factory=list)
    rejected: int = 0
    duration_ms: float = 0.0
    completed_at: str = ""

    @property
    def primary(self) -> dict[str, Any] | None:
        return self.responses[0] if self.responses else None


class VsslDiscoveryClient:
    """Query the two documented VSSL discovery UDP ports."""

    def __init__(self, host: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.host = host
        self.timeout = timeout

    async def async_refresh(self) -> DiscoveryResult:
        """Run the blocking UDP socket work away from the HA event loop."""
        return await asyncio.to_thread(self._refresh_sync)

    def _refresh_sync(self) -> DiscoveryResult:
        started = time.monotonic()
        accepted: list[dict[str, Any]] = []
        rejected = 0
        errors: list[str] = []
        for port in DISCOVERY_PORTS:
            port_started = time.monotonic()
            _LOGGER.debug("VSSL discovery step=send destination_port=%d", port)
            try:
                payloads = self._query_port(port)
            except OSError as exc:
                errors.append(f"udp/{port}: {type(exc).__name__}")
                _LOGGER.debug(
                    "VSSL discovery step=receive destination_port=%d duration_ms=%.1f "
                    "responses=0 rejection=network_error",
                    port,
                    (time.monotonic() - port_started) * 1000,
                )
                continue
            for payload, source_port in payloads:
                parsed = parse_datagram(payload)
                parsed["destination_port"] = port
                parsed["source_port"] = source_port
                if parsed["is_vssl"]:
                    accepted.append(parsed)
                else:
                    rejected += 1
            _LOGGER.debug(
                "VSSL discovery step=receive destination_port=%d duration_ms=%.1f "
                "responses=%d rejection=%s",
                port,
                (time.monotonic() - port_started) * 1000,
                len(payloads),
                "not_vssl" if payloads and not accepted else "none",
            )
        result = DiscoveryResult(
            responses=accepted,
            rejected=rejected,
            duration_ms=round((time.monotonic() - started) * 1000, 1),
            completed_at=datetime.now(UTC).isoformat(),
        )
        if not accepted:
            reason = ", ".join(errors) if errors else "no VSSL response"
            raise VsslConnectionError(reason)
        return result

    def _query_port(self, port: int) -> list[tuple[bytes, int]]:
        """Send one discovery request and collect replies until timeout."""
        replies: list[tuple[bytes, int]] = []
        request = build_discovery_request(port)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.bind(("", 0))
            sock.sendto(request, (self.host, port))
            deadline = time.monotonic() + self.timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    payload, address = sock.recvfrom(65535)
                except TimeoutError:
                    break
                if address[0] == self.host:
                    replies.append((payload, address[1]))
        return replies
