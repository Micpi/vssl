"""Coordinator and in-memory field diagnostics for VSSL."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DiscoveryResult, VsslConnectionError, VsslDiscoveryClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VsslDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh discovery data while retaining bounded in-memory diagnostics."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: VsslDiscoveryClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.last_valid_response: dict[str, Any] | None = None
        self.last_failure: dict[str, Any] | None = None
        self.metrics: dict[str, int | float] = {
            "refresh_attempts": 0,
            "refresh_successes": 0,
            "refresh_failures": 0,
            "responses_accepted": 0,
            "responses_rejected": 0,
            "last_duration_ms": 0.0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        self.metrics["refresh_attempts"] += 1
        started = time.monotonic()
        try:
            result: DiscoveryResult = await self.client.async_refresh()
        except VsslConnectionError as exc:
            duration = round((time.monotonic() - started) * 1000, 1)
            self.metrics["refresh_failures"] += 1
            self.metrics["last_duration_ms"] = duration
            self.last_failure = {
                "at": datetime.now(UTC).isoformat(),
                "type": type(exc).__name__,
                "reason": str(exc),
                "duration_ms": duration,
            }
            _LOGGER.debug(
                "VSSL refresh step=complete duration_ms=%.1f responses=0 rejection=%s",
                duration,
                str(exc),
            )
            raise UpdateFailed(str(exc)) from exc

        self.metrics["refresh_successes"] += 1
        self.metrics["responses_accepted"] += len(result.responses)
        self.metrics["responses_rejected"] += result.rejected
        self.metrics["last_duration_ms"] = result.duration_ms
        self.last_valid_response = result.primary
        self.last_failure = None
        _LOGGER.debug(
            "VSSL refresh step=complete duration_ms=%.1f responses=%d rejection_count=%d",
            result.duration_ms,
            len(result.responses),
            result.rejected,
        )
        return result.primary or {}
