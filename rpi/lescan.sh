#!/bin/bash

while true
do
    sudo hcitool lescan --passive
    sudo ./usbreset  /dev/bus/usb/001/004
done
