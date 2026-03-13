"""Philips Air Purifier & Humidifier."""

from __future__ import annotations

import logging
from collections.abc import Callable

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
    """Set up the fan platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        fan_entity = model_class(hass, entry, config_entry_data)
    else:
        _LOGGER.error("Unsupported model: %s", model)
        return

    # some humidifiers don't need a fan entity
    if fan_entity.CREATE_FAN:
        async_add_entities([fan_entity])
