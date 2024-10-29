"""Timer class to handle instable Philips CoaP API."""

import asyncio
import contextlib
import logging

_LOGGER = logging.getLogger(__name__)


class CallbackRunningException(Exception):
    """Exception indicating that a callback is still running."""


class Timer:
    """Class to represent a timer when communicating async with the API."""

    _in_callback: bool = False
    _auto_restart: bool = False

    def __init__(self, timeout, callback, autostart=True) -> None:  # noqa: D107
        self._timeout = timeout
        self._callback = callback
        self._task = None

        if autostart:
            self.start()

    async def _job(self):
        while True:
            try:
                self._in_callback = False
                _LOGGER.debug("Starting Timer %ss", self._timeout)
                await asyncio.sleep(self._timeout)
                self._in_callback = True
                _LOGGER.debug("Calling timeout callback")
                await self._callback()
                _LOGGER.debug("Timeout callback finished!")
            except asyncio.exceptions.CancelledError as e:
                _LOGGER.debug("Timer cancelled: %s", e.args)
                break
            except RuntimeError:
                try:
                    # Ensure that the runtime error, is because hass is going down!
                    asyncio.get_running_loop()
                except RuntimeError:
                    # Yes seems like hass is going down, stepping out
                    _LOGGER.warning("RuntimeError! Stopping Timer")
                    self._auto_restart = False
                    self._task = None
                    return
            except:  # noqa: E722
                _LOGGER.exception("Timer callback failure")
            self._in_callback = False
            if not self._auto_restart:
                break

    def setTimeout(self, timeout):
        """Set a new timeout."""
        self._timeout = timeout
        # Set new Timeout immediatly effective
        self.reset()

    def cancel(self, msg="STOP"):
        """Cancel the task."""
        if self._in_callback:
            raise CallbackRunningException("Timedout too late to cancel!")
        if self._task is not None:
            self._task.cancel(msg=msg)
            self._task = None

    def reset(self):
        """Reset the task."""
        # _LOGGER.debug("Cancel current timer...")
        with contextlib.suppress(CallbackRunningException):
            self.cancel(msg="RESET")
        self.start()

    def start(self):
        """Start the task."""
        if self._task is None:
            self._task = asyncio.ensure_future(self._job())

    def setAutoRestart(self, auto_restart):
        """Set the autorestart."""
        self._auto_restart = auto_restart
