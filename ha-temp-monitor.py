#!/usr/bin/python

import math
import time
import os
import sys
import json
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import requests
import smbus
import RPi.GPIO as GPIO
from datetime import datetime, timedelta

# Setup
with open( "/home/pi/home-assistant-temperature-monitor/config.json" ) as json_file:
    config = json.load( json_file )

GPIO.setmode( GPIO.BCM )
GPIO.setup( config['button_pin'], GPIO.IN )
GPIO.setup( config['led_pin'], GPIO.OUT )
GPIO.output( config['led_pin'], GPIO.LOW )
bus = smbus.SMBus( 1 )
lcd = LCD.Adafruit_RGBCharLCD( config['lcd_rs_pin'], config['lcd_en_pin'],
	config['lcd_d4_pin'], config['lcd_d5_pin'], config['lcd_d6_pin'], config['lcd_d7_pin'],
	config['lcd_columns'], config['lcd_rows'],
	config['lcd_red_pin'], config['lcd_green_pin'], config['lcd_blue_pin'],
	enable_pwm = True )

# Some defaults
prev_rgb     = ( 1, 1, 1 )
switch       = 'off'
last_update  = 0
desired_temp = 0
out_temp     = 0
out_humid    = 0
bus_delay    = 0.025

# Home Assistant
url = config['ha_url'] + '/api/states/'
headers = {'x-ha-access': config['ha_password'],
	'content-type': 'application/json'}
mqtt.Client.connected_flag = False
mqtt.Client.bad_connection_flag = False
mqtt.Client.retry_count = 0

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

def get_home_assistant_value( entity_id, old_value ):
	state = get_home_assistant_state( entity_id )
	if ( state is not None and 'state' in state and state['state'] and 'unknown' != state['state'] ):
		ret = state['state']
	else:
		ret = old_value

	return ret

def get_home_assistant_state( entity_id ):
	ret = None
	try:
		response = requests.get( url + entity_id, headers = headers )
		if ( 200 == response.status_code and 'unknown' != response.json()['state'] ):
			ret = response.json()
	except requests.exceptions.RequestException as e:
		print e

	return ret

def set_home_assistant_switch( entity_id, switch ):
	if ( 'on' != switch ):
		switch = 'off'

	new_state = {
		'state': switch,
		'attributes': {
			'icon': '',
			'friendly_name': ''
		}
	}

	# Otherwise Home Assistant resets these values!
	state = get_home_assistant_state( entity_id )
	if ( state['attributes']['icon'] ):
		new_state['attributes']['icon'] = state['attributes']['icon']
	if ( state['attributes']['friendly_name'] ):
		new_state['attributes']['friendly_name'] = state['attributes']['friendly_name']

	try:
		data = json.dumps( new_state )
		requests.post( url + entity_id, data, headers = headers )
	except requests.exceptions.RequestException as e:
		print e

def switch_change( switch, push ):
	global config

	if ( 'on' == switch ):
		GPIO.output( config['led_pin'], GPIO.HIGH )
	else:
		GPIO.output( config['led_pin'], GPIO.LOW )

	if ( True == push ):
		set_home_assistant_switch( config['ha_monitor_entity_id'], switch )

def on_disconnect( client, userdata, flags, rc = 0 ):
	client.connected_flag = False

def on_connect( client, userdata, flags, rc ):
	if ( 0 == rc ):
		client.connected_flag = True
	else:
		client.bad_connection_flag = True

def update_home_assistant_sensors( humid, temp ):
	#http://www.steves-internet-guide.com/client-connections-python-mqtt/

	global last_update, desired_temp, out_temp, out_humid, switch, config, prev_rgb

	client = mqtt.Client( 'ha-client' )
	client.on_connect = on_connect
	client.on_disconnect = on_disconnect

	run_main = False
	run_flag = True
	while ( run_flag ):
		while ( False == client.connected_flag and client.retry_count < 3 ):
			count = 0
			run_main = False
			try:
				client.connect( config['ha_ip'] )
				break
			except:
				client.retry_count += 1
				if ( client.retry_count > 5 ):
					run_flag = False

			time.sleep( 3 )

		if ( run_main ):
			run_flag = False

			client.publish( config['ha_humid_topic'], humid )
			client.publish( config['ha_temp_topic'], temp )

			switch       = get_home_assistant_value( config['ha_monitor_entity_id'], switch )
			desired_temp = int( round( float( get_home_assistant_value( config['ha_desired_entity_id'], desired_temp ) ) ) )
			out_temp     = int( round( float( get_home_assistant_value( config['ha_out_temp_entity_id'], out_temp ) ) ) )
			out_humid    = int( round( float( get_home_assistant_value( config['ha_out_humid_entity_id'], out_humid ) ) ) )

			switch_change( switch, False )

			rgb = rgb_temp( config['low_temp_f'], config['high_temp_f'], temp )
			if ( rgb[0] != prev_rgb[0] or rgb[1] != prev_rgb[1] or rgb[2] != prev_rgb[2] ):
				lcd.set_color( rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0 )
				prev_rgb = rgb

			lcd.set_cursor( 0, 0 )
			lcd.message( datetime.now().strftime( '%H:%M --- %a %b %d' ) + '\nOutside: {0:3}\x01 {1:2}%\n Inside: {2:3}\x01 {3:2}%\n'.format( out_temp, out_humid, temp, humid ) + 'Desired: {0:3}\x01'.format( desired_temp ).ljust( config['lcd_columns'] ) )

			last_update = time.time()
		else:
			client.loop_start()
	        while ( True ):
				if ( client.connected_flag ):
					client.retry_count = 0
					run_main = True
					break
				elif ( count > 6 or client.bad_connection_flag ):
					client.loop_stop()
					client.retry_count += 1
					if ( client.retry_count > 5 ):
						run_flag = False
						break
				else:
					time.sleep( 3 )
					count += 1

	client.disconnect()
	client.loop_stop()

while ( True ):
	update_lcd = False

	humid = int( read_humidity() )
	temp  = int( read_temperature() )

	if ( False == GPIO.input( config['button_pin'] ) ):
		if ( 'on' == switch ):
			switch = 'off'
		else:
			switch = 'on'

		switch_change( switch, True )
		last_update = 0

	if ( time.time() > ( last_update + config['update_frequency'] ) ):
		update_home_assistant_sensors( humid, temp )

	time.sleep( 1 )
