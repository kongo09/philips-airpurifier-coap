"""Philips Air Purifier & Humidifier Buttons."""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import DOMAIN, FILTER_TYPES, FanAttributes
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up platform for button."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model
    status = config_entry_data.latest_status

    model_class = model_to_class.get(model)
    if model_class:
        available_filter_resets = []

        for cls in reversed(model_class.__mro__):
            cls_available_filter_resets = getattr(cls, "AVAILABLE_FILTER_RESETS", [])
            available_filter_resets.extend(cls_available_filter_resets)

        buttons = [
            PhilipsFilterResetButton(hass, entry, config_entry_data, _filter)
            for _filter in FILTER_TYPES
            if _filter in available_filter_resets
            and _filter in status
            and FILTER_TYPES[_filter][FanAttributes.TOTAL] in status
        ]

        async_add_entities(buttons, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsFilterResetButton(PhilipsEntity, ButtonEntity):
    """Define a Philips AirPurifier filter reset button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        kind: str,
    ) -> None:
        """Initialize the button."""

        super().__init__(hass, config, config_entry_data)

        self._description = FILTER_TYPES[kind]
        label = self._description[FanAttributes.LABEL]
        self._attr_translation_key = f"reset_{label}"

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-reset_{label}"

        self._value_key = kind
        self._total_key = self._description[FanAttributes.TOTAL]

    async def async_press(self) -> None:
        """Reset the filter counter to the filter's total lifetime."""
        total = int(self._device_status[self._total_key])
        await self.coordinator.client.set_control_value(self._value_key, total)
        self._device_status[self._value_key] = total
        self._handle_coordinator_update()
