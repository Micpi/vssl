"""Protocol regression tests against an actual local HTTP test server."""

import asyncio
import importlib.util
from pathlib import Path
import unittest

from aiohttp import ClientSession, web

spec = importlib.util.spec_from_file_location(
    "vssl_api", Path(__file__).parents[1] / "custom_components/vssl/api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.values = {
            "player:volume": {"type": "i32_", "i32_": 41},
            "settings:/mediaPlayer/mute": {"type": "bool_", "bool_": False},
            "settings:/vssl/volumeIsFixed": {"type": "bool_", "bool_": False},
            "player:player/data": {"state": "playing", "controls": {"pause": True}},
        }
        self.writes = []
        self.rows = [
            [
                "ui:/hdmiaux_plug",
                "HDMI in",
                "audio",
                {
                    "resources": [
                        {"uri": "alsa://aux_plug", "mimeType": "audio/unknown"}
                    ],
                    "metaData": {
                        "playLogicPath": "pipewire:playLogic",
                        "serviceID": "HDMI",
                        "live": True,
                    },
                },
            ],
            ["ui:/googlecastlite", "Google Cast", "container", None],
        ]
        self.status = 200
        self.malformed = False
        self.application_error = False
        app = web.Application()
        app.router.add_get("/api/getData", self.read)
        app.router.add_post("/api/setData", self.write)
        app.router.add_get("/api/getRows", self.read_rows)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.session = ClientSession()
        self.client = api.VsslClient(self.session, "127.0.0.1")
        self.client.base_url = (
            f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def read(self, request):
        if self.malformed:
            return web.Response(text="not JSON")
        if self.application_error:
            return web.json_response({"error": {"name": "invalidPath"}})
        return web.json_response(
            [self.values.get(request.query["path"])], status=self.status
        )

    async def write(self, request):
        data = await request.json()
        self.writes.append(data)
        if data["role"] == "activate":
            if data["value"].get("control") == "play":
                self.values["player:player/data"] = {
                    "state": "playing",
                    "mediaRoles": data["value"]["mediaRoles"],
                }
                return web.json_response(None)
            if data["value"].get("control") == "stop":
                self.values["player:player/data"] = {"state": "stopped"}
                return web.json_response(None)
            current = self.values["player:player/data"]["state"]
            self.values["player:player/data"]["state"] = (
                "paused" if current == "playing" else "playing"
            )
        else:
            self.values[data["path"]] = data["value"]
        return web.json_response(None)

    async def read_rows(self, request):
        return web.json_response({"rows": self.rows})

    async def test_source_discovery_filters_nonplayable_services(self):
        self.assertEqual(list(await self.client.sources()), ["HDMI"])

    async def test_hdmi_uses_device_supplied_media_roles(self):
        await self.client.select_source("HDMI")
        self.assertEqual(api.source_name((await self.client.state())["player"]), "HDMI")
        payload = self.writes[-1]["value"]
        self.assertEqual(payload["mediaRoles"]["mediaData"], self.rows[0][3])
        self.assertEqual(payload["type"], "none")
        await self.client.select_source("HDMI")
        self.assertEqual(len(self.writes), 1)

    async def test_streaming_releases_local_input(self):
        await self.client.select_source("HDMI")
        await self.client.select_source("Streaming")
        self.assertEqual(self.writes[-1]["value"], {"control": "stop"})
        self.assertEqual(
            api.source_name((await self.client.state())["player"]), "Streaming"
        )

    async def test_streaming_does_not_interrupt_cast(self):
        self.values["player:player/data"]["mediaRoles"] = {
            "mediaData": {"metaData": {"serviceID": "googlecast"}}
        }
        await self.client.select_source("Streaming")
        self.assertFalse(self.writes)

    async def test_unknown_or_disabled_source_never_written(self):
        for source in ["Optique", "ui:/hdmiaux_plug", "Google Cast"]:
            with self.assertRaises(api.VsslError):
                await self.client.select_source(source)
        self.assertFalse(self.writes)

    async def test_malformed_source_rows_ignored(self):
        self.rows = [
            None,
            [],
            ["bad", "bad", "audio", None],
            ["bad", "bad", "audio", {}],
        ]
        self.assertEqual(await self.client.sources(), {})

    def test_source_uses_media_not_stale_track_metadata(self):
        player = {
            "mediaRoles": {"mediaData": {"metaData": {"serviceID": "HDMI"}}},
            "trackRoles": {"mediaData": {"metaData": {"serviceID": "googlecast"}}},
        }
        self.assertEqual(api.source_name(player), "HDMI")

    async def test_state_and_volume_roundtrip(self):
        self.assertEqual((await self.client.state())["volume"], 41)
        await self.client.volume(40)
        await self.client.mute(True)
        state = await self.client.state()
        self.assertEqual(state["volume"], 40)
        self.assertTrue(state["muted"])

    async def test_pause_resume_are_idempotent_and_serialized(self):
        await asyncio.gather(self.client.playback(False), self.client.playback(False))
        self.assertEqual(len(self.writes), 1)
        await self.client.playback(True)
        await self.client.playback(True)
        self.assertEqual(len(self.writes), 2)
        self.assertTrue(all(w["value"] == {"control": "pause"} for w in self.writes))

    async def test_idle_does_not_start_unknown_media(self):
        self.values["player:player/data"]["state"] = "stopped"
        with self.assertRaises(api.VsslError):
            await self.client.playback(True)
        self.assertFalse(self.writes)

    async def test_fixed_volume_is_respected(self):
        self.values["settings:/vssl/volumeIsFixed"]["bool_"] = True
        with self.assertRaises(api.VsslError):
            await self.client.volume(25)
        self.assertFalse(self.writes)

    async def test_http_and_protocol_errors(self):
        self.status = 503
        with self.assertRaises(api.VsslError):
            await self.client.state()
        self.status = 200
        self.malformed = True
        with self.assertRaises(api.VsslError):
            await self.client.state()
        self.malformed = False
        self.application_error = True
        with self.assertRaises(api.VsslError):
            await self.client.state()

    async def test_invalid_state_does_not_become_zero_volume(self):
        self.values["player:volume"] = {"type": "i32_", "i32_": "invalid"}
        with self.assertRaises(api.VsslError):
            await self.client.state()

    async def test_unsupported_device(self):
        self.values["settings:/system/manufacturer"] = {
            "type": "string_",
            "string_": "Other",
        }
        self.values["settings:/system/modelName"] = {
            "type": "string_",
            "string_": "MS1",
        }
        with self.assertRaises(api.UnsupportedDevice):
            await self.client.identity()

    async def test_missing_value(self):
        with self.assertRaises(api.VsslError):
            await self.client.get("missing:")

    async def test_bad_volume_never_written(self):
        for value in (-1, 101, True, float("nan")):
            with self.assertRaises(ValueError):
                await self.client.volume(value)
        self.assertFalse(self.writes)

    def test_host_validation(self):
        for host in ("http://example.com", "host/path", "user@host", ""):
            with self.assertRaises(ValueError):
                api.validate_host(host)
        self.assertEqual(api.validate_host("192.168.1.26"), "192.168.1.26")
        self.assertEqual(api.validate_host("VSSL.local"), "vssl.local")


if __name__ == "__main__":
    unittest.main()
