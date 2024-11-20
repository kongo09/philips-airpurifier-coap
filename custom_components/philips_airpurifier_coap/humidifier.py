from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import DOMAIN
from .philips import model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
):
    """Set up the humidifier platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    # Map model to humidifier class
    model_class = model_to_class.get(model)
    if model_class:
        humidifier_entity = model_class(hass, entry, config_entry_data)
    else:
        _LOGGER.error("Unsupported humidifier model: %s", model)
        return

    async_add_entities([humidifier_entity])
