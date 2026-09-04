"""Network-shape and logging invariance tests."""

from __future__ import annotations

import logging
from unittest.mock import Mock

from custom_components.vssl.api import VsslDiscoveryClient

PAYLOAD = b"HTTP/1.1 200 OK\r\nSERVER: VSSL/MS.1\r\nX-Model: MS.1\r\n\r\n"


def run_with_level(level: int) -> tuple[list[int], int]:
    client = VsslDiscoveryClient("192.0.2.10", timeout=0.01)
    query = Mock(return_value=[(PAYLOAD, 1900)])
    client._query_port = query  # type: ignore[method-assign]
    logging.getLogger("custom_components.vssl.api").setLevel(level)
    result = client._refresh_sync()  # pylint: disable=protected-access
    return [call.args[0] for call in query.call_args_list], len(result.responses)


def test_debug_level_does_not_change_network_behavior() -> None:
    assert (
        run_with_level(logging.INFO)
        == run_with_level(logging.DEBUG)
        == ([1800, 1900], 2)
    )
