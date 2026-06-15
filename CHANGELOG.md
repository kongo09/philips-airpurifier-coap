# Changelog

All notable changes to the Philips AirPurifier CoAP integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Full internal overhaul. The `unique_id` of every entity is unchanged, so existing
automations and history are preserved.

### Changed
- **Coordinator** now extends Home Assistant's `DataUpdateCoordinator` (push pattern via
  `async_set_updated_data`); the custom `Timer` was replaced by an `async_call_later`
  reconnect watchdog, and entities derive from `CoordinatorEntity`.
- **Entities** migrated from string-keyed `dict` descriptions to frozen
  `EntityDescription` dataclasses; the duplicated MRO walk is now `collect_class_attribute()`.
- **Config flow** uses `ConfigFlowResult` (not the deprecated `FlowResult`),
  `_get_reauth_entry()`/`_get_reconfigure_entry()` and `async_update_reload_and_abort()`.
- `const.py` reduced from 1066 to ~560 lines (pure constants); `model.py` from 126 to 24.

### Added
- Options flow to configure the filter-alert threshold per config entry.
- `loggers` declared in `manifest.json`.
- Exhaustive pytest suite (~91% coverage).

### Fixed
- The network **scan flow never ran** (`async_show_progress` was missing its
  `progress_task`); scans now execute and a device can be picked.
- `light.is_on`/`brightness` could crash on `int(None)`; `light.async_turn_on` could raise
  `UnboundLocalError`.
- `switch.is_on` reported *on* when its key was absent; it now reports *unknown*.
- `select.current_option` returned the string `"None"` for unknown values; it now returns `None`.
- `climate.async_set_temperature` crashed when called without a temperature.
- `helpers.ping_sweep` always returned an empty set; `fan.async_set_percentage` could crash
  on an unknown speed.
- Device actions now raise `HomeAssistantError` on client failure.

### Removed
- Dead code: `timer.py`, unused constants (`TEST_ON`, `DATA_KEY_*`, `FanUnits`, …) and
  redundant tooling (`[tool.black]`, `[tool.isort]`, `.flake8`).

## [0.37.0] - 2025-01-18

### Changed
- Optimized startup time with parallel operations
- Deferred MAC address lookup to background task (non-blocking)
- Added 5s timeout for CoAP client creation

### Fixed
- Pre-commit fixes and code quality improvements
- HA/HACS compliance fixes
- Complete missing translations for de, bg, nl, ro, sk

## [0.36.0] - 2025-01-17

### Added
- Spanish translation

### Fixed
- Capitalize 'Humidifying' state for consistency
- Replace ConfigEntryNotReady with proper abort in config flow

## [0.35.0] - 2025-01-04

### Added
- French translation
- Child lock support for AC303x family
- Water level sensor for AC3420
- Child lock for AC3858/50

### Fixed
- DhcpServiceInfo import deprecation
- Hassfest action configuration
- TVOC unit display

### Changed
- Major refactoring and new features
- Optimized network scan performance

## Previous Versions

For changes prior to version 0.35.0, please refer to the [commit history](https://github.com/kongo09/philips-airpurifier-coap/commits/master).
