"""Refresh VSSL state and expose connection failures to Home Assistant."""

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VsslClient, VsslError


class VsslCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client: VsslClient, identity):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=entry,
            name="VSSL MX",
            update_interval=timedelta(seconds=5),
        )
        self.client = client
        self.identity = identity

    async def _async_update_data(self):
        try:
            return await self.client.state()
        except VsslError as err:
            raise UpdateFailed(str(err)) from err
