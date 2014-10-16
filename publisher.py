#!/usr/bin/python

import serial
import time
import json
import mosquitto
import sys
import logging
import os

logger = logging.getLogger('publisher')

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

def process_line(line):
    pass



def main():
    DEVICE_ID = os.environ['BASE_ID']

    datapacket = ""
    rc = 0
    mqttc = mosquitto.Mosquitto()

    mqttc.on_connect = on_connect
#    mqttc.on_publish = on_publish
    
    try:
        mqttc.connect("winter.ceit.uq.edu.au", 1883, 60)
    except:
        logger.error('Cannot connect to MQTT server')
        sys.exit(1)
        
    while mqttc.loop(0.001) == 0:
        try:
            line = sys.stdin.readline()
            if line.startswith('>'): 
                mqttc.publish("/beacons/base/" + DEVICE_ID, datapacket, 0)
                datapacket = ""
            datapacket = datapacket + line
        except KeyboardInterrupt:
            logger.info('Program closed via keyboard')
            sys.exit(0)
        except:
            pass

main()


