#!/usr/bin/python

########
# CONFIG

# Where are the button and status LED connected?
button_pin = 19
led_pin    = 21

# LCD configuration
lcd_rs = 27
lcd_en = 22
lcd_d4 = 25
lcd_d5 = 24
lcd_d6 = 23
lcd_d7 = 18

lcd_red   = 4
lcd_green = 17
lcd_blue  = 7

lcd_columns = 20
lcd_rows    = 4

# Acceptable temperature when monitor will stop
desired_temp = 45

# High/low used for LCD color calculations
high_temp = 80
low_temp  = 32

# END CONFIG
############

import math
import time
import os
import sys
import socket
import psutil
import json
from datetime import datetime
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from requests import get
import smbus # https://github.com/ControlEverythingCommunity/SI7021
import RPi.GPIO as GPIO

# Setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(button_pin, GPIO.IN)
GPIO.setup(led_pin, GPIO.OUT)
GPIO.output(led_pin, GPIO.LOW)
bus = smbus.SMBus(1)
lcd = LCD.Adafruit_RGBCharLCD(lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7,
                              lcd_columns, lcd_rows, lcd_red, lcd_green, lcd_blue,
                              enable_pwm=True)

# Some defaults
prev_rgb     = (1, 1, 1)
monitoring   = False
monitor_def  = 'Monitor: hold button'
monitor_str  = monitor_def
switch       = 'OFF'
update_loops = 30
loop         = 0
out_temp     = 0
out_humid    = 0
bus_delay    = 0.025

# Home Assistant
ha_ip = '192.168.2.149'
url = 'http://' + ha_ip + ':8123/api/states/'
with open('ha-password.txt', 'r') as f:
  password = f.readline().strip()
headers  = {'x-ha-access': password,
           'content-type': 'application/json'}
client = mqtt.Client("ha-client")
client.connect(ha_ip)
client.loop_start()

# Create degree character
lcd.create_char(1, [28,20,28,0,0,0,0,0])

def convert_c_to_f(celcius):
  return celcius * 1.8 + 32

def get_cpu_temperature():
  res = os.popen('vcgencmd measure_temp').readline()
  return int(convert_c_to_f(float(res.replace("temp=", "").replace("'C\n",""))))

# http://stackoverflow.com/a/20792531
def rgb_temp(min_temp, max_temp, temp):
  if (temp < min_temp):
    minT = temp
  elif (temp > max_temp):
    maxT = temp

  min_temp = float(min_temp)
  max_temp = float(max_temp)
  ratio = 2 * (temp - min_temp) / (max_temp - min_temp)
  b = int(max(0, 255 * (1 - ratio)))
  r = int(max(0, 255 * (ratio - 1)))
  g = 255 - b - r
  return r, g, b

def read_humidity():
  # 0x40(64) - SI7021 address
  # 0xF5(245) - Relative Humidity NO HOLD master mode
  bus.write_byte(0x40, 0xF5)
  time.sleep(bus_delay)
  data0 = bus.read_byte(0x40)
  data1 = bus.read_byte(0x40)
  time.sleep(bus_delay)

  return int((data0 * 256 + data1) * 125 / 65536.0 - 6)

def read_temperature():
  # 0x40(64) - SI7021 address
  # 0xF3(243) - Temperature NO HOLD master mode
  bus.write_byte(0x40, 0xF3)
  time.sleep(bus_delay)
  data0 = bus.read_byte(0x40)
  data1 = bus.read_byte(0x40)
  time.sleep(bus_delay)

  return int(convert_c_to_f((data0 * 256 + data1) * 175.72 / 65536.0 - 46.85))

def get_home_assistant_state(entity_id):
  response = get(url + entity_id, headers=headers)
  return int(round(float(json.loads(response.text)['state'])))


while True:
  humid = read_humidity()
  temp  = read_temperature()

  if (monitoring):
    if (temp >= desired_temp or GPIO.input(button_pin) == False):
      monitoring = False
      monitor_str = monitor_def
      switch = 'OFF'
      loop = 0
      GPIO.output(led_pin, GPIO.LOW)
  elif (GPIO.input(button_pin) == False):
    monitoring = True
    monitor_str = '@ ' + datetime.now().strftime('%H:%M') + ': {0:3}\x01 {1:2}%'.format(temp, humid)
    switch = 'ON'
    loop = 0
    GPIO.output(led_pin, GPIO.HIGH)

  if (0 == loop):
    client.publish('garage/pi/humidity', humid)
    client.publish('garage/pi/temperature', temp)
    client.publish('garage/pi/temp-monitor', switch)
    client.publish('pis/' + socket.gethostname() + '/cpu-temp', get_cpu_temperature())
    client.publish('pis/' + socket.gethostname() + '/cpu-use', psutil.cpu_percent())
    client.publish('pis/' + socket.gethostname() + '/ram-use', psutil.virtual_memory().percent)

    out_temp  = get_home_assistant_state('sensor.dark_sky_temperature')
    out_humid = get_home_assistant_state('sensor.dark_sky_humidity')

  if (loop >= update_loops):
    loop = 0
  else:
    loop += 1

  rgb = rgb_temp(low_temp, high_temp, temp)
  if (rgb[0] != prev_rgb[0] or rgb[1] != prev_rgb[1] or rgb[2] != prev_rgb[2]):
    lcd.set_color(*rgb)
    prev_rgb = rgb

  lcd.set_cursor(0, 0)
  lcd.message(datetime.now().strftime('%H:%M --- %a %b %d') + '\nOutside: {0:3}\x01 {1:2}%\n Inside: {2:3}\x01 {3:2}%\n'.format(out_temp, out_humid, temp, humid) + monitor_str.ljust(20))

  time.sleep(2)
