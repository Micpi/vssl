"""Real HA source-selector test with a simulated MS.1 HTTP device (no LAN)."""

import asyncio
from aiohttp import web
from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant


async def main():
    values = {
        "settings:/system/manufacturer": {"type": "string_", "string_": "VSSL, LLC"},
        "settings:/system/modelName": {"type": "string_", "string_": "MS1"},
        "settings:/deviceName": {"type": "string_", "string_": "VSSL test"},
        "settings:/version": {"type": "string_", "string_": "test"},
        "network:info": {
            "type": "networkInfo",
            "networkInfo": {"wired": {"mac": "02:00:00:00:00:01"}},
        },
        "player:volume": {"type": "i32_", "i32_": 30},
        "settings:/mediaPlayer/mute": {"type": "bool_", "bool_": False},
        "settings:/vssl/volumeIsFixed": {"type": "bool_", "bool_": False},
        "player:player/data": {"state": "stopped"},
    }
    rows = [
        [
            f"ui:/{path}aux_plug",
            title,
            "audio",
            {
                "resources": [{"uri": "alsa://aux_plug", "mimeType": "audio/unknown"}],
                "metaData": {
                    "playLogicPath": "pipewire:playLogic",
                    "serviceID": service,
                    "live": True,
                },
            },
        ]
        for path, title, service in [
            ("hdmi", "HDMI in", "HDMI"),
            ("spdifin", "SPDIF in", "SPDIFIN"),
            ("coaxin", "COAX in", "COAXIN"),
            ("aux", "Line in (AUX)", "AUX"),
            ("usbMem", "USB Memory", "Storage"),
        ]
    ]

    async def read(request):
        return web.json_response([values.get(request.query["path"])])

    async def catalog(request):
        return web.json_response({"rows": rows})

    async def write(request):
        payload = await request.json()
        command = payload["value"]
        assert payload["path"] == "player:player/control"
        if command["control"] == "stop":
            values["player:player/data"] = {"state": "stopped"}
        else:
            assert command["control"] == "play" and command["type"] == "none"
            values["player:player/data"] = {
                "state": "playing",
                "mediaRoles": command["mediaRoles"],
            }
        return web.json_response(None)

    app = web.Application()
    app.router.add_get("/api/getData", read)
    app.router.add_get("/api/getRows", catalog)
    app.router.add_post("/api/setData", write)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 80).start()
    hass = HomeAssistant("/config")
    loader.async_setup(hass)
    try:
        await bootstrap.async_from_config_dict(
            {
                "homeassistant": {"name": "Source test", "time_zone": "Europe/Paris"},
                "http": {},
            },
            hass,
        )
        result = await hass.config_entries.flow.async_init(
            "vssl", context={"source": "user"}, data={"host": "127.0.0.1"}
        )
        assert result["type"] == "create_entry", result
        await hass.async_block_till_done()
        entity = hass.states.async_all("media_player")[0]
        assert entity.attributes["source_list"] == [
            "Streaming",
            "HDMI",
            "Optique",
            "Coaxial",
            "AUX",
            "USB",
        ]
        for source in ["HDMI", "Optique", "Coaxial", "AUX", "USB", "Streaming"]:
            await hass.services.async_call(
                "media_player",
                "select_source",
                {"entity_id": entity.entity_id, "source": source},
                blocking=True,
            )
            assert hass.states.get(entity.entity_id).attributes["source"] == source
        assert await hass.config_entries.async_unload(result["result"].entry_id)
        print(
            "PASS: source_list and all six select_source services through real HA with simulated device",
            flush=True,
        )
    finally:
        await hass.async_stop()
        await runner.cleanup()


asyncio.run(main())
