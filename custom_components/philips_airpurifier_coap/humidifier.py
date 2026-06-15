"""Philips Air Purifier & Humidifier humidifier."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FanFunction, PhilipsApi
from .devices import PhilipsGenericControlBase, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PhilipsHumidifierEntityDescription(HumidifierEntityDescription):
    """Describe a Philips humidifier entity."""

    humidity_key: str
    power_key: str
    function_key: str
    on_value: Any
    off_value: Any
    humidifying_value: Any
    idle_value: Any
    switch: bool
    min_humidity: int
    max_humidity: int
    step: int


HUMIDIFIER_TYPES: tuple[PhilipsHumidifierEntityDescription, ...] = (
    PhilipsHumidifierEntityDescription(
        key=PhilipsApi.HUMIDITY_TARGET,
        humidity_key=PhilipsApi.HUMIDITY,
        power_key=PhilipsApi.POWER,
        function_key=PhilipsApi.FUNCTION,
        on_value="1",
        off_value="0",
        humidifying_value="PH",
        idle_value="P",
        switch=True,
        min_humidity=40,
        max_humidity=70,
        step=10,
    ),
    PhilipsHumidifierEntityDescription(
        key=PhilipsApi.NEW2_HUMIDITY_TARGET,
        humidity_key=PhilipsApi.NEW2_HUMIDITY,
        power_key=PhilipsApi.NEW2_POWER,
        function_key=PhilipsApi.NEW2_MODE_C,
        on_value=1,
        off_value=0,
        humidifying_value=1,
        idle_value=5,
        switch=False,
        min_humidity=40,
        max_humidity=70,
        step=10,
    ),
    PhilipsHumidifierEntityDescription(
        key=PhilipsApi.NEW2_HUMIDITY_TARGET2,
        humidity_key=PhilipsApi.NEW2_HUMIDITY,
        power_key=PhilipsApi.NEW2_POWER,
        function_key=PhilipsApi.NEW2_POWER,
        on_value=1,
        off_value=0,
        humidifying_value=1,
        idle_value=0,
        switch=False,
        min_humidity=30,
        max_humidity=70,
        step=5,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the humidifier platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_humidifiers = collect_class_attribute(model_class, "AVAILABLE_HUMIDIFIERS")
    available_preset_modes: dict[str, Any] = {}
    for cls in reversed(model_class.__mro__):
        available_preset_modes.update(getattr(cls, "AVAILABLE_PRESET_MODES", {}))

    async_add_entities(
        PhilipsHumidifier(hass, entry, config_entry_data, description, available_preset_modes)
        for description in HUMIDIFIER_TYPES
        if description.key in available_humidifiers
    )


class PhilipsHumidifier(PhilipsGenericControlBase, HumidifierEntity):
    """Define a Philips AirPurifier humidifier."""

    entity_description: PhilipsHumidifierEntityDescription
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_available_modes: list[str] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsHumidifierEntityDescription,
        available_preset_modes: dict[str, Any],
    ) -> None:
        """Initialize the humidifier."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description
        latest_status = config_entry_data.latest_status

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

        self._available_preset_modes = available_preset_modes
        self._power_key = description.power_key
        self._function_key = description.function_key
        self._humidity_target_key = description.key.partition("#")[0]
        self._humidity_key = description.humidity_key
        self._switch = description.switch

        self._attr_min_humidity = description.min_humidity
        self._attr_max_humidity = description.max_humidity
        self._attr_target_humidity = latest_status.get(self._humidity_target_key)
        self._attr_current_humidity = latest_status.get(self._humidity_key)

        # 2-in-1 devices select humidification vs purification with a switch.
        if self._switch:
            self._attr_supported_features = HumidifierEntityFeature.MODES
            self._attr_available_modes = [
                FanFunction.PURIFICATION,
                FanFunction.PURIFICATION_HUMIDIFICATION,
            ]
        # Pure humidifiers expose the fan modes as humidifier modes.
        elif self._function_key == self._power_key:
            self._attr_supported_features = HumidifierEntityFeature.MODES
            self._attr_available_modes = list(self._available_preset_modes.keys())

    @property
    def action(self) -> HumidifierAction:
        """Return the current action."""
        if self._device_status.get(self._function_key) == self.entity_description.humidifying_value:
            return HumidifierAction.HUMIDIFYING
        return HumidifierAction.IDLE

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._device_status.get(self._humidity_key)

    @property
    def target_humidity(self) -> int | None:
        """Return the target humidity."""
        return self._device_status.get(self._humidity_target_key)

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        if self._switch:
            if (
                self._device_status.get(self._function_key)
                == self.entity_description.humidifying_value
            ):
                return FanFunction.PURIFICATION_HUMIDIFICATION
            return FanFunction.PURIFICATION

        if self._function_key == self._power_key:
            for preset_mode, status_pattern in self._available_preset_modes.items():
                if all(self._device_status.get(k) == v for k, v in status_pattern.items()):
                    return preset_mode

        return None

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the humidifier."""
        if not self._attr_available_modes or mode not in self._attr_available_modes:
            return

        if self._switch:
            if mode == FanFunction.PURIFICATION:
                function_value = self.entity_description.idle_value
            else:
                function_value = self.entity_description.humidifying_value
            await self._async_set_control_values(
                {
                    self._power_key: self.entity_description.on_value,
                    self._function_key: function_value,
                }
            )
        elif self._function_key == self._power_key:
            status_pattern = self._available_preset_modes.get(mode)
            if status_pattern:
                await self._async_set_control_values(status_pattern)

    @property
    def is_on(self) -> bool:
        """Return True if the device is on."""
        return self._device_status.get(self._power_key) != self.entity_description.off_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self._async_set_control_value(self._power_key, self.entity_description.on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self._async_set_control_value(self._power_key, self.entity_description.off_value)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity, snapped to the configured step."""
        step = self.entity_description.step
        humidity = int(humidity)

        # The +/- buttons move by 1; translate that into a full step.
        current_target = self.target_humidity
        if current_target is not None:
            if humidity == int(current_target) + 1:
                humidity = int(current_target) + step
            elif humidity == int(current_target) - 1:
                humidity = int(current_target) - step

        target = round(humidity / step) * step
        target = max(self._attr_min_humidity, min(target, self._attr_max_humidity))
        await self._async_set_control_value(self._humidity_target_key, target)
