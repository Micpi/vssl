"""UI configuration and AirPlay discovery for VSSL MX."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UnsupportedDevice, VsslClient, VsslError, validate_host
from .const import DOMAIN


class VsslConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                host = validate_host(user_input[CONF_HOST])
                client = VsslClient(async_get_clientsession(self.hass), host)
                identity = await client.identity()
                await client.state()
            except ValueError:
                errors["base"] = "invalid_host"
            except UnsupportedDevice:
                errors["base"] = "unsupported_device"
            except VsslError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(identity["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=identity["name"], data={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        host = discovery_info.host
        try:
            client = VsslClient(async_get_clientsession(self.hass), host)
            identity = await client.identity()
        except (VsslError, ValueError):
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(identity["id"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._discovered_host = host
        self._discovered_name = identity["name"]
        self.context["title_placeholders"] = {"name": identity["name"]}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            return await self.async_step_user({CONF_HOST: self._discovered_host})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._discovered_name,
                "host": self._discovered_host,
            },
        )
