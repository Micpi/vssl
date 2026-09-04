"""Downloadable diagnostics for VSSL, including failed first refreshes."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import FIXTURE_STATUS, SUPPORT_STATUS
from .protocol import diagnostics_view


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without raw payloads or local identifiers."""
    runtime = getattr(entry, "runtime_data", None)
    coordinator = runtime.coordinator if runtime else None
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_HOST, "name"}),
        "options": dict(entry.options),
        "support": {
            "ms1": SUPPORT_STATUS,
            "fixtures": FIXTURE_STATUS,
            "warning": "Real-device validation is still required",
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success
            if coordinator
            else False,
            "metrics": dict(coordinator.metrics) if coordinator else {},
            "last_failure": coordinator.last_failure if coordinator else None,
            "last_valid_response": diagnostics_view(coordinator.last_valid_response)
            if coordinator
            else {},
        },
    }
