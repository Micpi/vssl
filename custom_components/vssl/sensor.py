"""Diagnostic sensors for VSSL."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FIXTURE_STATUS, SUPPORT_STATUS
from .entity import VsslEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up field-readiness sensors."""
    async_add_entities(
        [
            VsslDiscoveryStatusSensor(entry),
            VsslProtocolSupportSensor(entry),
        ]
    )


class VsslDiscoveryStatusSensor(VsslEntity, SensorEntity):
    """Expose the latest refresh status and safe counters."""

    _attr_name = "Discovery status"
    _attr_icon = "mdi:radar"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_discovery_status"

    @property
    def native_value(self) -> str:
        """Return a readable status."""
        return "responding" if self.coordinator.last_update_success else "no_response"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive field counters."""
        return dict(self.coordinator.metrics)

    @property
    def available(self) -> bool:
        """Stay visible when the device is unavailable."""
        return True


class VsslProtocolSupportSensor(VsslEntity, SensorEntity):
    """Make the experimental status impossible to overlook in the UI."""

    _attr_name = "Protocol support"
    _attr_icon = "mdi:test-tube"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_protocol_support"

    @property
    def native_value(self) -> str:
        """Return the support status."""
        return SUPPORT_STATUS

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose fixture provenance."""
        return {
            "fixture_status": FIXTURE_STATUS,
            "next_step": "validate_with_real_ms1_capture",
        }

    @property
    def available(self) -> bool:
        """This information is independent of device availability."""
        return True
