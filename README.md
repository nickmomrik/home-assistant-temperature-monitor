# Home Assistant - Temperature & Humidity Sensors
My goal with this project was to create a device I could leave in the garage, which would push temperature and humidity data to Home Assistant. I also wanted to be able to enable a "monitor" mode when I turn on the heat in the garage so the system would alert me when a certain temperature was reached. See the [working version on my blog](https://nickmomrik.com/2017/01/13/garage-temperature-sensor-monitor/).

Hardware used:
* [Raspberry Pi Zero](https://www.adafruit.com/products/2885)
* [Miniature WiFi (802.11b/g/n) Module](https://www.adafruit.com/products/814)
* [Adafruit Si7021 Temperature & Humidity Sensor Breakout Board](https://www.adafruit.com/product/3251)
* [RGB backlight negative LCD 20x4](https://www.adafruit.com/products/498)
* [Adafruit Perma-Proto HAT for Pi Mini Kit](https://www.adafruit.com/products/2310)
* [16mm Illuminated Pushbutton](https://www.adafruit.com/products/1477)
* [Panel Mount 10K potentiometer](https://www.adafruit.com/products/562)
* [Potentiometer Knob](https://www.adafruit.com/products/2048)

![Home Assistant Temperature Monitor Fritzing](./home-assistant-temperature-monitor-fritzing.png?raw=true "Home Assistant Temperature Monitor Fritzing")

## Installation

* Install [smbus](https://pypi.python.org/pypi/smbus-cffi/0.5.1)
* Install [paho-mqtt](https://pypi.python.org/pypi/paho-mqtt)
* Install [Adafruit_Python_CharLCD](https://github.com/adafruit/Adafruit_Python_CharLCD)
* Install [Adafruit_Python_GPIO](https://github.com/adafruit/Adafruit_Python_GPIO)
* Clone this repo to `/home/pi`
* `cd home-assistant-temperature-monitor`
* `cp config-sample.json config.json`
* Edit `config.json` to set all of the options. Change `HOSTNAME` to whatever you want to use as a name and make sure your HA config also matches.
* Get [iOS](https://home-assistant.io/docs/ecosystem/ios/) (or [other notify component](https://home-assistant.io/components/notify/)) and [Dark Sky](https://home-assistant.io/components/sensor.darksky/) working in Home Assistant
* Configure Home Assistant. Here's an example of some `configuration.yaml` settings:

```
homeassistant:
  # You should have a bunch of other
  # settings here in your config
  customize:
    - entity_id: sensor.garage_temperature
      icon: mdi:thermometer
    - entity_id: sensor.garage_humidity
      icon: mdi:water-percent
	- entity_id: switch.garage_temp_monitor
	  icon: mdi:eye
	  friendly_name: Temp Monitor
	  assumed_state: false

sensor:
  - platform: mqtt
    state_topic: 'garage/pi/temperature'
    name: 'Garage Temperature'
    unit_of_measurement: '°F'

  - platform: mqtt
    state_topic: 'garage/pi/humidity'
    name: 'Garage Humidity'
    unit_of_measurement: '%'

switch:
  platform: command_line
  switches:
    garage_temp_monitor:
    command_on: "echo 'Garage temp monitor'"

input_slider:
  garage_temp_desired:
    name: Desired Temperature
    initial: 50
    min: 40
    max: 60
    step: 1
    icon: mdi:target

group:
  garage:
    name: Garage
    control: hidden
    entities:
        - switch.garage_temp_monitor
        - sensor.garage_temperature
        - input_slider.garage_temp_desired
        - sensor.garage_humidity

automation:
	- alias: 'Garage temp reached desired temp'
	  trigger:
	    platform: mqtt
	    topic: 'garage/pi/temperature'
	  condition:
	    condition: and
	    conditions:
	      - condition: state
	        entity_id: switch.garage_temp_monitor
	        state: 'on'
	      - condition: template
	        value_template: '{{ states.sensor.garage_temperature.state >= states.input_slider.garage_temp_desired.state }}'
	  action:
	    - service: switch.turn_off
	      entity_id: switch.garage_temp_monitor

	- alias: 'Notify garage temp monitor turned off'
	  trigger:
	    platform: state
	    entity_id: switch.garage_temp_monitor
	    from: 'on'
	    to: 'off'
	  action:
	    service: notify.ios_IPHONENAME
	    data_template:
	      title: "Garage Monitor Turned OFF"
	      message: "Temperature in the garage is {{ states.sensor.garage_temperature.state }}°F"
```
* You probably want to [run this program as a service on your Raspberry Pi](http://www.diegoacuna.me/how-to-run-a-script-as-a-service-in-raspberry-pi-raspbian-jessie/).
