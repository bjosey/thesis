#!/usr/bin/python
import time
import json
import mosquitto
import sys
import logging
import os
import math
import array
from threading import Timer

accelTimeouts = {}
ACCEL_THRESHHOLD = 0.9
ACCEL_TIMEOUT = 120

def twos_comp(val, bits):
    """compute the 2's compliment of int value val"""
    if( (val&(1<<(bits-1))) != 0 ):
        val = val - (1<<bits)
    return val

#converts a string of the form "0x39 0x01 0x43 0xff 0x58 0x01"
#to an array of values
def str2hexArr(hexString):
    hexString = hexString.replace("0x", "")
    hexString = hexString.replace(" ", "")
    hexString = hexString.decode("hex")

    array.array('B', hexString)
    hex_arr = map(ord, hexString);
    return hex_arr

#takes raw magnet data in the form off "0x39 0x01 0x43 0xff 0x58 0x01"
def magnet2heading(mag_str):
    hex_arr = str2hexArr(mag_str)

    x = twos_comp(hex_arr[0] + (hex_arr[1] << 8), 16)
    y = twos_comp(hex_arr[2] + (hex_arr[3] << 8), 16)
    z = twos_comp(hex_arr[4] + (hex_arr[5] << 8), 16)

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

    #print "x=" + str(x) + ",y=" + str(y) + ",z=" + str(z) + ",heading=" + str(headingDegrees)
    return headingDegrees

def acc2magnitude(acc_str):
    hex_arr = str2hexArr(acc_str)
    #scale the acc reading according to acc datasheet
    acc_arr = [float((twos_comp(x, 8)) / (256.0/8.0)) for x in hex_arr]
    added = sum(x ** 2 for x in acc_arr)
    return math.sqrt(added)

def rssi2distance(rssi):
    return math.exp((1/271.0)*(-50.0*rssi - 3599.0))
    
class Chair:

    def __init__(self, bdaddr):
        self.bdaddr = bdaddr
        self.sightings = []
        self.sightingsByBase = {}
        pass

    def __str__(self):
        return "Chair {3}, accel={0}, heading={1}, rssiSum={2}".format(round(self.maxAccel(), 2),
                int(round(self.lastHeading())), self.rssiSummary(), self.bdaddr)
        
    def addSighting(self, sighting):
        sighting['accel'] = acc2magnitude(sighting['accel'])
        sighting['heading'] = magnet2heading(sighting['magnet'])
        
        self.sightings.append(sighting)
        if sighting['baseId'] not in self.sightingsByBase.keys():
            self.sightingsByBase[sighting['baseId']] = []
        self.sightingsByBase[sighting['baseId']].append(sighting)

    def getLocation(self):
        return min_max(self.rssiSummary())

    #averages out the rssi's over the ones seen
    def rssiSummary(self):
        result = {}
        for base in self.sightingsByBase:
            rssiSum = 0
            for sighting in self.sightingsByBase[base]:
                rssiSum = rssiSum + sighting['rssi']
            result[base] = float(rssiSum) / len(self.sightingsByBase[base])
        return result

    def maxAccel(self):
        result = -1
        for sighting in self.sightings:
            if sighting.get('accel', -1) > result:
                result = sighting['accel']
        return result

    def lastHeading(self):
        result = -1
        lastTime = 0L
        for sighting in self.sightings:
            if sighting['time'] > lastTime:
                result = sighting.get('heading', -1)
        return result

    def getSummary(self):
        pass

#true if string is integer
def is_int(s):
    try: 
        float(s)
        return True
    except ValueError:
        return False

def valid_sighting(sighting):
    return ('bdaddr' in sighting.keys()
    and 'time' in sighting.keys()
    and is_int(sighting['time'])
    and 'rssi' in sighting.keys()
    and is_int(sighting['rssi'])
    and 'baseId' in sighting.keys()
    and int(sighting['baseId']) in bases.keys())

#converts it to co-ordinates for the browser. See the image on the webpage
def loc2pixels(loc):
    x = 65.0 * loc[0]
    y = 634 - loc[1]*65.0
    return (int(round(x)), int(round(y)))

def get_accel_timeout(bdaddr, accel):
    if (accel > ACCEL_THRESHHOLD):
        accelTimeouts[bdaddr] = ACCEL_TIMEOUT
    else:
        if bdaddr in accelTimeouts.keys():
            accelTimeouts[bdaddr] = accelTimeouts[bdaddr] - 1
        else:
            accelTimeouts[bdaddr] = 0
    if (accelTimeouts[bdaddr] < 0):
        accelTimeouts[bdaddr] = 0
    return accelTimeouts[bdaddr]
    

