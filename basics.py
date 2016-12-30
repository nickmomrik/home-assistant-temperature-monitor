#!/usr/bin/python
import time

import Adafruit_CharLCD as LCD

# https://github.com/ControlEverythingCommunity/SI7021
import smbus

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
                              lcd_columns, lcd_rows, lcd_red, lcd_green, lcd_blue)

# Get I2C bus
bus = smbus.SMBus(1)

# SI7021 address, 0x40(64)
#               0xF5(245)       Select Relative Humidity NO HOLD master mode
bus.write_byte(0x40, 0xF5)

time.sleep(0.3)

# SI7021 address, 0x40(64)
# Read data back, 2 bytes, Humidity MSB first
data0 = bus.read_byte(0x40)
data1 = bus.read_byte(0x40)

# Convert the data
humidity = ((data0 * 256 + data1) * 125 / 65536.0) - 6

time.sleep(0.3)

# SI7021 address, 0x40(64)
#               0xF3(243)       Select temperature NO HOLD master mode
bus.write_byte(0x40, 0xF3)

time.sleep(0.3)

# SI7021 address, 0x40(64)
# Read data back, 2 bytes, Temperature MSB first
data0 = bus.read_byte(0x40)
data1 = bus.read_byte(0x40)

# Convert the data
cTemp = ((data0 * 256 + data1) * 175.72 / 65536.0) - 46.85
fTemp = cTemp * 1.8 + 32

# Output data to screen
lcd.set_color(1.0, 1.0, 1.0)
lcd.clear()
print "Relative Humidity is : %.2f %%" %humidity
print "Temperature in Celsius is : %.2f C" %cTemp
print "Temperature in Fahrenheit is : %.2f F" %fTemp

lcd.message('  Humidity: {0:0.1f}%\n\n   Celsius: {1:0.1f}\nFahrenheit: {2:0.1f}'.format(humidity, cTemp, fTemp))
