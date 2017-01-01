#!/usr/bin/python
import time
from datetime import datetime

import Adafruit_CharLCD as LCD

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

setting = False
desiredTemp = 0
startTemp = 0

colorTemps = [[0]*3 for i in range(10)]
colorTemps[9] = [255, 0, 16]
colorTemps[8] = [255, 50, 0]
colorTemps[7] = [255, 110, 0]
colorTemps[6] = [255, 170, 0]
colorTemps[5] = [255, 230, 0]
colorTemps[4] = [138, 255, 0]
colorTemps[3] = [0, 255, 92]
colorTemps[2] = [0, 212, 255]
colorTemps[1] = [0, 116, 255]
colorTemps[0] = [0, 18, 255]

defaultRed = currRed = 1.0
defaultGreen = currGreen = 1.0
defaultBlue = currBlue = 1.0

# Create degree character
lcd.create_char(1, [28,20,28,0,0,0,0,0])

lcd.set_color(defaultRed, defaultGreen, defaultBlue)

# Output data to screen
while True:
    if (setting == False):
        incTemp = 0;

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

    if (GPIO.input(26) == False):
        delay = 0.1
        incTemp += 1
        setting = True
        startTemp = inTemp
        desiredTemp = startTemp + incTemp
    else:
        delay = 5.0
        setting = False

        if (desiredTemp == 0):
            desiredTemp = inTemp

    if (startTemp):
	color = int((inTemp - startTemp) / (desiredTemp - startTemp) * 10)
	if (color > 9):
            color = 9
        elif (color < 0):
            color = 0
        red = colorTemps[color][0] / 255.0
        green = colorTemps[color][1] / 255.0
        blue = colorTemps[color][2] / 255.0
    else:
        red = defaultRed
        green = defaultGreen
        blue = defaultBlue

    if (red != currRed or green != currGreen or blue != currBlue):
        lcd.set_color(red, green, blue)
        currRed = red
        currGreen = green
        currBlue = blue

    lcd.set_cursor(0, 0)
    dt = datetime.now().strftime('%H:%M     %a %b %d')
    lcd.message(dt + '\n    Out: {0:3}\x01 {1:3}%\n     In: {2:3}\x01 {3:3}%\nDesired: {4:3}\x01'.format(outTemp, outHumid, inTemp, inHumid, desiredTemp))

    time.sleep(delay)
