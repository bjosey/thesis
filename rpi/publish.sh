#!/bin/bash

while true
do
    sudo hcidump | ./publisher.py
done
