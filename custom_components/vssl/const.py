"""Constants for the VSSL integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "vssl"
MANUFACTURER = "VSSL"
DEFAULT_NAME = "VSSL MS.1"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600
DEFAULT_TIMEOUT = 3.0

CONF_SCAN_INTERVAL = "scan_interval"

PLATFORMS = ["binary_sensor", "sensor"]
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SUPPORT_STATUS = "unconfirmed_on_real_ms1"
FIXTURE_STATUS = "synthetic_only"
