"""Philips Air Purifier & Humidifier Selects."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_CATEGORY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import DOMAIN, OPTIONS, SELECT_TYPES, FanAttributes
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the select platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        available_selects = []
        unavailable_selects = []

        for cls in reversed(model_class.__mro__):
            cls_available_selects = getattr(cls, "AVAILABLE_SELECTS", [])
            available_selects.extend(cls_available_selects)
            cls_unavailable_selects = getattr(cls, "UNAVAILABLE_SELECTS", [])
            unavailable_selects.extend(cls_unavailable_selects)

        selects = [
            PhilipsSelect(hass, entry, config_entry_data, select)
            for select in SELECT_TYPES
            if select in available_selects and select not in unavailable_selects
        ]

        async_add_entities(selects, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsSelect(PhilipsEntity, SelectEntity):
    """Define a Philips AirPurifier select."""

    _attr_is_on: bool | None = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        select: str,
    ) -> None:
        """Initialize the select."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model

        self._description = SELECT_TYPES[select]
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        label = FanAttributes.LABEL
        label = label.partition("#")[0]
        self._attr_translation_key = self._description.get(FanAttributes.LABEL)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        self._options = self._description.get(OPTIONS)
        self._attr_options = list(self._options.values())

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{select.lower()}"

        self._attrs: dict[str, Any] = {}
        self.kind = select.partition("#")[0]

    @property
    def current_option(self) -> str:
        """Return the currently selected option."""
        option = self._device_status.get(self.kind)
        current_option = str(self._options.get(option))
        _LOGGER.debug("option: %s, returning as current_option: %s", option, current_option)
        return current_option

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option is None or len(option) == 0:
            _LOGGER.error("Cannot set empty option '%s'", option)
            return
        try:
            option_key = next(key for key, value in self._options.items() if value == option)
            _LOGGER.debug(
                "async_selection_option, kind: %s - option: %s - value: %s",
                self.kind,
                option,
                option_key,
            )
            await self.coordinator.client.set_control_value(self.kind, option_key)
            self._device_status[self.kind] = option_key
            self._handle_coordinator_update()

        except KeyError:
            _LOGGER.exception("Invalid option key: '%s'", option)
        except ValueError:
            _LOGGER.exception("Invalid value for option: '%s'", option)
