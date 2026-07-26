"""Helper functions for Philips air purifier status."""

from homeassistant.helpers.device_registry import format_mac

from .const import PhilipsApi


INVALID_MAC_ADDRESSES = {
    "00:00:00:00:00:00",
    "ff:ff:ff:ff:ff:ff",
}


def extract_name(status: dict) -> str:
    """Extract the name from the status."""
    for name_key in [PhilipsApi.NAME, PhilipsApi.NEW_NAME, PhilipsApi.NEW2_NAME]:
        name = status.get(name_key)
        if name:
            return name
    return ""


def extract_model(status: dict) -> str:
    """Extract the model from the status."""
    for model_key in [
        PhilipsApi.MODEL_ID,
        PhilipsApi.NEW_MODEL_ID,
        PhilipsApi.NEW2_MODEL_ID,
    ]:
        model = status.get(model_key)
        if model:
            return model[:9]
    return ""


def normalize_connection_mac(mac_address: str | None) -> str | None:
    """Normalize and validate a MAC address for device registry connections."""
    if not mac_address:
        return None

    formatted_mac = format_mac(mac_address)
    if formatted_mac in INVALID_MAC_ADDRESSES:
        return None

    return formatted_mac
