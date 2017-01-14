#!/usr/bin/python

import math
import time
import os
import sys
import json
from datetime import datetime
from datetime import timedelta
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import requests
import smbus
import RPi.GPIO as GPIO

# Setup
with open( "/home/pi/home-assistant-temperature-monitor/config.json" ) as json_file:
    j = json.load( json_file )

GPIO.setmode( GPIO.BCM )
GPIO.setup( j['button_pin'], GPIO.IN )
GPIO.setup( j['led_pin'], GPIO.OUT )
GPIO.output( j['led_pin'], GPIO.LOW )
bus = smbus.SMBus( 1 )
lcd = LCD.Adafruit_RGBCharLCD( j['lcd_rs_pin'], j['lcd_en_pin'],
								j['lcd_d4_pin'], j['lcd_d5_pin'], j['lcd_d6_pin'], j['lcd_d7_pin'],
								j['lcd_columns'], j['lcd_rows'],
								j['lcd_red_pin'], j['lcd_green_pin'], j['lcd_blue_pin'],
								enable_pwm = True )

# Some defaults
prev_rgb     = ( 1, 1, 1 )
monitoring   = False
monitor_def  = 'Monitor:  OFF'
monitor_str  = monitor_def
switch       = 'OFF'
last_update  = 0
out_temp     = 0
out_humid    = 0
bus_delay    = 0.025

# Home Assistant
url = j['ha_url'] + '/api/states/'
headers = {'x-ha-access': j['ha_password'],
			'content-type': 'application/json'}
client = mqtt.Client( "ha-client" )
client.connect( j['ha_ip'] )
client.loop_start()

# Create degree character
lcd.create_char( 1, [28,20,28,0,0,0,0,0] )

def convert_c_to_f( celcius ):
	return celcius * 1.8 + 32

# http://stackoverflow.com/a/20792531
def rgb_temp( min_temp, max_temp, temp ):
	if ( temp < min_temp ):
		min_temp = temp
	elif ( temp > max_temp ):
		max_temp = temp

	min_temp = float( min_temp )
	max_temp = float( max_temp )
	ratio = 2 * ( temp - min_temp ) / ( max_temp - min_temp )
	b = int( max( 0, 255 * ( 1 - ratio ) ) )
	r = int( max( 0, 255 * ( ratio - 1 ) ) )
	g = 255 - b - r

	return r, g, b

def get_si7021_data( mode ):
	# 0x40(64) - SI7021 address
	bus.write_byte( 0x40, mode )
	time.sleep( bus_delay )
	data0 = bus.read_byte( 0x40 )
	data1 = bus.read_byte( 0x40 )
	time.sleep( bus_delay )

	return data0 * 256 + data1

def read_humidity():
	# 0xF5(245) - Relative Humidity NO HOLD master mode
	return get_si7021_data( 0xF5 ) * 125 / 65536.0 - 6

def read_temperature():
	# 0xF3(243) - Temperature NO HOLD master mode
	return convert_c_to_f( get_si7021_data( 0xF3 ) * 175.72 / 65536.0 - 46.85 )

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
	GPIO.output( j['led_pin'], GPIO.LOW )


while True:
	update_lcd = False

	humid = int( read_humidity() )
	temp  = int( read_temperature() )

	if ( GPIO.input( j['button_pin'] ) == False ):
		if ( monitoring ):
			reset_monitor()
		else:
			monitoring  = True
			monitor_str = '@ ' + datetime.now().strftime( '%H:%M' ) + ': {0:3}\x01 {1:2}%'.format( temp, humid )
			switch      = 'ON'
			last_update = 0
			update_lcd  = True
			GPIO.output( j['led_pin'], GPIO.HIGH )

	now = time.time();
	if ( now > last_update + j['update_frequency'] ):
		last_update = now
		update_lcd  = True

		if ( monitoring and temp >= j['desired_temp_f'] ):
			reset_monitor()

		client.publish( j['ha_humid_topic'], humid )
		client.publish( j['ha_temp_topic'], temp )
		client.publish( j['ha_monitor_topic'], switch )

		out_temp  = get_home_assistant_state( j['ha_out_temp_entity_id'], out_temp )
		out_humid = get_home_assistant_state( j['ha_out_humid_entity_id'], out_humid )

	if ( update_lcd ):
		rgb = rgb_temp( j['low_temp_f'], j['high_temp_f'], temp )
		if ( rgb[0] != prev_rgb[0] or rgb[1] != prev_rgb[1] or rgb[2] != prev_rgb[2] ):
			lcd.set_color( rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0 )
			prev_rgb = rgb

		lcd.set_cursor( 0, 0 )
		lcd.message( datetime.now().strftime( '%H:%M --- %a %b %d' ) + '\nOutside: {0:3}\x01 {1:2}%\n Inside: {2:3}\x01 {3:2}%\n'.format( out_temp, out_humid, temp, humid ) + monitor_str.ljust( j['lcd_columns'] ) )

	time.sleep( 1 )
