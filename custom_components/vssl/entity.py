"""Shared VSSL entity helpers."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VsslDataUpdateCoordinator


@dataclass(slots=True)
class VsslRuntimeData:
    """Runtime data attached to the config entry before the first refresh."""

    coordinator: VsslDataUpdateCoordinator


class VsslEntity(CoordinatorEntity[VsslDataUpdateCoordinator]):
    """Base entity for the diagnostic-first MS.1 integration."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return the VSSL device registry information."""
        identity = (self.coordinator.data or {}).get("identity", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.unique_id or self.entry.entry_id)},
            name=self.entry.title,
            manufacturer=MANUFACTURER,
            model=identity.get("model") or "MS.1 (unconfirmed)",
        )
