"""Tests for coordinator memory and diagnostic entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.vssl.api import DiscoveryResult, VsslConnectionError
from custom_components.vssl.binary_sensor import VsslReachableBinarySensor
from custom_components.vssl.coordinator import VsslDataUpdateCoordinator
from custom_components.vssl.entity import VsslRuntimeData
from custom_components.vssl.sensor import (
    VsslDiscoveryStatusSensor,
    VsslProtocolSupportSensor,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

PARSED = {
    "protocol": "ssdp",
    "is_vssl": True,
    "header_names": ["server", "x-model"],
    "identity": {"model": "MS.1"},
}


async def test_coordinator_retains_safe_failure_state(hass) -> None:
    client = AsyncMock()
    client.async_refresh.return_value = DiscoveryResult(
        responses=[PARSED], duration_ms=12.5, completed_at="2026-09-04T10:00:00+00:00"
    )
    coordinator = VsslDataUpdateCoordinator(hass, client, 60)
    await coordinator.async_refresh()
    assert coordinator.last_valid_response == PARSED
    assert coordinator.metrics["refresh_successes"] == 1

    client.async_refresh.side_effect = VsslConnectionError("no VSSL response")
    await coordinator.async_refresh()
    assert coordinator.last_valid_response == PARSED
    assert coordinator.last_failure["reason"] == "no VSSL response"
    assert coordinator.metrics["refresh_failures"] == 1


def test_entities_remain_visible_when_refresh_failed(hass) -> None:
    coordinator = VsslDataUpdateCoordinator(hass, AsyncMock(), 60)
    coordinator.last_update_success = False
    entry = MockConfigEntry(domain="vssl", unique_id="192.0.2.10", title="Lab MS.1")
    entry.runtime_data = VsslRuntimeData(coordinator)
    reachable = VsslReachableBinarySensor(entry)
    status = VsslDiscoveryStatusSensor(entry)
    support = VsslProtocolSupportSensor(entry)
    assert reachable.available is True and reachable.is_on is False
    assert status.available is True and status.native_value == "no_response"
    assert support.native_value == "unconfirmed_on_real_ms1"
