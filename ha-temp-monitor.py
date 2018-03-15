#!/usr/bin/python

import math
import time
import os
import sys
import json
import Adafruit_CharLCD as LCD
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import smbus
import RPi.GPIO as GPIO
from datetime import datetime, timedelta

# Setup
with open( "/home/pi/home-assistant-temperature-monitor/config.json" ) as json_file :
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
status       = 'off'
target_temp  = 0
temp         = 0
out_temp     = 0
humid        = 0
out_humid    = 0
bus_delay    = 0.025
last_update  = 0

# Low Pass Filters
# https://www.norwegiancreations.com/2015/10/tutorial-potentiometers-with-arduino-and-filtering/
temp_alpha = 0.1
humid_alpha = 0.1

# Create degree character
lcd.create_char( 1, [28,20,28,0,0,0,0,0] )

def convert_c_to_f( celcius ) :
	return celcius * 1.8 + 32

# http://stackoverflow.com/a/20792531
def rgb_temp( min_temp, max_temp, temp ) :
	if ( temp < min_temp ) :
		min_temp = temp
	elif ( temp > max_temp ) :
		max_temp = temp

	min_temp = float( min_temp )
	max_temp = float( max_temp )
	ratio = 2 * ( temp - min_temp ) / ( max_temp - min_temp )
	b = int( max( 0, 255 * ( 1 - ratio ) ) )
	r = int( max( 0, 255 * ( ratio - 1 ) ) )
	g = 255 - b - r

	return r, g, b

def get_si7021_data( mode ) :
	# 0x40(64) - SI7021 address
	bus.write_byte( 0x40, mode )
	time.sleep( bus_delay )
	data0 = bus.read_byte( 0x40 )
	data1 = bus.read_byte( 0x40 )
	time.sleep( bus_delay )

	return data0 * 256 + data1

def read_humidity() :
	# 0xF5(245) - Relative Humidity NO HOLD master mode
	return get_si7021_data( 0xF5 ) * 125 / 65536.0 - 6

def read_temperature() :
	# 0xF3(243) - Temperature NO HOLD master mode
	return convert_c_to_f( get_si7021_data( 0xF3 ) * 175.72 / 65536.0 - 46.85 )

def on_connect( client, userdata, flags, rc ) :
	if ( 0 == rc ) :
		client.connected_flag = True
		client.subscribe( [( config['target_temp_topic'], 1 ), ( config['outdoor_temp_topic'], 1 ), ( config['outdoor_humid_topic'], 1)] )

def on_message( client, userdata, msg ) :
	global target_temp, out_temp, out_humid

	value = int( round( float( msg.payload.decode( "utf-8" ) ) ) )
	if ( config['target_temp_topic'] == msg.topic ) :
		target_temp = value
	elif ( config['outdoor_temp_topic'] == msg.topic ) :
		out_temp = value
	elif ( config['outdoor_humid_topic'] == msg.topic ) :
		out_humid = value

def button_is_pressed() :
	return False == GPIO.input( config['button_pin'] )

client = mqtt.Client()
client.connected_flag = False
client.on_connect = on_connect
client.on_message = on_message
client.loop_start()
client.connect( config['ip'] )
while ( not client.connected_flag ) :
	time.sleep( 1 )

try :
	humid = read_humidity()
	client.publish( config['humid_topic'], int( humid ) )
	temp = read_temperature()
	client.publish( config['temp_topic'], int( temp ) )

	loops = 0;
	max_loops = 300;
	while ( True ) :
		last_humid = int( humid )
		humid = ( humid_alpha * read_humidity() ) + ( ( 1 - humid_alpha ) * humid );
		if ( last_humid != int( humid ) or loops == max_loops ) :
			client.publish( config['humid_topic'], int( humid ) )

		last_temp = int( temp )
		temp = ( temp_alpha * read_temperature() ) + ( ( 1 - temp_alpha ) * temp );
		if ( last_temp != int( temp ) or loops == int( 0.3 * max_loops ) ) :
			client.publish( config['temp_topic'], int( temp ) )

		if ( button_is_pressed() or loops == int( 0.6 * max_loops ) ) :
			if ( button_is_pressed() ) :
				if ( 'on' == status ) :
					status = 'off'
					GPIO.output( config['led_pin'], GPIO.LOW )
				else :
					status = 'on'
					GPIO.output( config['led_pin'], GPIO.HIGH )

				while ( button_is_pressed ) :
					time.sleep( 1 )

			client.publish( config['status_topic'], status, 2 )

		rgb = rgb_temp( config['low_temp_f'], config['high_temp_f'], temp )
		if ( rgb[0] != prev_rgb[0] or rgb[1] != prev_rgb[1] or rgb[2] != prev_rgb[2] ) :
			lcd.set_color( rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0 )
			prev_rgb = rgb

		lcd.set_cursor( 0, 0 )
		lcd.message( datetime.now().strftime( '%H:%M --- %a %b %d' ).upper() + '\nOUTSIDE: {0:3}\x01 {1:2}%\n INSIDE: {2:3}\x01 {3:2}%\n'.format( out_temp, out_humid, int( temp ), int( humid ) ) + ' TARGET: {0:3}\x01'.format( target_temp ).ljust( config['lcd_columns'] ) )

		loops = 0 if ( max_loops == loops ) else loops + 1

		time.sleep( 2 )
except KeyboardInterrupt:
    client.disconnect()
    client.loop_stop()
