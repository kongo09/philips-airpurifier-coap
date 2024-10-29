"""The Philips AirPurifier component."""

import ipaddress
import logging
import re
from typing import Any

from aioairctrl import CoAPClient
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util.timeout import TimeoutManager

from .const import CONF_DEVICE_ID, CONF_MODEL, DOMAIN, PhilipsApi
from .philips import model_to_class

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

    def __init__(self) -> None:
        """Initialize."""
        self._host: str = None
        self._model: Any = None
        self._name: Any = None
        self._device_id: str = None
        self._wifi_version: Any = None

    def _get_schema(self, user_input):
        """Provide schema for user input."""
        return vol.Schema(
            {vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): cv.string}
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle initial step of auto discovery flow."""
        _LOGGER.debug("async_step_dhcp: called, found: %s", discovery_info)

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
        model_map = map(
            status.get,
            [
                PhilipsApi.MODEL_ID,
                PhilipsApi.NEW_MODEL_ID,
                PhilipsApi.NEW2_MODEL_ID,
            ],
        )
        _LOGGER.debug("model_map retrieved: %s", model_map)
        model_filter = filter(None, model_map)
        _LOGGER.debug("model_filter applied: %s", model_filter)
        model_list = list(model_filter)
        _LOGGER.debug("model_list built: %s", model_list)
        first_model = model_list[0]
        _LOGGER.debug("first model selected: %s", first_model)
        self._model = first_model[:9]
        _LOGGER.debug("model type extracted: %s", self._model)

        # autodetect Wifi version
        self._wifi_version = status.get(PhilipsApi.WIFI_VERSION)

        # autodetect name
        self._name = list(
            filter(
                None,
                map(
                    status.get,
                    [PhilipsApi.NAME, PhilipsApi.NEW_NAME, PhilipsApi.NEW2_NAME],
                ),
            )
        )[0]
        self._device_id = status[PhilipsApi.DEVICE_ID]
        _LOGGER.debug(
            "Detected host %s as model %s with name: %s",
            self._host,
            self._model,
            self._name,
        )

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

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
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

            return self.async_create_entry(
                title=self._model + " " + self._name, data=user_input
            )

        _LOGGER.debug("showing confirmation form")
        # show the form to the user
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"model": self._model, "name": self._name},
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle initial step of user config flow."""

        errors = {}

        # user input was provided, so check and save it
        if user_input is not None:
            try:
                # first some sanitycheck on the host input
                if not host_valid(user_input[CONF_HOST]):
                    raise InvalidHost  # noqa: TRY301
                self._host = user_input[CONF_HOST]
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
                    _LOGGER.warning(
                        r"Timeout, host %s doesn't answer, aborting", self._host
                    )
                    return self.async_abort(reason="timeout")

                except Exception as ex:
                    _LOGGER.warning(r"Failed to connect: %s", ex)
                    raise exceptions.ConfigEntryNotReady from ex

                # autodetect model
                model_map = map(
                    status.get,
                    [
                        PhilipsApi.MODEL_ID,
                        PhilipsApi.NEW_MODEL_ID,
                        PhilipsApi.NEW2_MODEL_ID,
                    ],
                )
                _LOGGER.debug("model_map retrieved: %s", model_map)
                model_filter = filter(None, model_map)
                _LOGGER.debug("model_filter applied: %s", model_filter)
                model_list = list(model_filter)
                _LOGGER.debug("model_list built: %s", model_list)
                first_model = model_list[0]
                _LOGGER.debug("first model selected: %s", first_model)
                self._model = first_model[:9]
                _LOGGER.debug("model type extracted: %s", self._model)

                # autodetect Wifi version
                self._wifi_version = status.get(PhilipsApi.WIFI_VERSION)

                # autodetect name
                self._name = list(
                    filter(
                        None,
                        map(
                            status.get,
                            [
                                PhilipsApi.NAME,
                                PhilipsApi.NEW_NAME,
                                PhilipsApi.NEW2_NAME,
                            ],
                        ),
                    )
                )[0]
                self._device_id = status[PhilipsApi.DEVICE_ID]
                user_input[CONF_MODEL] = self._model
                user_input[CONF_NAME] = self._name
                user_input[CONF_DEVICE_ID] = self._device_id

                _LOGGER.debug(
                    "Detected host %s as model %s with name: %s",
                    self._host,
                    self._model,
                    self._name,
                )

                # check if model is supported
                model_long = self._model + " " + self._wifi_version.split("@")[0]
                model = self._model
                model_family = self._model[:6]

                if model in model_to_class:
                    _LOGGER.info("Model %s supported", model)
                    user_input[CONF_MODEL] = model
                elif model_long in model_to_class:
                    _LOGGER.info("Model %s supported", model_long)
                    user_input[CONF_MODEL] = model_long
                elif model_family in model_to_class:
                    _LOGGER.info("Model family %s supported", model_family)
                    user_input[CONF_MODEL] = model_family
                else:
                    return self.async_abort(reason="model_unsupported")

                # use the device ID as unique_id
                unique_id = self._device_id
                _LOGGER.debug("async_step_user: unique_id=%s", unique_id)

                # set the unique id for the entry, abort if it already exists
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

                # compile a name and return the config entry
                return self.async_create_entry(
                    title=self._model + " " + self._name, data=user_input
                )

            except InvalidHost:
                errors[CONF_HOST] = "host"
            except exceptions.ConfigEntryNotReady:
                errors[CONF_HOST] = "connect"

        if user_input is None:
            user_input = {}

        # no user_input so far
        # what to ask the user
        schema = self._get_schema(user_input)

        # show the form to the user
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
