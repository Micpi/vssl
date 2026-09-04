"""Config flow for VSSL MS.1 discovery diagnostics."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .api import VsslConnectionError, VsslDiscoveryClient
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def normalize_host(value: str) -> str:
    """Validate an IPv4 literal without performing DNS or external I/O."""
    address = ipaddress.ip_address(value.strip())
    if address.version != 4 or address.is_unspecified or address.is_multicast:
        raise ValueError("A unicast IPv4 address is required")
    return str(address)


class VsslConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle VSSL setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a known MS.1 address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                client = VsslDiscoveryClient(host)
                verified = True
                try:
                    await client.async_refresh()
                except VsslConnectionError as exc:
                    verified = False
                    _LOGGER.debug(
                        "VSSL setup probe did not confirm device; entry remains available "
                        "for field diagnostics (%s)",
                        exc,
                    )
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                data = dict(user_input)
                data[CONF_HOST] = host
                data["setup_probe_verified"] = verified
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME), data=data
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return VsslOptionsFlow(config_entry)


class VsslOptionsFlow(OptionsFlow):
    """Allow polling interval changes."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage VSSL options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
