"""VSSL MX player with native volume, mute and now-playing metadata."""

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerDeviceClass,
    MediaPlayerState,
    MediaType,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import VsslError
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VsslMediaPlayer(entry.runtime_data)])


class VsslMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    _attr_volume_step = 0.01

    def __init__(self, coordinator):
        super().__init__(coordinator)
        info = coordinator.identity
        self._attr_unique_id = info["id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info["id"])},
            name=info["name"],
            manufacturer="VSSL",
            model=info["model"],
            sw_version=info["version"],
            configuration_url=coordinator.client.base_url,
        )

    @property
    def player(self):
        return self.coordinator.data["player"]

    @property
    def supported_features(self):
        features = MediaPlayerEntityFeature.VOLUME_MUTE
        if not self.coordinator.data["fixed"]:
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.player.get("controls", {}).get("pause") and self.player.get(
            "state"
        ) in {"playing", "paused"}:
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        return features

    @property
    def state(self):
        return {
            "playing": MediaPlayerState.PLAYING,
            "paused": MediaPlayerState.PAUSED,
            "buffering": MediaPlayerState.BUFFERING,
        }.get(self.player.get("state"), MediaPlayerState.IDLE)

    @property
    def volume_level(self):
        return self.coordinator.data["volume"] / 100

    @property
    def is_volume_muted(self):
        return self.coordinator.data["muted"]

    @property
    def media_title(self):
        return self.player.get("trackRoles", {}).get("title")

    @property
    def metadata(self):
        return (
            self.player.get("trackRoles", {}).get("mediaData", {}).get("metaData", {})
        )

    @property
    def media_artist(self):
        return self.metadata.get("artist")

    @property
    def media_album_name(self):
        return self.metadata.get("album")

    @property
    def media_image_url(self):
        url = self.player.get("trackRoles", {}).get("icon", "")
        return url if url.startswith(("http://", "https://")) else None

    @property
    def source(self):
        return self.metadata.get("serviceName") or self.player.get(
            "mediaRoles", {}
        ).get("description")

    async def _command(self, action):
        try:
            await action
        except VsslError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_refresh()

    async def async_set_volume_level(self, volume):
        await self._command(self.coordinator.client.volume(round(volume * 100)))

    async def async_volume_up(self):
        await self.coordinator.async_refresh()
        await self.async_set_volume_level(min(1, self.volume_level + self.volume_step))

    async def async_volume_down(self):
        await self.coordinator.async_refresh()
        await self.async_set_volume_level(max(0, self.volume_level - self.volume_step))

    async def async_mute_volume(self, mute):
        await self._command(self.coordinator.client.mute(mute))

    async def async_media_play(self):
        await self._command(self.coordinator.client.playback(True))

    async def async_media_pause(self):
        await self._command(self.coordinator.client.playback(False))
