"""Test configuration for the VSSL custom integration."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_ROOT))

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def _allow_windows_event_loop_socket(socket_enabled):
    """Allow the Windows asyncio self-pipe; VSSL I/O is mocked in tests."""
    yield


@pytest.fixture
def event_loop_policy(socket_enabled):
    """Ensure pytest-socket is restored before pytest-asyncio builds its loop."""
    return asyncio.get_event_loop_policy()
