"""Tests for helper functions."""

import asyncio
from unittest.mock import AsyncMock, mock_open, patch

from custom_components.philips_airpurifier_coap import helpers
from custom_components.philips_airpurifier_coap.const import PhilipsApi
from custom_components.philips_airpurifier_coap.helpers import extract_model, extract_name


class TestExtractName:
    """Tests for extract_name function."""

    def test_extract_name_legacy(self):
        """Test extracting name from legacy API key."""
        status = {PhilipsApi.NAME: "Living Room"}
        assert extract_name(status) == "Living Room"

    def test_extract_name_new(self):
        """Test extracting name from new API key."""
        status = {PhilipsApi.NEW_NAME: "Bedroom"}
        assert extract_name(status) == "Bedroom"

    def test_extract_name_new2(self):
        """Test extracting name from new2 API key."""
        status = {PhilipsApi.NEW2_NAME: "Office"}
        assert extract_name(status) == "Office"

    def test_extract_name_priority(self):
        """Test that legacy name takes priority over new names."""
        status = {
            PhilipsApi.NAME: "Legacy",
            PhilipsApi.NEW_NAME: "New",
            PhilipsApi.NEW2_NAME: "New2",
        }
        assert extract_name(status) == "Legacy"

    def test_extract_name_fallback_to_new(self):
        """Test fallback to new name when legacy is missing."""
        status = {
            PhilipsApi.NEW_NAME: "New",
            PhilipsApi.NEW2_NAME: "New2",
        }
        assert extract_name(status) == "New"

    def test_extract_name_empty_status(self):
        """Test extracting name from empty status."""
        assert extract_name({}) == ""

    def test_extract_name_none_value(self):
        """Test extracting name when value is None."""
        status = {PhilipsApi.NAME: None}
        assert extract_name(status) == ""

    def test_extract_name_empty_string(self):
        """Test extracting name when value is empty string."""
        status = {PhilipsApi.NAME: ""}
        # Empty string is falsy, should continue to next key or return ""
        assert extract_name(status) == ""


class TestExtractModel:
    """Tests for extract_model function."""

    def test_extract_model_legacy(self):
        """Test extracting model from legacy API key."""
        status = {PhilipsApi.MODEL_ID: "AC3033/10"}
        assert extract_model(status) == "AC3033/10"

    def test_extract_model_new(self):
        """Test extracting model from new API key."""
        status = {PhilipsApi.NEW_MODEL_ID: "AC1715/10"}
        assert extract_model(status) == "AC1715/10"

    def test_extract_model_new2(self):
        """Test extracting model from new2 API key."""
        status = {PhilipsApi.NEW2_MODEL_ID: "AC0950/10"}
        assert extract_model(status) == "AC0950/10"

    def test_extract_model_truncates_to_9_chars(self):
        """Test that model is truncated to 9 characters."""
        status = {PhilipsApi.MODEL_ID: "AC3033/10_EXTRA_LONG_STRING"}
        assert extract_model(status) == "AC3033/10"
        assert len(extract_model(status)) == 9

    def test_extract_model_priority(self):
        """Test that legacy model takes priority over new models."""
        status = {
            PhilipsApi.MODEL_ID: "AC1214/10",
            PhilipsApi.NEW_MODEL_ID: "AC1715/10",
            PhilipsApi.NEW2_MODEL_ID: "AC0950/10",
        }
        assert extract_model(status) == "AC1214/10"

    def test_extract_model_fallback_to_new(self):
        """Test fallback to new model when legacy is missing."""
        status = {
            PhilipsApi.NEW_MODEL_ID: "AC1715/10",
            PhilipsApi.NEW2_MODEL_ID: "AC0950/10",
        }
        assert extract_model(status) == "AC1715/10"

    def test_extract_model_empty_status(self):
        """Test extracting model from empty status."""
        assert extract_model({}) == ""

    def test_extract_model_none_value(self):
        """Test extracting model when value is None."""
        status = {PhilipsApi.MODEL_ID: None}
        assert extract_model(status) == ""

    def test_extract_model_short_string(self):
        """Test extracting model shorter than 9 characters."""
        status = {PhilipsApi.MODEL_ID: "AC3033"}
        assert extract_model(status) == "AC3033"


class TestNetworkScan:
    """Tests for the network discovery helpers."""

    def test_get_local_ip(self):
        """A reachable socket reveals the local IP."""
        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.getsockname.return_value = ("192.168.1.10", 0)
            assert helpers.get_local_ip() == "192.168.1.10"

    def test_get_local_ip_failure(self):
        """A socket error yields None."""
        with patch("socket.socket", side_effect=OSError):
            assert helpers.get_local_ip() is None

    def test_get_active_ips_from_arp(self):
        """Only entries with a valid flag (0x2) are returned."""
        arp = (
            "IP address  HW type  Flags  HW address  Mask  Device\n"
            "192.168.1.50  0x1  0x2  aa:bb:cc:dd:ee:ff  *  eth0\n"
            "192.168.1.51  0x1  0x0  00:00:00:00:00:00  *  eth0\n"
        )
        with patch("builtins.open", mock_open(read_data=arp)):
            ips = helpers.get_active_ips_from_arp()
        assert "192.168.1.50" in ips
        assert "192.168.1.51" not in ips

    async def test_check_single_ip_found(self):
        """A responding Philips device is returned with its model and name."""
        client = AsyncMock()
        client.get_status = AsyncMock(
            return_value=(
                {
                    PhilipsApi.MODEL_ID: "AC3033/10",
                    PhilipsApi.NAME: "Living Room",
                    PhilipsApi.DEVICE_ID: "id",
                },
                60,
            )
        )
        client.shutdown = AsyncMock()
        with patch(
            "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
            AsyncMock(return_value=client),
        ):
            result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
        assert result["ip"] == "1.2.3.4"
        assert result["model"] == "AC3033/10"

    async def test_check_single_ip_not_philips(self):
        """A non-responding host yields None."""
        with patch(
            "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
            AsyncMock(side_effect=TimeoutError),
        ):
            result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
        assert result is None

    async def test_ping_sweep(self):
        """The ping sweep sends UDP probes across the subnet."""
        with (
            patch("socket.socket"),
            patch(
                "custom_components.philips_airpurifier_coap.helpers.asyncio.sleep",
                AsyncMock(),
            ),
        ):
            await helpers.ping_sweep("192.168.1")

    async def test_scan_for_devices(self):
        """The scan returns the devices found via the ARP table."""
        device = {"ip": "192.168.1.50", "model": "AC3033/10", "name": "x", "status": {}}
        with (
            patch.object(helpers, "get_local_ip", return_value="192.168.1.10"),
            patch.object(helpers, "ping_sweep", AsyncMock()),
            patch.object(helpers, "get_active_ips_from_arp", return_value=["192.168.1.50"]),
            patch.object(helpers, "_check_single_ip", AsyncMock(return_value=device)),
        ):
            devices = await helpers.scan_for_devices(timeout=0.1)
        assert devices == [device]

    async def test_scan_for_devices_no_local_ip(self):
        """The scan returns nothing when the local IP cannot be determined."""
        with patch.object(helpers, "get_local_ip", return_value=None):
            assert await helpers.scan_for_devices() == []
