"""The Philips AirPurifier component."""

import ipaddress
import logging
import re
from typing import Any

import voluptuous as vol
from aioairctrl import CoAPClient
from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.util.timeout import TimeoutManager

from .const import CONF_DEVICE_ID, CONF_MODEL, CONF_STATUS, DOMAIN, PhilipsApi
from .helpers import extract_model, extract_name, normalize_connection_mac
from .philips import model_to_class

_LOGGER = logging.getLogger(__name__)


def entry_host(entry: ConfigEntry) -> str:
    """Return the host an entry connects to; a host set in options overrides data."""
    return entry.options.get(CONF_HOST, entry.data[CONF_HOST])


@callback
def async_set_entry_host(hass: HomeAssistant, entry: ConfigEntry, host: str) -> bool:
    """Point an entry at a new host and make sure it is set up again with it.

    The host is written where the entry reads it from (options when overridden there,
    data otherwise). A loaded entry reloads through its update listener. An entry that
    never finished setup (e.g. stuck in setup_retry on the old address) has no update
    listener, so its reload is scheduled here.
    """
    if entry_host(entry) == host:
        return False

    if CONF_HOST in entry.options:
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_HOST: host})
    else:
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HOST: host})

    if entry.state is not ConfigEntryState.LOADED:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return True


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
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None
        self._model: Any = None
        self._name: Any = None
        self._device_id: str | None
        self._wifi_version: Any = None
        self._status: Any = None

    def _get_schema(self, user_input):
        """Provide schema for user input."""
        return vol.Schema({vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): cv.string})

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """Handle initial step of auto discovery flow."""
        _LOGGER.debug("async_step_dhcp: called, found: %s", discovery_info)

        # A device we already know must not be probed: these devices keep a single
        # status observer, so a probe takes the status stream away from the running
        # coordinator. Probing a device that has just reconnected also often times out,
        # which used to abort the flow before a changed IP address was ever stored.
        if (entry := self._async_known_entry(discovery_info)) is not None:
            if async_set_entry_host(self.hass, entry, discovery_info.ip):
                _LOGGER.info(
                    "Device %s of %s moved to %s, updated its host",
                    discovery_info.macaddress,
                    entry.title,
                    discovery_info.ip,
                )
            return self.async_abort(reason="already_configured")

        self._host = discovery_info.ip
        _LOGGER.debug("trying to configure host: %s", self._host)

        # let's try and connect to an AirPurifier
        try:
            client = None
            timeout = TimeoutManager()

            # try for 30s to get a valid client
            async with timeout.async_timeout(30):
                client = await CoAPClient.create(self._host)
                _LOGGER.debug("got a valid client for host %s", self._host)

            # we give it 30s to get a status, otherwise we abort
            async with timeout.async_timeout(30):
                _LOGGER.debug("trying to get status")
                status, _ = await client.get_status()
                _LOGGER.debug("got status")

            if client is not None:
                await client.shutdown()

            # get the status out of the queue
            _LOGGER.debug("status for host %s is: %s", self._host, status)

        except TimeoutError:
            _LOGGER.warning(
                r"Timeout, host %s looks like a Philips AirPurifier but doesn't answer, aborting",
                self._host,
            )
            return self.async_abort(reason="model_unsupported")

        except Exception as ex:
            _LOGGER.warning(r"Failed to connect: %s", ex)
            raise exceptions.ConfigEntryNotReady from ex

        # autodetect model
        self._model = extract_model(status)

        # autodetect Wifi version
        self._wifi_version = status.get(PhilipsApi.WIFI_VERSION)

        self._name = extract_name(status)
        self._device_id = status[PhilipsApi.DEVICE_ID]
        _LOGGER.debug(
            "Detected host %s as model %s with name: %s and firmware %s",
            self._host,
            self._model,
            self._name,
            self._wifi_version,
        )
        self._status = status

        # check if model is supported
        model_long = self._model + " " + self._wifi_version.split("@")[0]
        model = self._model
        model_family = self._model[:6]

        if model in model_to_class:
            _LOGGER.info("Model %s supported", model)
            self._model = model
        elif model_long in model_to_class:
            _LOGGER.info("Model %s supported", model_long)
            self._model = model_long
        elif model_family in model_to_class:
            _LOGGER.info("Model family %s supported", model_family)
            self._model = model_family
        else:
            _LOGGER.warning(
                "Model %s of family %s not supported in DHCP discovery",
                model,
                model_family,
            )
            return self.async_abort(reason="model_unsupported")

        # use the device ID as unique_id
        unique_id = self._device_id
        _LOGGER.debug("async_step_user: unique_id=%s", unique_id)

        # set the unique id for the entry, abort if it already exists
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        # store the data for the next step to get confirmation
        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: self._model + " " + self._name,
                }
            }
        )

        # show the confirmation form to the user
        _LOGGER.debug("waiting for async_step_confirm")
        return await self.async_step_confirm()

    @callback
    def _async_known_entry(self, discovery_info: DhcpServiceInfo) -> ConfigEntry | None:
        """Find the configured entry for a discovered device, by MAC first, then by host."""
        entries = self._async_current_entries(include_ignore=False)
        device_registry = dr.async_get(self.hass)

        if mac := normalize_connection_mac(discovery_info.macaddress):
            device = device_registry.async_get_device(connections={(dr.CONNECTION_NETWORK_MAC, mac)})
            if device is not None:
                for entry in entries:
                    if entry.entry_id in device.config_entries:
                        return entry

        # Entries whose MAC could not be detected at setup can only be matched by host.
        # Entries that do have a MAC did not match above, so a device at their (stale)
        # host is a different one and must go through discovery.
        for entry in entries:
            if entry_host(entry) != discovery_info.ip:
                continue
            has_mac = any(
                conn_type == dr.CONNECTION_NETWORK_MAC
                for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
                for conn_type, _ in device.connections
            )
            if not has_mac:
                return entry

        return None

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
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
            user_input[CONF_DEVICE_ID] = self._device_id
            user_input[CONF_HOST] = self._host
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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial step of user config flow."""

        errors = {}
        config_entry_data = user_input

        # user input was provided, so check and save it
        if config_entry_data is not None:
            # first some sanitycheck on the host input
            if not host_valid(config_entry_data[CONF_HOST]):
                raise InvalidHost

            try:
                self._host = config_entry_data[CONF_HOST]
                _LOGGER.debug("trying to configure host: %s", self._host)

                # let's try and connect to an AirPurifier
                try:
                    client = None
                    timeout = TimeoutManager()

                    # try for 30s to get a valid client
                    async with timeout.async_timeout(30):
                        client = await CoAPClient.create(self._host)
                        _LOGGER.debug("got a valid client")

                    # we give it 30s to get a status, otherwise we abort
                    async with timeout.async_timeout(30):
                        _LOGGER.debug("trying to get status")
                        status, _ = await client.get_status()
                        _LOGGER.debug("got status")

                    if client is not None:
                        await client.shutdown()

                except TimeoutError:
                    _LOGGER.warning(r"Timeout, host %s doesn't answer, aborting", self._host)
                    return self.async_abort(reason="timeout")

                except Exception as ex:
                    _LOGGER.warning(r"Failed to connect: %s", ex)
                    raise exceptions.ConfigEntryNotReady from ex

                # autodetect model
                self._model = extract_model(status)

                # autodetect Wifi version
                self._wifi_version = status.get(PhilipsApi.WIFI_VERSION)

                self._name = extract_name(status)
                self._device_id = status[PhilipsApi.DEVICE_ID]
                config_entry_data[CONF_MODEL] = self._model
                config_entry_data[CONF_NAME] = self._name
                config_entry_data[CONF_DEVICE_ID] = self._device_id
                config_entry_data[CONF_HOST] = self._host
                config_entry_data[CONF_STATUS] = status

                _LOGGER.debug(
                    "Detected host %s as model %s with name: %s and firmware: %s",
                    self._host,
                    self._model,
                    self._name,
                    self._wifi_version,
                )

                # check if model is supported
                model_long = self._model + " " + self._wifi_version.split("@")[0]
                model = self._model
                model_family = self._model[:6]

                if model in model_to_class:
                    _LOGGER.info("Model %s supported", model)
                    config_entry_data[CONF_MODEL] = model
                elif model_long in model_to_class:
                    _LOGGER.info("Model %s supported", model_long)
                    config_entry_data[CONF_MODEL] = model_long
                elif model_family in model_to_class:
                    _LOGGER.info("Model family %s supported", model_family)
                    config_entry_data[CONF_MODEL] = model_family
                else:
                    _LOGGER.warning(
                        "Model %s of family %s not supported in user discovery",
                        model,
                        model_family,
                    )
                    return self.async_abort(reason="model_unsupported")

                # use the device ID as unique_id
                config_entry_unique_id = self._device_id
                config_entry_name = f"{self._model} {self._name}"

                # set the unique id for the entry, abort if it already exists
                await self.async_set_unique_id(config_entry_unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                # compile a name and return the config entry
                return self.async_create_entry(title=config_entry_name, data=config_entry_data)

            except InvalidHost:
                errors[CONF_HOST] = "host"
            except exceptions.ConfigEntryNotReady:
                errors[CONF_HOST] = "connect"

        if config_entry_data is None:
            config_entry_data = {}

        # no user_input so far
        schema = self._get_schema(config_entry_data)

        # show the form to the user
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Philips AirPurifier."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow to change the device host address."""
        errors = {}
        current_host = entry_host(self.config_entry)

        if user_input is not None:
            new_host = user_input[CONF_HOST]
            if not host_valid(new_host):
                errors[CONF_HOST] = "host"
            else:
                _LOGGER.debug("options flow: trying to connect to new host %s", new_host)
                try:
                    client = None
                    timeout = TimeoutManager()

                    async with timeout.async_timeout(30):
                        client = await CoAPClient.create(new_host)
                        _LOGGER.debug("options flow: got a valid client for host %s", new_host)

                    async with timeout.async_timeout(30):
                        status, _ = await client.get_status()
                        _LOGGER.debug("options flow: got status from host %s", new_host)

                    if client is not None:
                        await client.shutdown()

                    device_id = status[PhilipsApi.DEVICE_ID]
                    _LOGGER.debug(
                        "options flow: found device_id %s at %s, expected %s",
                        device_id,
                        new_host,
                        self.config_entry.data[CONF_DEVICE_ID],
                    )
                    if device_id != self.config_entry.data[CONF_DEVICE_ID]:
                        _LOGGER.warning(
                            "options flow: device at %s has id %s, does not match configured device %s",
                            new_host,
                            device_id,
                            self.config_entry.data[CONF_DEVICE_ID],
                        )
                        errors[CONF_HOST] = "different_device"
                    else:
                        _LOGGER.debug("options flow: device confirmed, updating host to %s", new_host)
                        options = {**self.config_entry.options, CONF_HOST: new_host}
                        # Store the options now, so an entry that is not loaded (and so
                        # has no update listener) can be reloaded with the new host.
                        # Finishing the flow then writes the same options: a no-op.
                        self.hass.config_entries.async_update_entry(self.config_entry, options=options)
                        if self.config_entry.state is not ConfigEntryState.LOADED:
                            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
                        return self.async_create_entry(title="", data=options)

                except TimeoutError:
                    _LOGGER.warning("options flow: timeout connecting to host %s", new_host)
                    errors[CONF_HOST] = "timeout"
                except Exception as ex:
                    _LOGGER.warning("options flow: failed to connect to host %s: %s", new_host, ex)
                    errors[CONF_HOST] = "connect"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=current_host): cv.string}),
            errors=errors,
        )


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
