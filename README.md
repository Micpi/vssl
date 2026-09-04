# VSSL MS.1 (Experimental)

Custom Home Assistant integration and field-debug kit for the VSSL MS.1. Version
0.1 is intentionally non-destructive: it discovers the device over the documented
UDP ports and exposes reachability/support sensors plus downloadable diagnostics.
It does not send playback, volume, rename, reset, update or proprietary query frames.

Real MS.1 compatibility is not yet confirmed. Current tests use a synthetic fixture;
follow [DEBUG_SESSION.md](DEBUG_SESSION.md) to convert one real-network session into
sanitized reproducible tests.

## Installation

Copy `custom_components/vssl` to Home Assistant's `custom_components/`, restart,
then add **VSSL MS.1 (Experimental)** from Settings > Devices & services. HACS users
can add this repository as a custom Integration repository.

The setup accepts a known IPv4 address even when the initial probe fails. This is
deliberate so the diagnostic entry and its in-memory counters remain available in
the field. Use the standard `homeassistant.update_entity` action on the Discovery
status sensor for an immediate refresh.

## Development

```bash
python3 tools/validate_fixture.py tests/fixtures/synthetic_capture.json
python3 -m pytest
```

Protocol facts used here: VSSL documents multicast zone discovery on UDP 1800/1900
and application communication on TCP 7777/50002. The exact MS.1 response shape is
still an evidence gap, so unknown headers are retained by the parser and surfaced by
the fixture validator rather than assigned guessed semantics.

Primary references:

- [VSSL Networking Support](https://vsslknowledgebase.tawk.help/article/vssl-networking-support)
- [Official MS.1 product page](https://www.vssl.com/vssl-products/ms1)
- [Official MS.1 quick-start guide](https://www.vssl.com/qsg/ms-1-quick-start-guide)
