# Agents Guidelines for philips_airpurifier_coap

## Project Overview

Home Assistant custom integration for Philips air purifiers, humidifiers, and
heaters that communicate over CoAP. Supports 50+ device models across three
API generations.

- **Domain:** `philips_airpurifier_coap`
- **Platforms:** `binary_sensor`, `climate`, `fan`, `humidifier`, `light`,
  `number`, `select`, `sensor`, `switch`
- **External dependencies:** `aioairctrl` (CoAP client), `getmac` (MAC detection)
- **HA dependencies:** `frontend`, `http`
- **IoT class:** `local_push`

## File Structure

```
custom_components/philips_airpurifier_coap/
├── __init__.py           # Entry setup/unload, icon serving, MAC detection
├── config_flow.py        # Config flow with DHCP discovery + options flow
├── config_entry_data.py  # ConfigEntryData dataclass
├── coordinator.py        # DataUpdateCoordinator with push-based updates
├── philips.py            # Base entity classes + 50+ device-specific fan classes
├── model.py              # DeviceInformation, DeviceStatus, TypedDict descriptors
├── helpers.py            # extract_name(), extract_model()
├── const.py              # DOMAIN, enums, API mappings, entity type dicts
├── timer.py              # Async timer utility
├── binary_sensor.py      # Water tank / humidification sensors
├── climate.py            # Heater entities (HVAC mode, temperature, swing)
├── fan.py                # Fan platform setup
├── humidifier.py         # Humidifier entities
├── light.py              # Display backlight / brightness
├── number.py             # Oscillation angle, target temperature
├── select.py             # Function, lamp mode, timer, etc.
├── sensor.py             # Air quality, filter life, RSSI
├── switch.py             # Child lock, beep, standby sensors
├── manifest.json         # Integration metadata
├── strings.json          # English translation strings
├── icons/                # Custom PAP icons (static served via HTTP)
└── translations/         # Translation files
```

## Architecture

### Three Device Generations

The integration supports three CoAP API variants:

1. **Original** (`PhilipsGenericFan`) — uses keys like `pwr`, `mode`, `om`
2. **New** (`PhilipsNewGenericFan`) — uses keys like `D03-02`, `D03-12`
3. **New2** (`PhilipsNew2GenericFan`) — uses keys like `D03102`, `D03112`

Each generation has its own `PhilipsApi` field mappings in `const.py`.

### Class Hierarchy (philips.py)

```
PhilipsEntity (base — coordinator access, availability, device_info)
├── PhilipsGenericControlBase (set values via CoAP client)
│   ├── PhilipsGenericFanBase (speed/preset management)
│   │   ├── PhilipsGenericFan (original API)
│   │   ├── PhilipsNewGenericFan (new API)
│   │   └── PhilipsNew2GenericFan (new2 API)
│   ├── PhilipsBinarySensor
│   ├── PhilipsHeater (climate)
│   ├── PhilipsHumidifier
│   ├── PhilipsLight
│   ├── PhilipsNumber
│   ├── PhilipsSelect
│   ├── PhilipsSensor / PhilipsFilterSensor
│   └── PhilipsSwitch
└── model_to_class (FanModel → device class mapping)
```

### Entity Creation Pattern

Platform `async_setup_entry` functions:
1. Look up the device model from `config_entry.data`
2. Map model → device class via `model_to_class`
3. Inspect `AVAILABLE_*` class attributes to determine which entities to create
4. Create entities using type descriptors from `const.py`

### Data Flow

1. `Coordinator` connects to device via `aioairctrl` CoAP client
2. Device pushes status updates → coordinator stores in `self.data`
3. `async_set_updated_data()` notifies all entity listeners
4. Entities read values from `self.coordinator.data`
5. Control commands sent via `self._client.set_control_values()`

### Custom Icons

Custom PAP icons are served via HTTP at `/api/philips_airpurifier_coap/icons/`.
The `ICON` enum maps icon names to filenames.

## Key Patterns

- **ConfigEntryData:** dataclass on `entry.runtime_data` holding client,
  coordinator, device_information, latest_status
- **DHCP discovery:** 5 MAC prefixes + hostname pattern `mxchip*` +
  `registered_devices` trigger
- **Reconnection:** Coordinator uses Timer; if 3 status updates missed,
  triggers full reconnect cycle
- **Model detection:** Config flow tries exact model match, then model + firmware
  suffix, then model family (first 6 chars)

## Development

### Prerequisites

- Python 3.13+
- Linux environment (Home Assistant core requires `fcntl`)
- Use the devcontainer for development

### Running in devcontainer

```bash
# Open in VS Code with Dev Containers extension
# Or: devcontainer up --workspace-folder .
```

### Linting

```bash
ruff check custom_components/ tests/
ruff format --check custom_components/ tests/
```

### Testing

```bash
python -m pytest tests/ -x -q
```

### Coverage target

90%+ (to be established)

## Code Style

Follow [Home Assistant code style](https://developers.home-assistant.io/docs/development_guidelines):

- Use `ruff` for linting and formatting (replaces black, flake8, isort)
- Line length: 100
- Target: Python 3.13
- Type hints on all public functions
- Use `async`/`await` consistently
- Entity attributes use `_attr_*` pattern
- Prefer `hass.config_entries.async_forward_entry_setups()` over individual
  platform forwards
- Translation keys in `strings.json`, never hardcoded user-facing strings

## Testing Guidelines

Follow [Home Assistant testing guidelines](https://developers.home-assistant.io/docs/development_testing):

- Use `pytest-homeassistant-custom-component` for test infrastructure
- `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`
- Mock the `aioairctrl` CoAP client, never make real network calls
- Test each platform independently
- Config flow tests need `enable_custom_integrations` fixture
- Use `MockConfigEntry` for entry setup
- Patch at module import path, not instance level

## PR & Commit Conventions

- Conventional commit style: `feat:`, `fix:`, `refactor:`, `test:`, `ci:`, `docs:`
- One logical change per commit
- PR description should explain the "why"
- All CI checks must pass before merge
