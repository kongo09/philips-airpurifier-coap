"""Tests for the diagnostics."""

from custom_components.philips_airpurifier_coap.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_diagnostics_redacts_sensitive_data(hass: HomeAssistant, make_runtime) -> None:
    """Diagnostics expose device info while redacting host and identifiers."""
    entry, _ = make_runtime("AC3033")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["title"] == "AC3033 Living Room"
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["device_info"]["model"] == "AC3033"
    assert diagnostics["device_info"]["host"] == "**REDACTED**"
    assert "status" in diagnostics["coordinator"]
