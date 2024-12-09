"""Philips Air Purifier & Humidifier Switches."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_CATEGORY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import DOMAIN, SWITCH_OFF, SWITCH_ON, SWITCH_TYPES, FanAttributes
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up platform for switch."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        available_switches = []

        for cls in reversed(model_class.__mro__):
            cls_available_switches = getattr(cls, "AVAILABLE_SWITCHES", [])
            available_switches.extend(cls_available_switches)

        switches = [
            PhilipsSwitch(hass, entry, config_entry_data, switch)
            for switch in SWITCH_TYPES
            if switch in available_switches
        ]

        async_add_entities(switches, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsSwitch(PhilipsEntity, SwitchEntity):
    """Define a Philips AirPurifier switch."""

    _attr_is_on: bool | None = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        switch: str,
    ) -> None:
        """Initialize the switch."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model

        self._description = SWITCH_TYPES[switch]
        self._on = self._description.get(SWITCH_ON)
        self._off = self._description.get(SWITCH_OFF)
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_translation_key = self._description.get(FanAttributes.LABEL)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{switch.lower()}"

        self._attrs: dict[str, Any] = {}
        self.kind = switch

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        return self._device_status.get(self.kind) != self._off

    async def async_turn_on(self, **kwargs) -> None:
        """Switch the switch on."""
        await self.coordinator.client.set_control_value(self.kind, self._on)
        self._device_status[self.kind] = self._on
        self._handle_coordinator_update()

    async def async_turn_off(self, **kwargs) -> None:
        """Switch the switch off."""
        await self.coordinator.client.set_control_value(self.kind, self._off)
        self._device_status[self.kind] = self._off
        self._handle_coordinator_update()