def on_message(mosq, obj, msg):
    sightings = json.loads(msg.payload)
    
    chairs = {}
    for sighting in sightings:
        if not valid_sighting(sighting):
            continue
        #check if a chair already exists
        if sighting['bdaddr'] not in chairs.keys():
            chairs[sighting['bdaddr']] = Chair(sighting['bdaddr'])
        #now add the sighting to the chair
        chairs[sighting['bdaddr']].addSighting(sighting)
    
    #get their locations and put it into the output strin
    outputStr = '{"chairs":['
    for bdaddr in chairs:
        print str(chairs[bdaddr])
        #only if all 4 nodes got it
        if len(chairs[bdaddr].rssiSummary()) >= 4:
            pixelLoc = loc2pixels(chairs[bdaddr].getLocation())
            heading = chairs[bdaddr].lastHeading()
            accel = get_accel_timeout(bdaddr, chairs[bdaddr].maxAccel())
            outputStr = outputStr + '{{"bdaddr":"{0}", "loc":[{1},{2}], "heading":{3}, "accelTimeout":{4}}},'.format(bdaddr,
                    pixelLoc[0], pixelLoc[1], heading, accel)
    #close off the json response
    if (len(outputStr)>20):
        outputStr = outputStr[:-1] + ']}'
    else:
        outputStr = outputStr + ']}' #(if empty)
    #write it to file so the client can grab it
    file_ = open("json", 'w')
    file_.write(outputStr)
    file_.close()
    return chairs

#            Base   X      Y
bases     = {2 : (1.923, 1.385),
             1 : (9.85,  1.277),
             0 : (3.415, 6.846),
             3 : (9.077, 9.154)}

#returns (x,y) of estimated location
def min_max(rssi_summary):
    
    firstIteration = True #set false after first base station iteration
    
    for base in rssi_summary:
        est_dist = rssi2distance(rssi_summary[base])

        if firstIteration:
            l = bases[base][0] - est_dist
            r = bases[base][0] + est_dist
            t = bases[base][1] + est_dist
            b = bases[base][1] - est_dist
            firstIteration = False
        else:
            if (bases[base][0] - est_dist > l):
                l = bases[base][0] - est_dist
            if (bases[base][0] + est_dist < r):
                r = bases[base][0] + est_dist
            if (bases[base][1] + est_dist < t):
                t = bases[base][1] + est_dist
            if (bases[base][1] - est_dist > b):
                b = bases[base][1] - est_dist

    #now calc the centre of the intersections base on the veritices
    return ((l + r) / 2, (t + b) / 2) 

def extended_min_max(rssi_summary):
    estDistances = {}
    weightArray = {}
    firstIteration = True
    
    for base in rssi_summary:
        est_dist = rssi2distance(rssi_summary[base])
        estDistances[base] = est_dist
        if firstIteration:
            l = bases[base][0] - est_dist
            r = bases[base][0] + est_dist
            t = bases[base][1] + est_dist
            b = bases[base][1] - est_dist
            firstIteration = False
        else:
            if (bases[base][0] - est_dist > l):
                l = bases[base][0] - est_dist
            if (bases[base][0] + est_dist < r):
                r = bases[base][0] + est_dist
            if (bases[base][1] + est_dist < t):
                t = bases[base][1] + est_dist
            if (bases[base][1] - est_dist > b):
                b = bases[base][1] - est_dist
                
    #array of the vertices (bases) of bounding box
    vertexArray = [(l,t), (l,b), (r,t), (r,b)]

    #calculate the weights for each vertex
    for vertex in vertexArray:
        #W2: 1/SUM:(dist each beacon to vertex-estimatedradiusofnode)^2)
        denom = 0.0
        for base in rssi_summary:
            #Euclidean distance from becon to base
            euclidDist = math.sqrt(math.pow(bases[base][0] - vertex[0], 2)
                                +  math.pow(bases[base][1] - vertex[1], 2))
            denom = denom + math.pow(euclidDist - estDistances[base], 2)
        #store the weight of this vertex for later use
        weightArray[vertex] = (1.0 / denom)

    #stores for the final extended-min-max eqn
    sumNumx = 0.0
    sumNumy = 0.0
    sumDenom = 0.0
    for vertex in vertexArray:
        sumNumx = sumNumx + weightArray[vertex] * vertex[0]
        sumNumy = sumNumy + weightArray[vertex] * vertex[1]
        sumDenom = sumDenom + weightArray[vertex]

    #calculate the final location
    return ((sumNumx/sumDenom, sumNumy/sumDenom))
        

def main():
    datapacket = ""
    rc = 0
    mqttc = mosquitto.Mosquitto()

    mqttc.on_message = on_message

    try:
        mqttc.connect("winter.ceit.uq.edu.au", 1883, 60)
    except:
        print "cannot connect"
        sys.exit(1)
        
    mqttc.subscribe("/beacons/fromdb")

    while mqttc.loop(0.5) == 0:
        pass

main()
