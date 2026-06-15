"""Base classes for Philips AirPurifier devices."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from ..config_entry_data import ConfigEntryData
from ..const import (
    DOMAIN,
    ICON,
    MANUFACTURER,
    PAP,
    SWITCH_OFF,
    SWITCH_ON,
    PhilipsApi,
    PresetMode,
)
from ..coordinator import Coordinator
from ..helpers import extract_model

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class PhilipsEntity(CoordinatorEntity[Coordinator]):
    """Class to represent a generic Philips entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsEntity."""

        super().__init__(config_entry_data.coordinator)

        self.hass = hass
        self.config_entry = entry
        self.config_entry_data = config_entry_data

        name = self.config_entry_data.device_information.name
        model = extract_model(self._device_status)

        self._attr_device_info = DeviceInfo(
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=self._device_status[PhilipsApi.WIFI_VERSION],
            serial_number=self._device_status[PhilipsApi.DEVICE_ID],
            identifiers={(DOMAIN, self._device_status[PhilipsApi.DEVICE_ID])},
            connections={(CONNECTION_NETWORK_MAC, self.config_entry_data.device_information.mac)}
            if self.config_entry_data.device_information.mac is not None
            else set(),
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def _device_status(self) -> dict[str, Any]:
        """Return the status of the device."""
        return self.coordinator.data or {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.config_entry_data.latest_status = self._device_status
        self.async_write_ha_state()

    async def _async_set_control_value(self, key: str, value: Any) -> None:
        """Send a single control value and optimistically update local state."""
        try:
            await self.coordinator.client.set_control_value(key, value)
        except Exception as ex:  # noqa: BLE001 - surface any client error to the user
            raise HomeAssistantError(
                f"Failed to send command to {self.config_entry_data.device_information.name}"
            ) from ex
        self._device_status[key] = value
        self._handle_coordinator_update()

    async def _async_set_control_values(self, data: dict[str, Any]) -> None:
        """Send several control values and optimistically update local state."""
        try:
            await self.coordinator.client.set_control_values(data=data)
        except Exception as ex:  # noqa: BLE001 - surface any client error to the user
            raise HomeAssistantError(
                f"Failed to send command to {self.config_entry_data.device_information.name}"
            ) from ex
        self._device_status.update(data)
        self._handle_coordinator_update()


class PhilipsGenericControlBase(PhilipsEntity):
    """Class as basis for control entities of a Philips device."""

    AVAILABLE_ATTRIBUTES: list[tuple[Any, ...]] = []
    AVAILABLE_PRESET_MODES: dict[str, dict[str, Any]] = {}
    REPLACE_PRESET: tuple[str, str] | None = None

    _attr_name = None
    _attr_translation_key = PAP

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsGenericControlBase."""

        super().__init__(hass, entry, config_entry_data)

        self._available_attributes: list[tuple[Any, ...]] = []
        self._collect_available_attributes()

        self._preset_modes: list[str] = []
        self._available_preset_modes: dict[str, dict[str, Any]] = {}
        self._collect_available_preset_modes()

    def _collect_available_attributes(self):
        attributes = []

        for cls in reversed(self.__class__.__mro__):
            cls_attributes = getattr(cls, "AVAILABLE_ATTRIBUTES", [])
            attributes.extend(cls_attributes)

        self._available_attributes = attributes

    def _collect_available_preset_modes(self):
        preset_modes = {}

        for cls in reversed(self.__class__.__mro__):
            cls_preset_modes = getattr(cls, "AVAILABLE_PRESET_MODES", {})
            preset_modes.update(cls_preset_modes)

        self._available_preset_modes = preset_modes
        self._preset_modes = list(self._available_preset_modes.keys())

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""

        def append(
            attributes: dict,
            key: str,
            philips_key: str,
            value_map: dict | Callable[[Any, Any], Any] | None = None,
        ):
            # some philips keys are not unique, so # serves as a marker and needs to be filtered out
            philips_clean_key = philips_key.partition("#")[0]

            if philips_clean_key in self._device_status:
                value = self._device_status[philips_clean_key]
                if isinstance(value_map, dict) and value in value_map:
                    value = value_map.get(value, "unknown")
                    if isinstance(value, tuple):
                        value = value[0]
                elif callable(value_map):
                    value = value_map(value, self._device_status)
                attributes.update({key: value})

        device_attributes: dict[str, Any] = {}

        for key, philips_key, *rest in self._available_attributes:
            value_map = rest[0] if len(rest) else None
            append(device_attributes, key, philips_key, value_map)

        return device_attributes


