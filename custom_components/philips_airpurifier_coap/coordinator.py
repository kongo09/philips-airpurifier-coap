"""DataUpdateCoordinator managing push updates from a Philips device over CoAP."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from aioairctrl import CoAPClient

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .model import DeviceStatus

if TYPE_CHECKING:
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

# Number of consecutive missed status reports before we assume the connection
# is dead and trigger a reconnect.
MISSED_PACKAGE_COUNT = 3

# Fallback reporting interval (seconds) until the device tells us its own.
DEFAULT_TIMEOUT = 60


class Coordinator(DataUpdateCoordinator[DeviceStatus]):
    """Coordinate push updates from a Philips AirPurifier over CoAP.

    The device pushes status updates through a CoAP ``observe`` stream rather
    than being polled, so this coordinator does not implement
    ``_async_update_data``. Instead it forwards every observed status to the
    entities via :meth:`async_set_updated_data` and uses a watchdog timer to
    reconnect when updates stop arriving.
    """

    config_entry: PhilipsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: CoAPClient,
        host: str,
        status: DeviceStatus | None = None,
        config_entry: PhilipsConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=config_entry)

        self.client = client
        self.host = host
        self.data = status or {}

        self._observe_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._timeout: int = DEFAULT_TIMEOUT
        self._cancel_watchdog: CALLBACK_TYPE | None = None

    @property
    def status(self) -> DeviceStatus:
        """Return the latest known status (compatibility alias for ``data``)."""
        return self.data or {}

    async def async_first_refresh(self) -> None:
        """Fetch the initial status before the platforms are set up."""
        try:
            status, timeout = await self.client.get_status()
        except Exception as ex:
            _LOGGER.error("First refresh failed for host %s", self.host)
            raise ConfigEntryNotReady from ex

        self.data = status
        self._timeout = timeout or DEFAULT_TIMEOUT
        _LOGGER.debug("Finished first refresh for host %s", self.host)

    async def async_shutdown(self) -> None:
        """Cancel all background work and close the client."""
        self._cancel_watchdog_if_needed()

        if self._observe_task is not None:
            self._observe_task.cancel()
            self._observe_task = None

        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        with contextlib.suppress(Exception):
            await self.client.shutdown()

        await super().async_shutdown()

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> CALLBACK_TYPE:
        """Listen for data updates and start observing on the first listener."""
        start_observing = not self._listeners
        remove_listener = super().async_add_listener(update_callback, context)

        if start_observing:
            self._start_observing()

        @callback
        def remove_and_maybe_stop() -> None:
            remove_listener()
            if not self._listeners:
                self._stop_observing()

        return remove_and_maybe_stop

    @callback
    def _start_observing(self) -> None:
        """Start the CoAP observation task and arm the watchdog."""
        if self._observe_task is not None:
            self._observe_task.cancel()

        self._observe_task = self.hass.async_create_background_task(
            self._async_observe_status(), name=f"{DOMAIN}_observe_{self.host}"
        )
        self._arm_watchdog()

    @callback
    def _stop_observing(self) -> None:
        """Stop the observation task and disarm the watchdog."""
        self._cancel_watchdog_if_needed()

        if self._observe_task is not None:
            self._observe_task.cancel()
            self._observe_task = None

    async def _async_observe_status(self) -> None:
        """Forward every observed status update to the entities."""
        try:
            async for status in self.client.observe_status():
                self.async_set_updated_data(status)
                self._arm_watchdog()
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001 - any failure means the stream is dead
            _LOGGER.debug("Observation stopped for host %s: %s", self.host, ex)
            self.async_set_update_error(ex)

    @callback
    def _arm_watchdog(self) -> None:
        """(Re)arm the watchdog that reconnects when updates stop arriving."""
        self._cancel_watchdog_if_needed()
        self._cancel_watchdog = async_call_later(
            self.hass,
            self._timeout * MISSED_PACKAGE_COUNT,
            self._handle_watchdog_timeout,
        )

    @callback
    def _cancel_watchdog_if_needed(self) -> None:
        """Cancel the watchdog timer if it is armed."""
        if self._cancel_watchdog is not None:
            self._cancel_watchdog()
            self._cancel_watchdog = None

    @callback
    def _handle_watchdog_timeout(self, _now: datetime) -> None:
        """No update arrived in time: schedule a reconnect."""
        _LOGGER.debug(
            "No update from host %s within %ss, reconnecting",
            self.host,
            self._timeout * MISSED_PACKAGE_COUNT,
        )
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()

        self._reconnect_task = self.hass.async_create_background_task(
            self._async_reconnect(), name=f"{DOMAIN}_reconnect_{self.host}"
        )

    async def _async_reconnect(self) -> None:
        """Recreate the CoAP client and resume observing."""
        with contextlib.suppress(Exception):
            await self.client.shutdown()

        try:
            self.client = await CoAPClient.create(self.host)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001 - retry on any connection failure
            _LOGGER.warning("Reconnect to host %s failed: %s", self.host, ex)
            self.async_set_update_error(ex)
            # Try again after the watchdog interval.
            self._arm_watchdog()
            return

        _LOGGER.debug("Reconnected to host %s", self.host)
        self._start_observing()
