"""Home Assistant integration for VSSL MX."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VsslClient, VsslError
from .coordinator import VsslCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass, entry):
    client = VsslClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    try:
        identity = await client.identity()
        if entry.data.get("legacy_identity"):
            hass.config_entries.async_update_entry(
                entry,
                unique_id=identity["id"],
                title=identity["name"],
                data={CONF_HOST: entry.data[CONF_HOST]},
            )
        elif identity["id"] != entry.unique_id:
            raise VsslError("The IP address now belongs to a different VSSL")
    except VsslError as err:
        raise ConfigEntryNotReady(str(err)) from err
    coordinator = VsslCoordinator(hass, entry, client, identity)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass, entry):
    """Preserve the host configured by the experimental 0.1 integration."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            data={CONF_HOST: entry.data[CONF_HOST], "legacy_identity": True},
        )
    return True
