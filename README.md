[![HACS Default][hacs_shield]][hacs]
[![GitHub Latest Release][releases_shield]][latest_release]
[![Community Forum][community_forum_shield]][community_forum]

[hacs_shield]: https://img.shields.io/static/v1.svg?label=HACS&message=Default&style=popout&color=green&labelColor=41bdf5&logo=HomeAssistantCommunityStore&logoColor=white
[hacs]: https://hacs.xyz/docs/default_repositories

[latest_release]: https://github.com/kongo09/philips-airpurifier-coap/releases/latest
[releases_shield]: https://img.shields.io/github/release/kongo09/philips-airpurifier-coap.svg?style=popout

[community_forum_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Forum&style=popout&color=41bdf5&logo=HomeAssistant&logoColor=white
[community_forum]: https://community.home-assistant.io/t/philips-air-purifier/53030

This is a `Local Push` integration for Philips airpurifiers and humidifiers.
Currently only encrypted-CoAP is implemented.


## Word of Caution

Due to a bug in the Philips devices, this integration is rather instable. It might or might not work. Even if it seems ok at first, it might stop working after a while. Sometimes, a power cycle of the Philips device helps. Sometimes, only a power cycle and a Home Assistant restart together help. It is frustrating. Do not report this as an issue here. Nobody can help right now. @mhetzi contributed timer code to attempt reconnects if the device is not responsive. Sometimes, that helps. But not always. You've been warned.

It all goes back to some reverse engineering by @rgerganov and you can read about it here: https://xakcop.com/post/ctrl-air-purifier/

Philips has recently introduced a proper API to remote control the devices. However, this only works with the Philips cloud and it is not public (yet?) but only integrates Google Home and Alexa. It used to integrate IFTTT as well, but that seems discontinued.


## Credits

 - Original reverse engineering done by @rgerganov at https://github.com/rgerganov/py-air-control
 - The base of the current integration has been done by @betaboon at https://github.com/betaboon/philips-airpurifier-coap but apparently this is not maintained anymore.
 - The rework has been done by @Denaun at https://github.com/Denaun/philips-airpurifier-coap
 - Obviously, many other people contributed, notably @mhetzi, @Kraineff and @shexbeer

## Coffee

<a href="https://www.buymeacoffee.com/kongo09" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kongo09&repository=philips-airpurifier-coap&category=integration)

## Configuration

* The integration attempts to autodiscover your purifiers. Autodiscovery is based on the MAC address and original hostname of the devices. Home Assistant will notify you, if that is successful.
* Alternatively, go to Configuration -> Devices & Services
* Click `Add Integration`
* Search for `Philips AirPurifier` and select it
* Enter the hostname / IP address of your device
* The model type is detected automatically. You get a warning in the log, if it is not supported.

Note: `configuration.yaml` is no longer supported and your configuration is not automatically migrated. You have to start fresh.

## Re-configuration

- Should your devices change their IP address on the network, they need to be re-configured
- If autodiscovery works for your device and network, Home Assistant will discover the device again (latest at the next restart) and identify that it knows it already. The IP address is then automatically adjusted and no user interaction is needed.
- If autodiscovery doesn't work for you, you can simply add the device again as described above, using its new IP address. Home Assistant will detect that it knows the device already and adjust the configuration.


## Supported models

Note: Some of these models seem to have a newer firmware that does not allow local connections anymore. If you buy the device with the intention to manage it via Home Assistant, make sure you can return it, if the integration doesn't work for you.

- AC0850/11 AWS_Philips_AIR
- AC0850/11 AWS_Philips_AIR_Combo
- AC0850/20 AWS_Philips_AIR
- AC0850/20 AWS_Philips_AIR_Combo
- AC0850/31
- AC0850/81
- AC0850/85
- AC0950
- AC0951
- AC1214
- AC1715
- AC2729
- AC2889
- AC2936
- AC2939
- AC2958
- AC2959
- AC3033
- AC3036
- AC3039
- AC3055
- AC3059
- AC3210
- AC3220
- AC3221
- AC3420
- AC3421
- AC3259
- AC3737
- AC3829
- AC3836
- AC3854/50
- AC3854/51
- AC3858/50
- AC3858/51
- AC3858/83
- AC3858/86
- AC4220
- AC4221
- AC4236
- AC4550
- AC4558
- AC5660
- AC5659
- AMF765
- AMF870
- CX5120
- CX3550
- HU1509
- HU1510
- HU5710


## Is your model not supported yet?

You can help to get us there.

Please open an issue and provide the raw status-data for each combination of modes and speeds for your model.

To aquire those information please follow these steps:

### Prepare the environment

Create yourself a virtual environment

```sh
python -m venv env
source ./env/bin/activate
```

Install `aioairctrl` package inside the virtual environment

```sh
python -m pip install aioairctrl
```

