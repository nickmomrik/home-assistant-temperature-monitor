#!/usr/bin/python
import time
from datetime import datetime

import Adafruit_CharLCD as LCD

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish

broker = '192.168.2.149'
state_topic = 'garage/pi/'
client = mqtt.Client("ha-client")
client.connect(broker)
client.loop_start()

# https://github.com/ControlEverythingCommunity/SI7021
import smbus

import RPi.GPIO as GPIO
 
GPIO.setmode(GPIO.BCM)

# Button
GPIO.setup(26, GPIO.IN)

# Raspberry Pi configuration:
lcd_rs = 27  # Change this to pin 21 on older revision Raspberry Pi's
lcd_en = 22
lcd_d4 = 25
lcd_d5 = 24
lcd_d6 = 23
lcd_d7 = 18
lcd_red   = 4
lcd_green = 17
lcd_blue  = 7  # Pin 7 is CE1

lcd_columns = 20
lcd_rows    = 4

# Initialize the LCD using the pins above.
lcd = LCD.Adafruit_RGBCharLCD(lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7,
                              lcd_columns, lcd_rows, lcd_red, lcd_green, lcd_blue,
                              enable_pwm=True)

# Get I2C bus
bus = smbus.SMBus(1)

watching = False
watchStr = ''
switch = 'OFF'
desiredTemp = 45
updateSecs = 30
loop = 0

defaultRed = 0.1
defaultGreen = 0.1
defaultBlue = 1.0

# Create degree character
lcd.create_char(1, [28,20,28,0,0,0,0,0])

lcd.set_color(defaultRed, defaultGreen, defaultBlue)

# Output data to screen
while True:
    # SI7021 address, 0x40(64)
    #               0xF5(245)       Select Relative Humidity NO HOLD master mode
    bus.write_byte(0x40, 0xF5)

    time.sleep(0.05)

    # SI7021 address, 0x40(64)
    # Read data back, 2 bytes, Humidity MSB first
    data0 = bus.read_byte(0x40)
    data1 = bus.read_byte(0x40)

    time.sleep(0.05)

    # Convert the data
    inHumid = int(((data0 * 256 + data1) * 125 / 65536.0) - 6)

    # SI7021 address, 0x40(64)
    #               0xF3(243)       Select temperature NO HOLD master mode
    bus.write_byte(0x40, 0xF3)

    time.sleep(0.05)

    # SI7021 address, 0x40(64)
    # Read data back, 2 bytes, Temperature MSB first
    data0 = bus.read_byte(0x40)
    data1 = bus.read_byte(0x40)

    # Convert the data
    cTemp = ((data0 * 256 + data1) * 175.72 / 65536.0) - 46.85
    inTemp = int(cTemp * 1.8 + 32)

    # Get from Home Assistant
    outTemp = int(0.0)
    outHumid = int(0.0)

    if (watching):
      if (inTemp >= desiredTemp or GPIO.input(26) == False):
        watching = False
        watchStr = ' '*20
        switch = 'OFF'
        loop = 0
    elif (GPIO.input(26) == False):
      watching = True
      watchStr = '@ ' + datetime.now().strftime('%H:%M') + ': {0:3}\x01 {1:2}%'.format(inTemp, inHumid)
      switch = 'ON'
      loop = 0

    if (0 == loop):
      client.publish(state_topic + 'humidity', inHumid)
      client.publish(state_topic + 'temperature', inTemp)
      client.publish(state_topic + 'temp-watch/set', switch)

    if (loop >= updateSecs):
      loop = 0
    else:
      loop += 1

    lcd.set_cursor(0, 0)
    lcd.message(datetime.now().strftime('%H:%M --- %a %b %d') + '\n    Out: {0:3}\x01 {1:2}%\n     In: {2:3}\x01 {3:2}%\n'.format(outTemp, outHumid, inTemp, inHumid) + watchStr)

    time.sleep(2)
