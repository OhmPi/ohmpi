"""
29/10/2019
OHMPY_code is a program to control the low-cost and open source resistivity meter
OHMPY, it has been developed by Rémi CLEMENT,Vivien DUBOIS, Nicolas FORQUET (IRSTEA) and Yannick FARGIER (IFSTTAR).
"""
print 'OHMPI start' 
print MyDateTime.isoformat()
print 'Import library'

#!/usr/bin/python
import RPi.GPIO as GPIO
import time
import datetime
import board
import busio
import numpy
import os
import sys
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

"""
parameters
"""
nb_eletrodes = 32 # maximum number of electrodes on the resistivity meter


"""
functions
"""
# function swtich_mux select the right channels for the multiplexer cascade for electrodes A, B, M and N.
def switch_mux(quadripole):
    path2elec = numpy.loadtxt("path2elec.txt", delimiter=" ", dtype=bool)
    quadmux = numpy.loadtxt("quadmux.txt", delimiter=" ", dtype=int)
    for i in range(0,4):
        for j in range(0,5) :
            GPIO.output(int(quadmux[i,j]), bool(path2elec[quadripole[i]-1,j]))


def read_quad(filename, nb_elec):
    output = numpy.loadtxt(filename, delimiter=" ",dtype=int) # load quadripole file
    # locate lines where the electrode index exceeds the maximum number of electrodes
    test_index_elec = numpy.array(numpy.where(output > 32))
    # rajouter un test pour le deuxième cas du ticket #2
    # if statement with exit cases (rajouter un else if pour le deuxième cas du ticket #2)
    if test_index_elec.size != 0:
        for i in range(len(test_index_elec[0,:])):
            print("An electrode index at line "+ str(test_index_elec[0,i]+1)+" exceeds the maximum number of electrodes")
        sys.exit(1)
    else:
        return output             


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#i2c = busio.I2C(board.SCL, board.SDA)
# Create the ADC object using the I2C bus
#ads = ADS.ADS1115(i2c)
#chan = AnalogIn(ads, ADS.P0)
"""
Initialization of multiplexer channels
"""
pinList = [12,16,20,21,26,18,23,24,25,19,6,13,4,17,27,22,10,9,11,5] # List of GPIOs enabled for relay cards (electrodes)
for i in pinList:
    GPIO.setup(i, GPIO.OUT)
    GPIO.output(i, GPIO.HIGH)
"""
Measurement settings
"""
injection_time = 5 # Current injection time in second
nbr_meas= 900 # Number of times the quadrupole sequence is repeated
sequence_delay= 30 # Delay in Second between 2 sequences
stack= 1 # repetition of the current injection for each quadrupole

"""
Reading the quadripole file
"""
N=read_quad("ABMN.txt",nb_electrodes) # load quadripole file

for g in range(0,nbr_meas): # for time-lapse monitoring

    """
    Selection electrode activées pour chaque quadripole
    """
    for i in range(0,N.shape[0]): # boucle sur les quadripôles, qui tient compte du nombre de quadripole dans le fichier ABMN
        # call switch_mux function
        switch_mux(N[i,])

        time.sleep(injection_time);
        GPIO.output(12, GPIO.HIGH); GPIO.output(16, GPIO.HIGH); GPIO.output(20, GPIO.HIGH); GPIO.output(21, GPIO.HIGH); GPIO.output(26, GPIO.HIGH)
        GPIO.output(18, GPIO.HIGH); GPIO.output(23, GPIO.HIGH); GPIO.output(24, GPIO.HIGH); GPIO.output(25, GPIO.HIGH); GPIO.output(19, GPIO.HIGH)
        GPIO.output(6, GPIO.HIGH); GPIO.output(13, GPIO.HIGH); GPIO.output(4, GPIO.HIGH); GPIO.output(17, GPIO.HIGH); GPIO.output(27, GPIO.HIGH)
        GPIO.output(22, GPIO.HIGH); GPIO.output(10, GPIO.HIGH); GPIO.output(9, GPIO.HIGH); GPIO.output(11, GPIO.HIGH); GPIO.output(5, GPIO.HIGH)


    time.sleep(sequence_delay);#waiting next measurement




'''
Save result in txt file
'''

