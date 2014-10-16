#!/usr/bin/python

import serial
import time
import json
import mosquitto
import sys
import logging
import array
import math

logger = logging.getLogger('publisher')
def twos_comp(val, bits):
    """compute the 2's compliment of int value val"""
    if( (val&(1<<(bits-1))) != 0 ):
        val = val - (1<<bits)
    return val
    
def on_connect(mosq, obj, rc):
    if rc == 0:
        logger.info("mosquitto: Connected successfully")
        return
# Handle the error conditions
    if rc == 1:
        logger.error("mosquitto: unacceptable protocol version\n")
    elif rc == 2:
        logger.error("mosquitto: identifier rejected")
    elif rc == 3:
        logger.error("mosquitto: server winter.ceit.uq.edu.au unavailable")
    elif rc == 4:
        logger.error("mosquitto: bad user name or password")
    else:
        logger.error("mosquitto: not authorized")
# Go no further with this program
    sys.exit(1)

def main():
    DEVICE_ID = "1"

    datapacket = ""
    rc = 0
    mqttc = mosquitto.Mosquitto()

    mqttc.on_connect = on_connect

    try:
        mqttc.connect("winter.ceit.uq.edu.au", 1883, 60)
    except:
        logger.error('Cannot connect to MQTT server')
        sys.exit(1)

        
    while mqttc.loop(0.001) == 0:
        try:
            line = sys.stdin.readline()
            if "  A7 " in line: 
                strippedline = line.replace(" ", "")[:-1]
                hex_data = strippedline.decode("hex")
                array.array('B', hex_data)
                hex_arr = map(ord, hex_data);
                
                x = twos_comp(hex_arr[1] + (hex_arr[2] << 8), 16)
                y = twos_comp(hex_arr[3] + (hex_arr[4] << 8), 16)
                z = twos_comp(hex_arr[5] + (hex_arr[6] << 8), 16)
                
                XMAX = 160
                XMIN = -470
                YMAX = 590
                YMIN = 0
                
                mag_x_scale = 1.0/(XMAX - XMIN)
                mag_y_scale = 1.0/(YMAX - YMIN)
                x_avg = (XMAX + XMIN)/2.0
                y_avg = (XMAX + XMIN)/2.0
                
                heading = math.atan2((-y-y_avg)*mag_y_scale, (x-x_avg)*mag_x_scale)
                
                if (heading < 0):
                    heading = heading + math.pi * 2
                headingDegrees = math.degrees(heading)
                
                print "x=" + str(x) + ",y=" + str(y) + ",z=" + str(z) + ",heading=" + str(headingDegrees)
                
                mqttc.publish("/beacons/heading", str(headingDegrees), 0)
                
        except KeyboardInterrupt:
            logger.info('Program closed via keyboard')
            sys.exit(0)

main()



