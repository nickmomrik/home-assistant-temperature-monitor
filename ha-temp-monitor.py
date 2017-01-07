#!/usr/bin/python

########
# CONFIG

# Where are the button and status LED connected?
buttonPin = 19
ledPin    = 21

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
desiredTemp = 45

# High/low used for LCD color calculations
highTemp = 80
lowTemp  = 32

# END CONFIG
############

import math
import time
import os
import sys
import socket
from datetime import datetime
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import smbus # https://github.com/ControlEverythingCommunity/SI7021
import RPi.GPIO as GPIO

# Setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(buttonPin, GPIO.IN)
GPIO.setup(ledPin, GPIO.OUT)
GPIO.output(ledPin, GPIO.LOW)
bus = smbus.SMBus(1)
lcd = LCD.Adafruit_RGBCharLCD(lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7,
                              lcd_columns, lcd_rows, lcd_red, lcd_green, lcd_blue,
                              enable_pwm=True)

# Some defaults
prevRGB    = (1, 1, 1)
monitoring = False
monitorStr = ''
switch     = 'OFF'
updateSecs = 30
loop       = 0

# Create degree character
lcd.create_char(1, [28,20,28,0,0,0,0,0])

def convertCtoF(celcius):
  return celcius * 1.8 + 32

def getCPUtemperature():
  res = os.popen('vcgencmd measure_temp').readline()
  return int(convertCtoF(float(res.replace("temp=", "").replace("'C\n",""))))

# http://stackoverflow.com/a/20792531
def rgbTemp(minT, maxT, temp):
  if (temp < minT):
    minT = temp
  elif (temp > maxT):
    maxT = temp

  minT = float(minT)
  maxT = float(maxT)
  ratio = 2 * (temp - minT) / (maxT - minT)
  b = int(max(0, 255*(1 - ratio)))
  r = int(max(0, 255*(ratio - 1)))
  g = 255 - b - r
  return r, g, b

def readHumidity():
  # 0x40(64) - SI7021 address
  # 0xF5(245) - Relative Humidity NO HOLD master mode
  bus.write_byte(0x40, 0xF5)
  time.sleep(0.05)
  data0 = bus.read_byte(0x40)
  data1 = bus.read_byte(0x40)
  time.sleep(0.05)

  return int(((data0 * 256 + data1) * 125 / 65536.0) - 6)

def readTemperature():
  # 0x40(64) - SI7021 address
  # 0xF3(243) - Temperature NO HOLD master mode
  bus.write_byte(0x40, 0xF3)
  time.sleep(0.05)
  data0 = bus.read_byte(0x40)
  data1 = bus.read_byte(0x40)
  time.sleep(0.05)

  return int(convertCtoF(((data0 * 256 + data1) * 175.72 / 65536.0) - 46.85))


# Output data to screen
while True:
  humid = readHumidity()
  temp  = readTemperature()

  if (monitoring):
    if (temp >= desiredTemp or GPIO.input(buttonPin) == False):
      monitoring = False
      monitorStr = ' '*20 # blank out the line
      switch = 'OFF'
      loop = 0
      GPIO.output(ledPin, GPIO.LOW)
  elif (GPIO.input(buttonPin) == False):
    monitoring = True
    monitorStr = '@ ' + datetime.now().strftime('%H:%M') + ': {0:3}\x01 {1:2}%'.format(temp, humid)
    switch = 'ON'
    loop = 0
    GPIO.output(ledPin, GPIO.HIGH)

  if (0 == loop):
    msgs = [('garage/pi/humidity', humid, 0, True),
            ('garage/pi/temperature', temp, 0, True),
            ('garage/pi/temp-monitor', switch, 0, True),
            ('pis/' + socket.gethostname() + '/cpu-temp', getCPUtemperature(), 0, True)]
    publish.multiple(msgs, hostname='apple.local')

  if (loop >= updateSecs):
    loop = 0
  else:
    loop += 1

  rgb = rgbTemp(lowTemp, highTemp, temp)
  if (rgb[0] != prevRGB[0] or rgb[1] != prevRGB[1] or rgb[2] != prevRGB[2]):
    lcd.set_color(*rgb)
    prevRGB = rgb

  lcd.set_cursor(0, 0)
  lcd.message(datetime.now().strftime('%H:%M --- %a %b %d') + '\n\n     In: {0:3}\x01 {1:2}%\n'.format(temp, humid) + monitorStr)

  time.sleep(2)
