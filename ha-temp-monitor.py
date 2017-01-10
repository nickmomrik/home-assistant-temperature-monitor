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

# How often to update Home Assistant (in seconds)
frequency = 60

# Home Assistant
ha_ip                  = '192.168.2.149'
ha_humid_topic         = 'garage/pi/humidity'
ha_temp_topic          = 'garage/pi/temperature'
ha_monitor_topic       = 'garage/pi/temp-monitor'
import socket
topic_prefix           = 'pis/' + socket.gethostname() + '/'
ha_cpu_temp_topic      = topic_prefix + 'cpu-temp'
ha_cpu_use_topic       = topic_prefix + 'cpu-use'
ha_ram_use_topic       = topic_prefix + 'ram-use'
ha_uptime_topic        = topic_prefix + 'uptime'
ha_out_temp_entity_id  = 'sensor.dark_sky_temperature'
ha_out_humid_entity_id = 'sensor.dark_sky_humidity'

# END CONFIG
############

import math
import time
import os
import sys
import psutil
from datetime import datetime
from datetime import timedelta
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import requests
import smbus # https://github.com/ControlEverythingCommunity/SI7021
import RPi.GPIO as GPIO

# Setup
GPIO.setmode( GPIO.BCM )
GPIO.setup( button_pin, GPIO.IN )
GPIO.setup( led_pin, GPIO.OUT )
GPIO.output( led_pin, GPIO.LOW )
bus = smbus.SMBus( 1 )
lcd = LCD.Adafruit_RGBCharLCD( lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7,
							    lcd_columns, lcd_rows, lcd_red, lcd_green, lcd_blue,
							     enable_pwm = True )

# Some defaults
prev_rgb     = ( 1, 1, 1 )
monitoring   = False
monitor_def  = 'Monitor: OFF'
monitor_str  = monitor_def
switch       = 'OFF'
last_update  = time.time() - frequency
out_temp     = 0
out_humid    = 0
bus_delay    = 0.025

# Home Assistant
url = 'http://' + ha_ip + ':8123/api/states/'
with open( 'ha-password.txt', 'r' ) as f:
	password = f.readline().strip()
headers  = {'x-ha-access': password,
					 'content-type': 'application/json'}
client = mqtt.Client( "ha-client" )
client.connect( ha_ip )
client.loop_start()

# Create degree character
lcd.create_char( 1, [28,20,28,0,0,0,0,0] )

def convert_c_to_f( celcius ):
	return celcius * 1.8 + 32

def get_cpu_temperature():
	res = os.popen( 'vcgencmd measure_temp' ).readline()

	return int( convert_c_to_f( float( res.replace( "temp=", "" ).replace( "'C\n", "" ) ) ) )

# http://stackoverflow.com/a/20792531
def rgb_temp( min_temp, max_temp, temp ):
	if ( temp < min_temp ):
		minT = temp
	elif ( temp > max_temp ):
		maxT = temp

	min_temp = float( min_temp )
	max_temp = float( max_temp )
	ratio = 2 * ( temp - min_temp ) / ( max_temp - min_temp )
	b = int( max( 0, 255 * ( 1 - ratio ) ) )
	r = int( max( 0, 255 * ( ratio - 1 ) ) )
	g = 255 - b - r

	return r, g, b

def read_humidity():
	# 0x40(64) - SI7021 address
	# 0xF5(245) - Relative Humidity NO HOLD master mode
	bus.write_byte( 0x40, 0xF5 )
	time.sleep( bus_delay )
	data0 = bus.read_byte( 0x40 )
	data1 = bus.read_byte( 0x40 )
	time.sleep( bus_delay )

	return int( ( data0 * 256 + data1 ) * 125 / 65536.0 - 6 )

def read_temperature():
	# 0x40(64) - SI7021 address
	# 0xF3(243) - Temperature NO HOLD master mode
	bus.write_byte( 0x40, 0xF3 )
	time.sleep( bus_delay )
	data0 = bus.read_byte( 0x40 )
	data1 = bus.read_byte( 0x40 )
	time.sleep( bus_delay )

	return int( convert_c_to_f( ( data0 * 256 + data1 ) * 175.72 / 65536.0 - 46.85 ) )

def get_home_assistant_state( entity_id, old_value ):
	ret = old_value
	try:
		response = requests.get( url + entity_id, headers = headers )
		if ( 200 == response.status_code ):
			value = response.json()['state']
			if ( value and 'unknown' != value ):
				try:
					converted = int( round( float( value ) ) )
					ret = converted
				except ValueError as e:
					print e, response.json()
	except requests.exceptions.RequestException as e:
		print e

	return ret

def reset_monitor():
	global monitoring, monitor_str, switch, last_update, update_lcd, led_pin
	monitoring  = False
	monitor_str = monitor_def
	switch      = 'OFF'
	last_update = 0
	update_lcd  = True
	GPIO.output( led_pin, GPIO.LOW )

def get_uptime():
	with open( '/proc/uptime', 'r' ) as f:
		uptime_seconds = float( f.readline().split()[0] )

		return str( timedelta( seconds = uptime_seconds ) )


while True:
	update_lcd = False

	humid = read_humidity()
	temp  = read_temperature()

	if ( GPIO.input( button_pin ) == False):
		if ( monitoring ):
			reset_monitor()
		else:
			monitoring  = True
			monitor_str = '@ ' + datetime.now().strftime('%H:%M') + ': {0:3}\x01 {1:2}%'.format(temp, humid)
			switch      = 'ON'
			last_update = 0
			update_lcd  = True
			GPIO.output( led_pin, GPIO.HIGH )

	now = time.time();
	if ( now > last_update + frequency ):
		last_update = now
		update_lcd  = True

		if ( monitoring and temp >= desired_temp ):
			reset_monitor()

		client.publish( ha_humid_topic, humid )
		client.publish( ha_temp_topic, temp )
		client.publish( ha_monitor_topic, switch )
		client.publish( ha_cpu_temp_topic, get_cpu_temperature() )
		client.publish( ha_cpu_use_topic, psutil.cpu_percent() )
		client.publish( ha_ram_use_topic, psutil.virtual_memory().percent )
		client.publish( ha_uptime_topic, get_uptime() )

		out_temp  = get_home_assistant_state( ha_out_temp_entity_id, out_temp )
		out_humid = get_home_assistant_state( ha_out_humid_entity_id, out_humid )

	if ( update_lcd ):
		rgb = rgb_temp( low_temp, high_temp, temp )
		if ( rgb[0] != prev_rgb[0] or rgb[1] != prev_rgb[1] or rgb[2] != prev_rgb[2] ):
			lcd.set_color( rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0 )
			prev_rgb = rgb

		lcd.set_cursor( 0, 0 )
		lcd.message( datetime.now().strftime( '%H:%M --- %a %b %d' ) + '\nOutside: {0:3}\x01 {1:2}%\n Inside: {2:3}\x01 {3:2}%\n'.format( out_temp, out_humid, temp, humid ) + monitor_str.ljust( 20 ) )

	time.sleep( 1 )