### Aquire raw status-data

- Use the philips-app to activate a mode or speed
- run the following command to aquire the raw data (still in the virtual environment)

```sh
aioairctrl --host $DEVICE_IP status --json
```

to exit the virtual environment, simply type

```sh
deactivate
```

## Debugging

To aquire debug-logs, add the following to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.philips_airpurifier_coap: debug
    coap: debug
    aioairctrl: debug
```

logs should now be available in `home-assistant.log`


## Usage

### Entities

The integration provides `fan` entities for your devices which are [documented here](https://www.home-assistant.io/integrations/fan/). In addition, if your device is a humidifier or a 2-in-1 device, the integration will also provide a `humidifier` entity which is [documented here](https://www.home-assistant.io/integrations/humidifier/). The two entities work together, i.e. the `fan` controls power and settings for the fan operation while the `humidifier` adds extra capabilities.

It also provides a number of `sensor` entities for the air quality and other data measured by the device, as well as some diagnostic `sensor` entities with information about the filter or water fill level for humidifiers. A `switch` entity allows you to control the child lock function, should your device have one, or a set of other capabilities depending on your model. Finally, there are some `light` entities to control the display backlight and the brightness of the air quality display and some `select` entities to set other functions like timers. Few devices also have `number` entities to set certain values.

The goal is, to offer all existing functionality that is also available both, on the device itself but also in the official app.


### Services

Unlike the original `philips_airpurifier_coap` integration, this version does not provide any additional services anymore. Everything can be controlled through the entities provided.


### Attributes

The `fan` entity has some additional attributes not captured with sensors. Specifcs depend on the model. The following list gives an overview:

| attribute |content | example |
|---|---|---|
| name: | Name of the device | bedroom |
| type: | Configured model | AC2729 |
| model_id: | Philips model ID | AC2729/10 |
| product_id: | Philips product ID | 85bc26fae62611e8a1e3061302926720 |
| device_id: | Philips device ID | 3c84c6c8123311ebb1ae8e3584d00715 |
| software_version: | Installed software version on device | 0.2.1 |
| wifi_version: | Installed WIFI version on device | AWS_Philips_AIR\@62.1 |
| error_code: | Philips error code | 49408 |
| error: | Error in clear text | no water |
| preferred_index: | State of preferred air quality index | `PM2.5`, `IAI` |
| runtime: | Time the device is running in readable text | 9 days, 10:44:41 |


### Icons

The integration also provides the original Philips icons for your use in the frontend. The icons can be accessed with the prefix `pap:` and should be visible in the icon picker. Credit for this part of the code goes to @thomasloven

| icon                                                                                           | name                    |
|------------------------------------------------------------------------------------------------|-------------------------|
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/power_button.svg)            | power_button            |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/child_lock_button.svg)       | child_lock_button       |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/auto_mode_button.svg)        | auto_mode_button        |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/fan_speed_button.svg)        | fan_speed_button        |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/humidity_button.svg)         | humidity_button         |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/light_dimming_button.svg)    | light_dimming_button    |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/light_function.svg)          | light_function          |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/ambient_light.svg)           | ambient_light           |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/two_in_one_mode_button.svg)  | two_in_one_mode_button  |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/timer_reset_button.svg)      | timer_reset_button      |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/sleep_mode.svg)              | sleep_mode              |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/auto_mode.svg)               | auto_mode               |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/speed_1.svg)                 | speed_1                 |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/speed_2.svg)                 | speed_2                 |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/speed_3.svg)                 | speed_3                 |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/allergen_mode.svg)           | allergen_mode           |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/purification_only_mode.svg)  | purification_only_mode  |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/two_in_one_mode.svg)         | two_in_one_mode         |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/bacteria_virus_mode.svg)     | bacteria_virus_mode     |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/pollution_mode.svg)          | pollution_mode          |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/nanoprotect_filter.svg)      | nanoprotect_filter      |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/filter_replacement.svg)      | filter_replacement      |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/water_refill.svg)            | water_refill            |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/prefilter_cleaning.svg)      | prefilter_clearning     |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/prefilter_wick_cleaning.svg) | prefilter_wick_cleaning |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/pm25.svg)                    | pm25                    |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/iai.svg)                     | iai                     |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/wifi.svg)                    | wifi                    |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/reset.svg)                   | reset                   |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/circulate.svg)               | circulate               |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/clean.svg)                   | clean                   |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/mode.svg)                    | mode                    |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/pm25b.svg)                   | pm25b                   |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/rotate.svg)                  | rotate                  |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/oscillate.svg)               | oscillate               |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/heating.svg)                 | heating                 |
| ![Preview](./custom_components/philips_airpurifier_coap/icons/pap/gas.svg)                     | gas                     |

Note: you might have to clear your browser cache after installation to see the icons.
