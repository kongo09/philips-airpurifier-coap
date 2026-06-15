"""Helper functions for Philips air purifier status."""

from __future__ import annotations

import asyncio
import logging
import socket

from aioairctrl import CoAPClient

from .const import PhilipsApi

_LOGGER = logging.getLogger(__name__)


def extract_name(status: dict) -> str:
    """Extract the name from the status."""
    for name_key in [PhilipsApi.NAME, PhilipsApi.NEW_NAME, PhilipsApi.NEW2_NAME]:
        name = status.get(name_key)
        if name:
            return name
    return ""


def extract_model(status: dict) -> str:
    """Extract the model from the status."""
    for model_key in [
        PhilipsApi.MODEL_ID,
        PhilipsApi.NEW_MODEL_ID,
        PhilipsApi.NEW2_MODEL_ID,
    ]:
        model = status.get(model_key)
        if model:
            return model[:9]
    return ""


def get_local_ip() -> str | None:
    """Get the local IP address of this machine."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        return local_ip
    except Exception:
        return None


def get_active_ips_from_arp() -> list[str]:
    """Get list of active IPs from ARP table."""
    active_ips = []
    try:
        with open("/proc/net/arp") as f:
            lines = f.readlines()[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 4 and parts[2] == "0x2":  # Valid entry
                    active_ips.append(parts[0])
    except Exception as ex:
        _LOGGER.debug("Could not read ARP table: %s", ex)
    return active_ips


async def ping_sweep(network_prefix: str) -> None:
    """Send UDP probes across the subnet to populate the ARP table."""
    _LOGGER.debug("Ping sweep on %s.0/24 to discover active hosts", network_prefix)

    async def probe(ip: str, port: int) -> None:
        """Send a single UDP packet to trigger an ARP entry."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.sendto(b"\x00", (ip, port))
            sock.close()
        except OSError:
            pass

    # Send UDP packets to common ports to trigger ARP resolution.
    tasks = []
    for i in range(1, 255):
        ip = f"{network_prefix}.{i}"
        tasks.append(probe(ip, 5683))  # CoAP
        tasks.append(probe(ip, 80))  # HTTP

    await asyncio.gather(*tasks)
    await asyncio.sleep(1)  # Wait for ARP responses


async def _check_single_ip(
    ip: str,
    semaphore: asyncio.Semaphore,
    timeout: float,
) -> dict | None:
    """Check a single IP for a Philips device."""
    async with semaphore:
        client = None
        try:
            # Quick connection timeout - CoAP devices respond fast
            client = await asyncio.wait_for(CoAPClient.create(ip), timeout=3)
            status, _ = await asyncio.wait_for(client.get_status(), timeout=timeout)
            if status:
                model = extract_model(status)
                name = extract_name(status)
                _LOGGER.info("Found Philips device at %s: %s %s", ip, model, name)
                return {"ip": ip, "model": model, "name": name, "status": status}
        except TimeoutError:
            pass  # Expected for non-Philips devices
        except asyncio.CancelledError:
            _LOGGER.debug("Cancelled checking %s", ip)
        except Exception:  # noqa: S110
            pass  # Silently ignore non-Philips devices
        finally:
            if client:
                try:
                    await asyncio.wait_for(client.shutdown(), timeout=1)
                except Exception:  # noqa: S110
                    pass  # Best effort shutdown
        return None


async def scan_for_devices(timeout: float = 8.0) -> list[dict]:
    """Scan the local network for Philips air purifiers.

    Optimized scan strategy:
    1. First scan only IPs from ARP table (very fast)
    2. If nothing found, scan common DHCP range as fallback

    Returns a list of dicts with 'ip', 'model', 'name' keys.
    """
    # Suppress noisy CoAP logs during scan
    logging.getLogger("coap").setLevel(logging.ERROR)
    logging.getLogger("aioairctrl").setLevel(logging.WARNING)

    local_ip = get_local_ip()
    if not local_ip:
        _LOGGER.warning("Could not determine local IP address")
        return []

    network_prefix = ".".join(local_ip.split(".")[:3])

    # Step 1: Quick ping sweep to populate ARP table
    await ping_sweep(network_prefix)

    # Step 2: First try ARP IPs only (fast scan)
    arp_ips = get_active_ips_from_arp()
    arp_ips = [ip for ip in arp_ips if ip.startswith(network_prefix + ".")]

    found_devices = []
    semaphore = asyncio.Semaphore(50)  # High parallelism for speed

    if arp_ips:
        _LOGGER.info("Fast scan: checking %d IPs from ARP table...", len(arp_ips))
        tasks = [_check_single_ip(ip, semaphore, timeout) for ip in arp_ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        found_devices = [r for r in results if isinstance(r, dict)]

    # Step 3: If nothing found, scan common DHCP range as fallback
    if not found_devices:
        common_ips = [f"{network_prefix}.{i}" for i in range(1, 101)]
        # Exclude already scanned IPs
        common_ips = [ip for ip in common_ips if ip not in arp_ips]
        _LOGGER.info("Fallback scan: checking %d common IPs...", len(common_ips))
        tasks = [_check_single_ip(ip, semaphore, timeout) for ip in common_ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        found_devices = [r for r in results if isinstance(r, dict)]

    # Restore log levels
    logging.getLogger("coap").setLevel(logging.WARNING)
    logging.getLogger("aioairctrl").setLevel(logging.INFO)

    _LOGGER.info("Scan complete. Found %d device(s)", len(found_devices))
    return found_devices
