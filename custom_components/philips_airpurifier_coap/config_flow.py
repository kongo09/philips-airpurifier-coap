"""The Philips AirPurifier component."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import ipaddress
import logging
import re
from typing import Any, cast
from urllib.parse import urlparse

from aioairctrl import CoAPClient
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.util.timeout import TimeoutManager

from .const import (
    CONF_DEVICE_ID,
    CONF_FILTER_ALERT_THRESHOLD,
    CONF_MODEL,
    CONF_STATUS,
    DEFAULT_FILTER_ALERT_THRESHOLD,
    DOMAIN,
    PhilipsApi,
)
from .devices import model_to_class
from .helpers import extract_model, extract_name, scan_for_devices

CONF_METHOD = "method"
CONF_DEVICE = "device"
METHOD_SCAN = "scan"
METHOD_MANUAL = "manual"

_LOGGER = logging.getLogger(__name__)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version in [4, 6]:
            return True
    except ValueError:
        pass
    disallowed = re.compile(r"[^a-zA-Z\d\-]")
    return all(x and not disallowed.search(x) for x in host.split("."))


class PhilipsAirPurifierConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Philips AirPurifier."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PhilipsOptionsFlow:
        """Return the options flow handler."""
        return PhilipsOptionsFlow()

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._model: Any = None
        self._name: Any = None
        self._device_id: str | None = None
        self._wifi_version: Any = None
        self._status: Any = None
        self._discovered_devices: list[dict] = []
        self._scan_task: asyncio.Task | None = None

    def _get_schema(self, user_input):
        """Provide schema for user input."""
        return vol.Schema(
            {vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): cv.string}
        )

    def _resolve_model(self, model: str) -> str | None:
        """Resolve model name to supported model key."""
        model_family = model[:6]
        model_long = f"{model} {self._wifi_version.split('@')[0]}"

        for candidate in [model, model_long, model_family]:
            if candidate in model_to_class:
                _LOGGER.info("Model %s supported", candidate)
                return candidate

        _LOGGER.warning("Model %s of family %s not supported", model, model_family)
        return None

    async def _fetch_device_status(self) -> dict:
        """Create CoAP client and fetch device status."""
        client = None
        timeout = TimeoutManager()

        try:
            async with timeout.async_timeout(30):
                client = await CoAPClient.create(self._host)
                _LOGGER.debug("got a valid client for host %s", self._host)

            async with timeout.async_timeout(30):
                _LOGGER.debug("trying to get status")
                status, _ = await client.get_status()
                _LOGGER.debug("got status")

            return status
        finally:
            if client is not None:
                await client.shutdown()

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """Handle initial step of auto discovery flow."""
        _LOGGER.debug("async_step_dhcp: called, found: %s", discovery_info)

        self._host = discovery_info.ip
        _LOGGER.debug("trying to configure host: %s", self._host)

        try:
            status = await self._fetch_device_status()
            _LOGGER.debug("status for host %s is: %s", self._host, status)
        except TimeoutError:
            _LOGGER.warning(
                "Timeout, host %s looks like a Philips AirPurifier but doesn't answer",
                self._host,
            )
            return self.async_abort(reason="model_unsupported")
        except Exception as ex:
            _LOGGER.warning("Failed to connect: %s", ex)
            return self.async_abort(reason="timeout")

        self._extract_device_info(status)

        resolved_model = self._resolve_model(self._model)
        if resolved_model is None:
            return self.async_abort(reason="model_unsupported")
        self._model = resolved_model

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context.update({"title_placeholders": {CONF_NAME: f"{self._model} {self._name}"}})

        _LOGGER.debug("waiting for async_step_confirm")
        return await self.async_step_confirm()

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        """Handle initial step of SSDP discovery flow."""
        _LOGGER.debug("async_step_ssdp: called, found: %s", discovery_info)

        self._host = discovery_info.ssdp_headers.get("_host", "").split(":")[0]
        if not self._host:
            # Try to extract from SSDP location URL
            location = discovery_info.ssdp_location
            if location:
                self._host = urlparse(location).hostname

        if not self._host:
            _LOGGER.warning("Could not extract host from SSDP discovery info")
            return self.async_abort(reason="no_host")

        _LOGGER.debug("trying to configure host: %s", self._host)

        try:
            status = await self._fetch_device_status()
            _LOGGER.debug("status for host %s is: %s", self._host, status)
        except TimeoutError:
            _LOGGER.warning(
                "Timeout, host %s looks like a Philips AirPurifier but doesn't answer",
                self._host,
            )
            return self.async_abort(reason="model_unsupported")
        except Exception as ex:
            _LOGGER.warning("Failed to connect: %s", ex)
            return self.async_abort(reason="timeout")

        self._extract_device_info(status)

        resolved_model = self._resolve_model(self._model)
        if resolved_model is None:
            return self.async_abort(reason="model_unsupported")
        self._model = resolved_model

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context.update({"title_placeholders": {CONF_NAME: f"{self._model} {self._name}"}})

        _LOGGER.debug("waiting for async_step_confirm")
        return await self.async_step_confirm()

    def _extract_device_info(self, status: dict) -> None:
        """Extract device information from status."""
        self._model = extract_model(status)
        self._wifi_version = status.get(PhilipsApi.WIFI_VERSION)
        self._name = extract_name(status)
        self._device_id = status[PhilipsApi.DEVICE_ID]
        self._status = status

        _LOGGER.debug(
            "Detected host %s as model %s with name: %s and firmware %s",
            self._host,
            self._model,
            self._name,
            self._wifi_version,
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm the dhcp discovered data."""
        _LOGGER.debug("async_step_confirm called with user_input: %s", user_input)

        # user input was provided, so check and save it
        if user_input is not None:
            _LOGGER.debug(
                "entered creation for model %s with name '%s' at %s",
                self._model,
                self._name,
                self._host,
            )
            user_input[CONF_MODEL] = self._model
            user_input[CONF_NAME] = self._name
            user_input[CONF_DEVICE_ID] = cast(str, self._device_id)
            user_input[CONF_HOST] = cast(str, self._host)
            user_input[CONF_STATUS] = self._status

            config_entry_name = f"{self._model} {self._name}"

            return self.async_create_entry(title=config_entry_name, data=user_input)

        _LOGGER.debug("showing confirmation form")
        # show the form to the user
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"model": self._model, "name": self._name},
        )

    async def async_step_user(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Handle initial step - show menu to choose scan or manual entry."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["scan", "manual"],
        )

    async def async_step_scan(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Scan the network for Philips devices, showing progress to the user."""
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(self._async_scan())

        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan",
                progress_action="scanning",
                progress_task=self._scan_task,
            )

        return self.async_show_progress_done(next_step_id="scan_done")

    async def _async_scan(self) -> None:
        """Run the network scan and store newly discovered devices."""
        _LOGGER.info("Starting network scan for Philips devices...")
        all_devices = await scan_for_devices()

        # Filter out already configured devices.
        configured_ids = {entry.unique_id for entry in self._async_current_entries()}
        self._discovered_devices = [
            d for d in all_devices if d.get("status", {}).get("DeviceId") not in configured_ids
        ]

    async def async_step_scan_done(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle scan completion."""
        if not self._discovered_devices:
            _LOGGER.warning("No devices found during network scan")
            return self.async_abort(reason="no_devices_found")

        return await self.async_step_pick_device()

    async def async_step_pick_device(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Let user pick a discovered device."""
        if user_input is not None:
            selected_ip = user_input.get(CONF_DEVICE)
            for device in self._discovered_devices:
                if device["ip"] == selected_ip:
                    self._host = device["ip"]
                    self._status = device["status"]
                    self._extract_device_info(self._status)

                    resolved_model = self._resolve_model(self._model)
                    if resolved_model is None:
                        return self.async_abort(reason="model_unsupported")

                    config_entry_data = {
                        CONF_MODEL: resolved_model,
                        CONF_NAME: self._name,
                        CONF_DEVICE_ID: self._device_id,
                        CONF_HOST: self._host,
                        CONF_STATUS: self._status,
                    }

                    await self.async_set_unique_id(self._device_id)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                    return self.async_create_entry(
                        title=f"{resolved_model} {self._name}",
                        data=config_entry_data,
                    )

            return self.async_abort(reason="device_not_found")

        # Build device options
        device_options = {
            device["ip"]: f"{device['model']} - {device['name']} ({device['ip']})"
            for device in self._discovered_devices
        }

        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(device_options)})
        return self.async_show_form(
            step_id="pick_device",
            data_schema=schema,
            description_placeholders={"count": str(len(self._discovered_devices))},
        )

    async def async_step_manual(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Handle manual IP entry."""
        errors = {}

        if user_input is not None:
            try:
                if not host_valid(user_input[CONF_HOST]):
                    raise InvalidHost  # noqa: TRY301

                self._host = user_input[CONF_HOST]
                _LOGGER.debug("trying to configure host: %s", self._host)

                try:
                    status = await self._fetch_device_status()
                except TimeoutError:
                    _LOGGER.warning("Timeout, host %s doesn't answer", self._host)
                    return self.async_abort(reason="timeout")
                except Exception as ex:
                    _LOGGER.warning("Failed to connect: %s", ex)
                    errors[CONF_HOST] = "connect"
                    raise InvalidHost from ex

                self._extract_device_info(status)

                resolved_model = self._resolve_model(self._model)
                if resolved_model is None:
                    return self.async_abort(reason="model_unsupported")

                config_entry_data = {
                    CONF_MODEL: resolved_model,
                    CONF_NAME: self._name,
                    CONF_DEVICE_ID: self._device_id,
                    CONF_HOST: self._host,
                    CONF_STATUS: status,
                }

                await self.async_set_unique_id(self._device_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                return self.async_create_entry(
                    title=f"{resolved_model} {self._name}",
                    data=config_entry_data,
                )

            except InvalidHost:
                errors[CONF_HOST] = errors.get(CONF_HOST, "host")

        schema = self._get_schema(user_input or {})
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow when the device becomes unreachable."""
        self._host = entry_data.get(CONF_HOST)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth with an updated host if needed."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            self._host = user_input[CONF_HOST]

            try:
                if not host_valid(self._host):
                    raise InvalidHost  # noqa: TRY301

                status = await self._fetch_device_status()
                self._extract_device_info(status)

                # Verify it's still the same device.
                if self._device_id != reauth_entry.unique_id:
                    return self.async_abort(reason="reauth_different_device")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_HOST: self._host, CONF_STATUS: status},
                )

            except TimeoutError:
                errors[CONF_HOST] = "timeout"
            except InvalidHost:
                errors[CONF_HOST] = "host"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors[CONF_HOST] = "connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._get_schema({CONF_HOST: self._host or ""}),
            errors=errors,
            description_placeholders={"name": reauth_entry.title},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_host = user_input[CONF_HOST]

            try:
                if not host_valid(new_host):
                    raise InvalidHost  # noqa: TRY301

                self._host = new_host
                status = await self._fetch_device_status()
                self._extract_device_info(status)

                # Verify it's the same device
                if self._device_id != reconfigure_entry.unique_id:
                    return self.async_abort(reason="reconfigure_different_device")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: new_host, CONF_STATUS: status},
                )

            except TimeoutError:
                errors[CONF_HOST] = "timeout"
            except InvalidHost:
                errors[CONF_HOST] = "host"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure")
                errors[CONF_HOST] = "connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._get_schema({CONF_HOST: reconfigure_entry.data.get(CONF_HOST, "")}),
            errors=errors,
            description_placeholders={"name": reconfigure_entry.title},
        )


class PhilipsOptionsFlow(OptionsFlow):
    """Handle options for the Philips AirPurifier integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_FILTER_ALERT_THRESHOLD, DEFAULT_FILTER_ALERT_THRESHOLD
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_FILTER_ALERT_THRESHOLD, default=current): NumberSelector(
                    NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.SLIDER)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
