"""Exercise the real Home Assistant loader, config flow and entity lifecycle."""

import asyncio
import sys

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant


async def main():
    hass = HomeAssistant("/config")
    loader.async_setup(hass)
    await bootstrap.async_from_config_dict(
        {
            "homeassistant": {
                "name": "VSSL integration test",
                "time_zone": "Europe/Paris",
            },
            "http": {},
        },
        hass,
    )
    try:
        result = await hass.config_entries.flow.async_init(
            "vssl", context={"source": "user"}, data={"host": sys.argv[1]}
        )
        print("FLOW", result["type"], flush=True)
        assert result["type"] == "create_entry", result
        entry = result["result"]
        await hass.async_block_till_done()
        states = hass.states.async_all("media_player")
        print("ENTRIES", entry.state, flush=True)
        print(
            "ENTITIES",
            [(s.entity_id, s.state, s.attributes.get("volume_level")) for s in states],
            flush=True,
        )
        assert len(states) == 1
        assert states[0].state not in ("unavailable", "unknown")
        assert states[0].attributes["volume_level"] >= 0
        if "--write" in sys.argv:
            entity_id = states[0].entity_id
            original = states[0].attributes["volume_level"]
            original_mute = states[0].attributes["is_volume_muted"]
            try:
                target = max(0, round(original - 0.01, 2))
                await hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"entity_id": entity_id, "volume_level": target},
                    blocking=True,
                )
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).attributes["volume_level"] == target
                await hass.services.async_call(
                    "media_player",
                    "volume_mute",
                    {"entity_id": entity_id, "is_volume_muted": True},
                    blocking=True,
                )
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).attributes["is_volume_muted"] is True
            finally:
                await hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"entity_id": entity_id, "volume_level": original},
                    blocking=True,
                )
                await hass.services.async_call(
                    "media_player",
                    "volume_mute",
                    {"entity_id": entity_id, "is_volume_muted": original_mute},
                    blocking=True,
                )
            assert hass.states.get(entity_id).attributes["volume_level"] == original
            assert (
                hass.states.get(entity_id).attributes["is_volume_muted"]
                == original_mute
            )
            print(
                "PASS: HA volume and mute services, original settings restored",
                flush=True,
            )
        duplicate = await hass.config_entries.flow.async_init(
            "vssl", context={"source": "user"}, data={"host": sys.argv[1]}
        )
        assert (
            duplicate["type"] == "abort" and duplicate["reason"] == "already_configured"
        ), duplicate
        coordinator = entry.runtime_data
        original_url = coordinator.client.base_url
        try:
            coordinator.client.base_url = "http://127.0.0.1:1"
            await coordinator.async_refresh()
            assert hass.states.get(states[0].entity_id).state == "unavailable"
        finally:
            coordinator.client.base_url = original_url
            await coordinator.async_refresh()
        assert hass.states.get(states[0].entity_id).state != "unavailable"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        # Recreate the experimental entry's IP-based identity and version.
        hass.config_entries.async_update_entry(
            entry,
            version=1,
            unique_id=sys.argv[1],
            data={"host": sys.argv[1], "setup_probe_verified": False},
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.version == 2 and entry.unique_id != sys.argv[1]
        assert "legacy_identity" not in entry.data
        assert hass.states.get(states[0].entity_id).state != "unavailable"
        print(
            "PASS: real HA setup, live entity, duplicates, outage/recovery, unload and v0.1 migration",
            flush=True,
        )
    finally:
        await hass.async_stop()


asyncio.run(main())
