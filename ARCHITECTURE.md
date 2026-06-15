# Architecture — Philips AirPurifier (CoAP)

Home Assistant integration for Philips air purifiers/humidifiers that speak the
local **CoAP** protocol (via the `aioairctrl` library). It is a `local_push`
integration: the device streams status updates, it is not polled.

## Data flow

```
Philips device ──CoAP observe──▶ aioairctrl.CoAPClient
                                      │  (status dicts)
                                      ▼
                               Coordinator (DataUpdateCoordinator[DeviceStatus])
                                      │  async_set_updated_data(status)
                                      ▼
                               CoordinatorEntity subclasses  ──▶ HA state machine
```

* `aioairctrl.CoAPClient` — third-party client. We never poll; we consume its
  `observe_status()` async stream and call `set_control_value(s)` to act.
* `coordinator.py::Coordinator` — extends `DataUpdateCoordinator`. The observe
  loop forwards every status to entities via `async_set_updated_data`. A watchdog
  (`async_call_later`) reconnects when no update arrives within
  `timeout * MISSED_PACKAGE_COUNT` seconds. `status` is a compatibility alias for
  `self.data`.
* Entities read `coordinator.data` and are `available` only while
  `last_update_success` is true.

## File layout

| File | Role |
|------|------|
| `__init__.py` | `async_setup` (serves the custom SVG icons), `async_setup_entry`/`async_unload_entry`, the options-reload listener and the deferred MAC lookup. |
| `const.py` | **Pure constants only**: `DOMAIN`, the `ICON`/`FanModel`/`FanFunction`/`FanAttributes`/`PresetMode` enums, the `PhilipsApi` field-name catalogue and the `PhilipsConfigEntry` type alias. |
| `model.py` | `DeviceInformation` dataclass and the `DeviceStatus` type alias. |
| `coordinator.py` | The push coordinator + reconnect watchdog. |
| `config_entry_data.py` | `ConfigEntryData` — the object stored in `entry.runtime_data`. |
| `config_flow.py` | `ConfigFlow` (menu/scan/manual/DHCP/SSDP, reauth, reconfigure) + `PhilipsOptionsFlow`. |
| `diagnostics.py` | Redacted config-entry diagnostics. |
| `helpers.py` | Pure helpers: `extract_model`/`extract_name` and the optional network scan. |
| `devices/` | One class per device **model**, grouped by generation. |
| `<platform>.py` | One file per entity platform; each owns its `EntityDescription` subclass + descriptions tuple. |

## The device model

The **fan entity is the model class**. `devices/__init__.py::model_to_class` maps a
`FanModel` to a class in `devices/legacy.py` (old `P/A/M` modes), `devices/new_gen.py`
(AC1715/AC0850, `D01…` keys) or `devices/new2_gen.py` (`D03…` integer keys). Each class
declares, as class attributes, which features the model exposes:

```python
class PhilipsAC2729(PhilipsGenericFan):
    AVAILABLE_PRESET_MODES = {...}
    AVAILABLE_SPEEDS = {...}
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.HUMIDITY_TARGET]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.ERROR_CODE]
```

Each platform's `async_setup_entry` reads these lists across the class MRO with
`collect_class_attribute(model_class, "AVAILABLE_…")` and instantiates the matching
entities from its own `*_TYPES` descriptions (whose `key` is the `PhilipsApi` field).

## `unique_id` convention (do not change without migration)

| Entity | Format |
|--------|--------|
| Fan | `{model}-{device_id}` |
| Most entities | `{model}-{device_id}-{description.key.lower()}` |
| Filter sensor | `{model}-{device_id}-{description.translation_key}` |
| Filter-alert | `{model}-{device_id}-filter_alert` |

`model` is `entry.data[CONF_MODEL]`, `device_id` the Philips `DeviceId`. Changing any
of these requires `async_migrate_entry` + a `ConfigEntry.version` bump.

## How to add a new device model

1. Add the model string to `FanModel` in `const.py`.
2. Add a class in the right `devices/<generation>.py`, inheriting the closest base, and
   declare its `AVAILABLE_*` attributes (and `KEY_OSCILLATION`, `CREATE_FAN`, etc.).
3. Register it in `model_to_class` (`devices/__init__.py`).
4. Add any new `PhilipsApi` field names to `const.py` and a matching `EntityDescription`
   in the relevant platform file if the feature is new.

## How to add a new platform

1. Add the domain to `PLATFORMS` in `__init__.py`.
2. Create `<platform>.py` with: a frozen `Philips<Platform>EntityDescription`, a
   `*_TYPES` tuple, an `async_setup_entry` that uses `collect_class_attribute`, and an
   entity class deriving from `PhilipsEntity` (or `PhilipsGenericControlBase`) + the HA
   platform entity. Send commands through `self._async_set_control_value(s)`.
3. Add `AVAILABLE_<X>` to the device classes that expose it and translation keys to
   `strings.json` (+ `translations/`).
