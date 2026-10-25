"""Module containing the Coordinator class to manage data requests from the Philips API."""

import asyncio
import contextlib
import logging
from asyncio.tasks import Task
from collections.abc import Callable
from typing import Any

from aioairctrl import CoAPClient
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .status_recovery import StatusRecoveryClient
from .timer import Timer

_LOGGER = logging.getLogger(__name__)

MISSED_PACKAGE_COUNT = 3


class Coordinator:
    """Class to coordinate the data requests from the Philips API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CoAPClient | StatusRecoveryClient,
        host: str,
        status: dict[str, Any] | None,
    ) -> None:
        """Initialize the Coordinator.

        :param hass: HomeAssistant instance.
        :param client: CoAPClient instance.
        :param host: Host address of the device.
        :param status: Initial status of the device.
        """

        self.hass = hass
        self.client = client
        self.host = host
        self.status = status

        self._listeners: list[CALLBACK_TYPE] = []
        self._task: Task | None = None

        self._reconnect_task: Task | None = None
        self._timeout: int = 60

        self._timer_disconnected = Timer(
            timeout=self._timeout * MISSED_PACKAGE_COUNT,
            callback=self.reconnect,
            autostart=True,
        )
        self._timer_disconnected.setAutoRestart(True)

    async def shutdown(self):
        """Shutdown the API connection."""

        if self._timer_disconnected is not None:
            self._timer_disconnected.cancel()

        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            await asyncio.gather(self._reconnect_task, return_exceptions=True)

        await self._stop_observing()

        if self.client is not None:
            await self.client.shutdown()

    async def reconnect(self):
        """Reconnect to the API connection."""

        try:
            if self._reconnect_task is not None:
                self._reconnect_task.cancel()
                self._reconnect_task = None

            self._reconnect_task = asyncio.create_task(self._reconnect())

        except Exception:
            _LOGGER.exception("Exception on starting reconnect!")

    async def _reconnect(self):
        """Reconnect to the API connection."""

        try:
            await self._stop_observing()
            previous_client = self.client
            with contextlib.suppress(Exception):
                await self.client.shutdown()
            self.client = await CoAPClient.create(self.host)
            if isinstance(previous_client, StatusRecoveryClient):
                self.client = previous_client.with_client(self.client)
            self._start_observing()

        except asyncio.CancelledError:
            # Silently drop this exception, because we are responsible for it.
            # Reconnect took to long
            pass

        except Exception:
            _LOGGER.exception("_reconnect error")

    async def async_first_refresh(self) -> None:
        """Refresh the data for the first time."""

        try:
            self.status, timeout = await self.client.get_status()
            self._timeout = timeout
            if self._timer_disconnected is not None:
                self._timer_disconnected.setTimeout(timeout * MISSED_PACKAGE_COUNT)
            _LOGGER.debug("finished first refresh for host %s", self.host)

        except Exception as ex:
            _LOGGER.exception("Config not ready, first refresh failed for host %s", self.host)
            raise ConfigEntryNotReady from ex

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""

        start_observing = not self._listeners
        self._listeners.append(update_callback)

        if start_observing:
            self._start_observing()

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_listener(update_callback)

        return remove_listener

    @callback
    def async_remove_listener(self, update_callback) -> None:
        """Remove data update."""

        self._listeners.remove(update_callback)

        if not self._listeners and self._task and not self._task.cancelling():
            self._task.cancel()

    async def _async_observe_status(self) -> None:
        """Observe the status of the device."""

        async for status in self.client.observe_status():
            self.status = status
            self._timer_disconnected.reset()
            for update_callback in self._listeners:
                update_callback()

    async def _stop_observing(self) -> None:
        """Wait for any in-flight recovery to restore settings before closing."""
        if self._task:
            if not self._task.cancelling():
                self._task.cancel()
            await asyncio.shield(asyncio.gather(self._task, return_exceptions=True))
            self._task = None

    def _start_observing(self) -> None:
        """Schedule state observation."""

        previous = self._task
        if previous and not previous.cancelling():
            previous.cancel()

        async def observe() -> None:
            if previous:
                finished = asyncio.gather(previous, return_exceptions=True)
                try:
                    await asyncio.shield(finished)
                except asyncio.CancelledError:
                    await asyncio.shield(finished)
                    raise
            await self._async_observe_status()

        self._task = asyncio.create_task(observe())
        self._timer_disconnected.reset()