class PhilipsGenericFanBase(PhilipsGenericControlBase, FanEntity):
    """Class as basis to manage a generic Philips fan."""

    CREATE_FAN: bool = True

    AVAILABLE_SPEEDS: dict[str, dict[str, Any]] = {}
    REPLACE_SPEED: tuple[str, str] | None = None
    AVAILABLE_SWITCHES: list[str] = []
    AVAILABLE_LIGHTS: list[str] = []
    AVAILABLE_NUMBERS: list[str] = []
    AVAILABLE_BINARY_SENSORS: list[str] = []
    AVAILABLE_SELECTS: list[str] = []
    AVAILABLE_HEATERS: list[str] = []
    AVAILABLE_HUMIDIFIERS: list[str] = []
    UNAVAILABLE_FILTERS: list[str] = []
    UNAVAILABLE_SENSORS: list[str] = []
    EXTRA_SENSORS: list[str] = []

    KEY_PHILIPS_POWER: str = PhilipsApi.POWER
    STATE_POWER_ON: Any = "1"
    STATE_POWER_OFF: Any = "0"

    KEY_OSCILLATION: dict[str, Any] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsGenericFanBase."""

        super().__init__(hass, entry, config_entry_data)

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}"

        self._speeds: list[str] = []
        self._available_speeds: dict[str, dict[str, Any]] = {}
        self._collect_available_speeds()

        # set the supported features of the fan
        self._attr_supported_features |= (
            FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )

        if self.KEY_OSCILLATION is not None:
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

    def _collect_available_speeds(self):
        speeds = {}

        for cls in reversed(self.__class__.__mro__):
            cls_speeds = getattr(cls, "AVAILABLE_SPEEDS", {})
            speeds.update(cls_speeds)

        self._available_speeds = speeds
        self._speeds = list(self._available_speeds.keys())

        if len(self._speeds) > 0:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return if the fan is on."""
        status = self._device_status.get(self.KEY_PHILIPS_POWER)
        return status == self.STATE_POWER_ON

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ):
        """Turn the fan on."""

        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return

        if percentage:
            await self.async_set_percentage(percentage)
            return

        await self._async_set_control_value(self.KEY_PHILIPS_POWER, self.STATE_POWER_ON)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self._async_set_control_value(self.KEY_PHILIPS_POWER, self.STATE_POWER_OFF)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the supported preset modes."""
        # the fan uses the preset modes as collected from the classes
        return self._preset_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the selected preset mode."""
        # the fan uses the preset modes as collected from the classes

        for preset_mode, status_pattern in self._available_preset_modes.items():
            for k, v in status_pattern.items():
                # check if the speed sensor also used for presets is different from the setting field
                if self.REPLACE_PRESET is not None and k == self.REPLACE_PRESET[0]:
                    k = self.REPLACE_PRESET[1]
                status = self._device_status.get(k)
                if status != v:
                    break
            else:
                return preset_mode

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # the fan uses the preset modes as collected from the classes

        status_pattern = self._available_preset_modes.get(preset_mode)
        if status_pattern:
            await self._async_set_control_values(status_pattern)

    @property
    def speed_count(self) -> int:
        """Return the number of speed options."""
        return len(self._speeds)

    @property
    def oscillating(self) -> bool | None:
        """Return if the fan is oscillating."""

        if self.KEY_OSCILLATION is None:
            return None

        key = next(iter(self.KEY_OSCILLATION))
        values = self.KEY_OSCILLATION.get(key)
        off = values.get(SWITCH_OFF)
        status = self._device_status.get(key)

        if status is None:
            return None

        return status != off

    async def async_oscillate(self, oscillating: bool) -> None:
        """Osciallate the fan."""

        if self.KEY_OSCILLATION is None:
            return

        key = next(iter(self.KEY_OSCILLATION))
        values = self.KEY_OSCILLATION.get(key)
        on = values.get(SWITCH_ON)
        off = values.get(SWITCH_OFF)

        await self._async_set_control_value(key, on if oscillating else off)

    @property
    def percentage(self) -> int | None:
        """Return the speed percentages."""

        for speed, status_pattern in self._available_speeds.items():
            for k, v in status_pattern.items():
                # check if the speed sensor is different from the speed setting field
                if self.REPLACE_SPEED is not None and k == self.REPLACE_SPEED[0]:
                    k = self.REPLACE_SPEED[1]
                if self._device_status.get(k) != v:
                    break
            else:
                return ordered_list_item_to_percentage(self._speeds, speed)

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Return the selected speed percentage."""

        if percentage == 0:
            await self.async_turn_off()
            return

        speed = percentage_to_ordered_list_item(self._speeds, percentage)
        status_pattern = self._available_speeds.get(speed)
        if status_pattern:
            await self._async_set_control_values(status_pattern)

    @property
    def icon(self) -> str:
        """Return the icon of the fan."""
        # the fan uses the preset modes as collected from the classes
        # unfortunately, this cannot be controlled from the icon translation

        if not self.is_on:
            return ICON.POWER_BUTTON

        preset_mode = self.preset_mode

        if preset_mode is None:
            return ICON.FAN_SPEED_BUTTON
        if preset_mode in PresetMode.ICON_MAP:
            return PresetMode.ICON_MAP[preset_mode]

        return ICON.FAN_SPEED_BUTTON
