"""Local StreamSDK API used by VSSL MS.1 and MA.1."""

from __future__ import annotations

import asyncio
import ipaddress
import re
from typing import Any

import aiohttp


class VsslError(Exception):
    """Device communication or protocol error."""


class UnsupportedDevice(VsslError):
    """Host is not a supported VSSL MX device."""


def validate_host(host: str) -> str:
    """Accept an IP address or DNS hostname, never a URL or path."""
    host = host.strip()
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        if len(host) > 253 or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host
        ):
            raise ValueError("Invalid host") from None
        return host.lower()


class VsslClient:
    """Async client. The caller owns the HTTP session."""

    def __init__(self, session: aiohttp.ClientSession, host: str):
        self.session = session
        self.host = validate_host(host)
        address = f"[{self.host}]" if ":" in self.host else self.host
        self.base_url = f"http://{address}"
        self.command_lock = asyncio.Lock()

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        try:
            async with self.session.request(
                method,
                f"{self.base_url}/api/{endpoint}",
                timeout=aiohttp.ClientTimeout(total=8),
                **kwargs,
            ) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise VsslError(f"VSSL request failed: {endpoint}") from err
        if isinstance(data, dict) and data.get("error"):
            raise VsslError(f"VSSL rejected request: {endpoint}")
        return data

    async def get(self, path: str) -> Any:
        data = await self._request(
            "GET", "getData", params={"path": path, "roles": "value"}
        )
        if not isinstance(data, list) or len(data) != 1 or data[0] is None:
            raise VsslError(f"Missing value: {path}")
        value = data[0]
        if isinstance(value, dict) and "type" in value:
            if value["type"] not in value:
                raise VsslError(f"Malformed typed value: {path}")
            return value[value["type"]]
        return value

    async def set(self, path: str, value: Any, role: str = "value") -> None:
        result = await self._request(
            "POST", "setData", json={"path": path, "role": role, "value": value}
        )
        if result is False:
            raise VsslError(f"VSSL rejected write: {path}")

    async def identity(self) -> dict[str, str]:
        manufacturer = await self.get("settings:/system/manufacturer")
        model = await self.get("settings:/system/modelName")
        if (
            not isinstance(manufacturer, str)
            or not manufacturer.startswith("VSSL")
            or model not in {"MS1", "MA1"}
        ):
            raise UnsupportedDevice(
                "Only VSSL MS.1 / MA.1 StreamSDK devices are supported"
            )
        name = await self.get("settings:/deviceName")
        version = await self.get("settings:/version")
        network = await self.get("network:info")
        if not isinstance(network, dict):
            raise VsslError("Missing network identity")
        mac = network.get("wired", {}).get("mac") or network.get("wireless", {}).get(
            "mac"
        )
        if not isinstance(mac, str) or not re.fullmatch(
            r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac
        ):
            raise VsslError("Missing stable hardware address")
        return {
            "id": mac.replace(":", "").lower(),
            "name": str(name),
            "model": model,
            "version": str(version),
        }

    async def state(self) -> dict[str, Any]:
        # Serial requests keep the embedded HTTP server load low.
        volume = await self.get("player:volume")
        muted = await self.get("settings:/mediaPlayer/mute")
        player = await self.get("player:player/data")
        fixed = await self.get("settings:/vssl/volumeIsFixed")
        if (
            type(volume) is not int
            or not 0 <= volume <= 100
            or type(muted) is not bool
            or not isinstance(player, dict)
            or type(fixed) is not bool
        ):
            raise VsslError("Invalid player state")
        return {"volume": volume, "muted": muted, "player": player, "fixed": fixed}

    async def volume(self, value: int) -> None:
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError("Volume must be an integer from 0 to 100")
        async with self.command_lock:
            if await self.get("settings:/vssl/volumeIsFixed"):
                raise VsslError("Volume is fixed in the VSSL application")
            await self.set("player:volume", {"type": "i32_", "i32_": value})

    async def mute(self, value: bool) -> None:
        if type(value) is not bool:
            raise ValueError("Mute must be boolean")
        async with self.command_lock:
            await self.set(
                "settings:/mediaPlayer/mute", {"type": "bool_", "bool_": value}
            )

    async def playback(self, playing: bool) -> None:
        """StreamSDK pause is a toggle; never send the invalid 'play' command."""
        async with self.command_lock:
            player = await self.get("player:player/data")
            current = player.get("state")
            target = "playing" if playing else "paused"
            if current == target:
                return
            if current not in {"playing", "paused"}:
                raise VsslError(
                    "Start a stream from Music Assistant, Cast, AirPlay or the VSSL app first"
                )
            if not player.get("controls", {}).get("pause"):
                raise VsslError("The current source does not support pause/resume")
            await self.set("player:player/control", {"control": "pause"}, "activate")
