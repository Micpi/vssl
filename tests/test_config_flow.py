"""Tests for VSSL configuration flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from custom_components.vssl.api import VsslConnectionError
from custom_components.vssl.const import CONF_SCAN_INTERVAL, DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_entry_created_for_offline_field_diagnostics(hass) -> None:
    with patch(
        "custom_components.vssl.config_flow.VsslDiscoveryClient.async_refresh",
        side_effect=VsslConnectionError("no VSSL response"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_HOST: "192.0.2.10",
                CONF_NAME: "Lab MS.1",
                CONF_SCAN_INTERVAL: 60,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["setup_probe_verified"] is False
    assert result["data"][CONF_HOST] == "192.0.2.10"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_host_stays_on_form(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "not-an-ip", CONF_NAME: "Lab MS.1", CONF_SCAN_INTERVAL: 60},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}
