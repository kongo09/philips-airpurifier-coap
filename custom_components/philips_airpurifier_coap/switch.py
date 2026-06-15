"""Philips Air Purifier & Humidifier switches."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FanAttributes, PhilipsApi
from .devices import PhilipsEntity, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PhilipsSwitchEntityDescription(SwitchEntityDescription):
    """Describe a Philips switch entity."""

    on_value: Any = None
    off_value: Any = None


SWITCH_TYPES: tuple[PhilipsSwitchEntityDescription, ...] = (
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.CHILD_LOCK,
        translation_key=FanAttributes.CHILD_LOCK,
        entity_category=EntityCategory.CONFIG,
        on_value=True,
        off_value=False,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_CHILD_LOCK,
        translation_key=FanAttributes.CHILD_LOCK,
        entity_category=EntityCategory.CONFIG,
        on_value=1,
        off_value=0,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_BEEP,
        translation_key=FanAttributes.BEEP,
        entity_category=EntityCategory.CONFIG,
        on_value=100,
        off_value=0,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_STANDBY_SENSORS,
        translation_key=FanAttributes.STANDBY_SENSORS,
        on_value=1,
        off_value=0,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_AUTO_PLUS_AI,
        translation_key=FanAttributes.AUTO_PLUS,
        on_value=1,
        off_value=0,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_AUTO_QUICKDRY_MODE,
        translation_key=FanAttributes.AUTO_QUICKDRY_MODE,
        on_value=1,
        off_value=0,
    ),
    PhilipsSwitchEntityDescription(
        key=PhilipsApi.NEW2_QUICKDRY_MODE,
        translation_key=FanAttributes.QUICKDRY_MODE,
        on_value=1,
        off_value=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_switches = collect_class_attribute(model_class, "AVAILABLE_SWITCHES")
    async_add_entities(
        PhilipsSwitch(hass, entry, config_entry_data, description)
        for description in SWITCH_TYPES
        if description.key in available_switches
    )


class PhilipsSwitch(PhilipsEntity, SwitchEntity):
    """Define a Philips AirPurifier switch."""

    entity_description: PhilipsSwitchEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        if self.entity_description.key not in self._device_status:
            return None
        return self._device_status[self.entity_description.key] != self.entity_description.off_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_control_value(
            self.entity_description.key, self.entity_description.on_value
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_control_value(
            self.entity_description.key, self.entity_description.off_value
        )
