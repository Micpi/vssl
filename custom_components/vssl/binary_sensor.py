"""Binary sensors for VSSL discovery health."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import VsslEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up reachability sensor."""
    async_add_entities([VsslReachableBinarySensor(entry)])


class VsslReachableBinarySensor(VsslEntity, BinarySensorEntity):
    """Report whether the last UDP refresh found a VSSL response."""

    _attr_name = "Discovery reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = (
            f"{entry.unique_id or entry.entry_id}_discovery_reachable"
        )

    @property
    def is_on(self) -> bool:
        """Return the coordinator health."""
        return self.coordinator.last_update_success

    @property
    def available(self) -> bool:
        """The diagnostic entity itself remains available on refresh failure."""
        return True
