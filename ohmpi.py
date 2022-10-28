# -*- coding: utf-8 -*-
"""
created on January 6, 2020.
Updates May 2022, Oct 2022.
Ohmpi.py is a program to control a low-cost and open hardware resistivity meter OhmPi that has been developed by
Rémi CLEMENT (INRAE),Vivien DUBOIS (INRAE), Hélène GUYARD (IGE), Nicolas FORQUET (INRAE), Yannick FARGIER (IFSTTAR)
Olivier KAUFMANN (UMONS), Arnaud WATELET (UMONS) and Guillaume BLANCHY (ILVO).
"""

import os
import io
import json

import numpy as np
import csv
import time
from io import StringIO
from datetime import datetime
from termcolor import colored
import threading
import paho.mqtt.client as mqtt_client
from logging_setup import setup_loggers
from config import MQTT_CONTROL_CONFIG, OHMPI_CONFIG

# finish import (done only when class is instantiated as some libs are only available on arm64 platform)
try:
    import board  # noqa
    import busio  # noqa
    import adafruit_tca9548a  # noqa
    import adafruit_ads1x15.ads1115 as ads  # noqa
    from adafruit_ads1x15.analog_in import AnalogIn  # noqa
    from adafruit_mcp230xx.mcp23008 import MCP23008  # noqa
    from adafruit_mcp230xx.mcp23017 import MCP23017  # noqa
    import digitalio  # noqa
    from digitalio import Direction  # noqa
    from gpiozero import CPUTemperature  # noqa

    arm64_imports = True
except ImportError as error:
    print(colored(f'Import error: {error}', 'yellow'))
    arm64_imports = False
except Exception as error:
    print(colored(f'Unexpected error: {error}', 'red'))
    exit()


class OhmPi(object):
    """Create the main OhmPi object.

    Parameters
    ----------
    settings : str, optional
        Path to the .json configuration file.
    sequence : str, optional
        Path to the .txt where the sequence is read. By default, a 1 quadrupole
        sequence: 1, 2, 3, 4 is used.
    """

    def __init__(self, settings=None, sequence=None, use_mux=False, mqtt=True, on_pi=None idps=False):
        # flags and attributes
        if on_pi is None:
            _, on_pi = OhmPi.get_platform()

        self._sequence = sequence
        self.use_mux = use_mux
        self.on_pi = on_pi  # True if run from the RaspberryPi with the hardware, otherwise False for random data
        self.status = 'idle'  # either running or idle
        self.thread = None  # contains the handle for the thread taking the measurement

        # set loggers
        config_exec_logger, _, config_data_logger, _, _ = setup_loggers(mqtt=mqtt)  # TODO: add SOH
        self.data_logger = config_data_logger
        self.exec_logger = config_exec_logger
        self.soh_logger = None
        print('Loggers:')
        print(colored(f'Exec logger {self.exec_logger.handlers if self.exec_logger is not None else "None"}', 'blue'))
        print(colored(f'Data logger {self.data_logger.handlers if self.data_logger is not None else "None"}', 'blue'))
        print(colored(f'SOH logger {self.soh_logger.handlers if self.soh_logger is not None else "None"}', 'blue'))

        # set controller
        self.controller = mqtt_client.Client(f"ohmpi_{OHMPI_CONFIG['id']}_listener", clean_session=False)  # create new instance
        print(colored(f"Connecting to control topic {MQTT_CONTROL_CONFIG['ctrl_topic']} on {MQTT_CONTROL_CONFIG['hostname']} broker", 'blue'))
        trials = 0
        trials_max = 10
        broker_connected = False
        while trials < trials_max:
            try:
                self.controller.username_pw_set(MQTT_CONTROL_CONFIG['auth'].get('username'),
                                                MQTT_CONTROL_CONFIG['auth']['password'])
                self.controller.connect(MQTT_CONTROL_CONFIG['hostname'])
                trials = trials_max
                broker_connected = True
            except Exception as e:
                self.exec_logger.debug(f'Unable to connect control broker: {e}')
                self.exec_logger.info('trying again to connect to control broker...')
                time.sleep(2)
                trials += 1
        if broker_connected:
            self.exec_logger.info(f"Subscribing to control topic {MQTT_CONTROL_CONFIG['ctrl_topic']}")
            self.controller.subscribe(MQTT_CONTROL_CONFIG['ctrl_topic'], MQTT_CONTROL_CONFIG['qos'])
        else:
            self.exec_logger.error(f"Unable to connect to control broker on {MQTT_CONTROL_CONFIG['hostname']}")
            self.controller = None

        # read in hardware parameters (config.py)
        self._read_hardware_config()

        # default acquisition settings
        self.settings = {
            'injection_duration': 0.2,
            'nbr_meas': 1,
            'sequence_delay': 1,
            'nb_stack': 1,
            'export_path': 'data/measurement.csv'
        }
        # read in acquisition settings
        if settings is not None:
            self._update_acquisition_settings(settings)

        print(self.settings)
        self.exec_logger.debug('Initialized with settings:' + str(self.settings))

        # read quadrupole sequence
        if sequence is not None:
            self.load_sequence(sequence)

        self.idps = idps  # flag to use dps for injection or not
        
        # connect to components on the OhmPi board
        if self.on_pi:
            # activation of I2C protocolge
            self.i2c = busio.I2C(board.SCL, board.SDA)  # noqa

            # I2C connexion to MCP23008, for current injection
            self.mcp = MCP23008(self.i2c, address=0x20)

            # ADS1115 for current measurement (AB)
            self.ads_current_address = 0x48
            self.ads_current = ads.ADS1115(self.i2c, gain=2 / 3, data_rate=860, address=self.ads_current_address)

            # ADS1115 for voltage measurement (MN)
            self.ads_voltage_address = 0x49
            self.ads_voltage = ads.ADS1115(self.i2c, gain=2 / 3, data_rate=860, address=self.ads_voltage_address)

            # current injection module
            if self.idps:
                self.DPS = minimalmodbus.Instrument(port='/dev/ttyUSB0', slaveaddress=1) # port name, slave address (in decimal)
                self.DPS.serial.baudrate = 9600                      # Baud rate 9600 as listed in doc
                self.DPS.serial.bytesize = 8                         # 
                self.DPS.serial.timeout  = 1                         # greater than 0.5 for it to work
                self.DPS.debug           = False                     # 
                self.DPS.serial.parity   = 'N'                       # No parity
                self.DPS.mode            = minimalmodbus.MODE_RTU    # RTU mode
                self.DPS.write_register(0x0001, 40, 0)   # max current allowed (36 mA for relays)
                # (last number) 0 is for mA, 3 is for A
            
            # injection courant and measure (TODO check if it works, otherwise back in run_measurement())
            self.pin0 = self.mcp.get_pin(0)
            self.pin0.direction = Direction.OUTPUT
            self.pin0.value = False
            self.pin1 = self.mcp.get_pin(1)
            self.pin1.direction = Direction.OUTPUT
            self.pin1.value = False


        # Starts the command processing thread
        self.cmd_listen = True
        self.cmd_thread = threading.Thread(target=self.process_commands)
        self.cmd_thread.start()

        # Starts the command processing thread
        self.cmd_listen = True
        self.cmd_thread = threading.Thread(target=self._control)
        self.cmd_thread.start()

    @property
    def sequence(self):
        """Gets or sets sequence"""
        if self._sequence is not None:
            assert isinstance(self._sequence, np.ndarray)
        return self._sequence

    @sequence.setter
    def sequence(self, sequence):
        if sequence is not None:
            assert isinstance(sequence, np.ndarray)
            self.use_mux = True
        else:
            self.use_mux = False
        self._sequence = sequence

    def _control(self):
        def on_message(client, userdata, message):
            command = message.payload.decode('utf-8')
            self.exec_logger.debug(f'Received command {command}')
            self.process_commands(command)

        self.controller.on_message = on_message
        self.controller.loop_start()
        while True:
            time.sleep(.5)

    def _update_acquisition_settings(self, config):
        warnings.warn('This function is deprecated, use update_settings() instead.',
                      DeprecationWarning)
        self.update_settings(config)
   
   def update_settings(self, config):
        """Update acquisition settings from a json file or dictionary.
        Parameters can be:
            - nb_electrodes (number of electrode used, if 4, no MUX needed)
            - injection_duration (in seconds)
            - nbr_meas (total number of times the sequence will be run)
            - sequence_delay (delay in second between each sequence run)
            - nb_stack (number of stack for each quadrupole measurement)
            - export_path (path where to export the data, timestamp will be added to filename)

        Parameters
        ----------
        config : str
            Path to the .json or dictionary.
        """
        if isinstance(config, dict):
            self.settings.update(config)
        else:
            with open(config) as json_file:
                dic = json.load(json_file)
            self.settings.update(dic)
        self.exec_logger.debug('Acquisition parameters updated: ' + str(self.settings))

    def _read_hardware_config(self):
        """Read hardware configuration from config.py
        """
        from config import OHMPI_CONFIG
        self.id = OHMPI_CONFIG['id']  # ID of the OhmPi
        self.r_shunt = OHMPI_CONFIG['R_shunt']  # reference resistance value in ohm
        self.Imax = OHMPI_CONFIG['Imax']  # maximum current
        self.exec_logger.warning(f'The maximum current cannot be higher than {self.Imax} mA')
        self.coef_p2 = OHMPI_CONFIG['coef_p2']  # slope for current conversion for ads.P2, measurement in V/V
        self.nb_samples = OHMPI_CONFIG['integer']  # number of samples measured for each stack
        self.version = OHMPI_CONFIG['version']  # hardware version
        self.max_elec = OHMPI_CONFIG['max_elec']  # maximum number of electrodes
        self.board_addresses = OHMPI_CONFIG['board_addresses']
        self.board_version = OHMPI_CONFIG['board_version']
        self.exec_logger.debug(f'OHMPI_CONFIG = {str(OHMPI_CONFIG)}')
        


    @staticmethod
    def _find_identical_in_line(quads):
        """Find quadrupole where A and B are identical.
        If A and B are connected to the same relay, the Pi burns (short-circuit).
        
        Parameters
        ----------
        quads : numpy.ndarray
            List of quadrupoles of shape nquad x 4 or 1D vector of shape nquad.
        
        Returns
        -------
        output : numpy.ndarray 1D array of int
            List of index of rows where A and B are identical.
        """
        # TODO is this needed for M and N?

        # if we have a 1D array (so only 1 quadrupole), make it 2D
        if len(quads.shape) == 1:
            quads = quads[None, :]

        output = np.where(quads[:, 0] == quads[:, 1])[0]

        # output = []
        # if array_object.ndim == 1:
        #     temp = np.zeros(4)
        #     for i in range(len(array_object)):
        #         temp[i] = np.count_nonzero(array_object == array_object[i])
        #     if any(temp > 1):
        #         output.append(0)
        # else:
        #     for i in range(len(array_object[:,1])):
        #         temp = np.zeros(len(array_object[1,:]))
        #         for j in range(len(array_object[1,:])):
        #             temp[j] = np.count_nonzero(array_object[i,:] == array_object[i,j])
        #         if any(temp > 1):
        #             output.append(i)
        return output


    @staticmethod
    def get_platform():
        """Get platform name and check if it is a raspberry pi
        Returns
        =======
        str, bool
            name of the platform on which the code is running, boolean that is true if the platform is a raspberry pi"""

        platform = 'unknown'
        on_pi = False
        try:
            with io.open('/sys/firmware/devicetree/base/model', 'r') as f:
                platform = f.read().lower()
            if 'raspberry pi' in platform:
                on_pi = True
        except FileNotFoundError:
            pass
        return platform, on_pi


    def read_quad(self, filename):
        warnings.warn('This function is deprecated, use load_sequence() instead.',
                      DeprecationWarning)

        self.load_sequence(filaname)
        
    def load_sequence(self, filename):
        """Read quadrupole sequence from file.

        Parameters
        ----------
        filename : str
            Path of the .csv or .txt file with A, B, M and N electrodes.
            Electrode index start at 1.

        Returns
        -------
        sequence : numpy.array
            Array of shape (number quadrupoles * 4).
        """
        sequence = np.loadtxt(filename, delimiter=" ", dtype=np.uint32)  # load quadrupole file

        if sequence is not None:
            self.exec_logger.debug('Sequence of {:d} quadrupoles read.'.format(sequence.shape[0]))

        # locate lines where the electrode index exceeds the maximum number of electrodes
        test_index_elec = np.array(np.where(sequence > self.max_elec))

        # locate lines where electrode A == electrode B
        test_same_elec = self.find_identical_in_line(sequence)

        # if statement with exit cases (TODO rajouter un else if pour le deuxième cas du ticket #2)
        if test_index_elec.size != 0:
            for i in range(len(test_index_elec[0, :])):
                self.exec_logger.error(f'An electrode index at line {str(test_index_elec[0, i] + 1)} '
                                       f'exceeds the maximum number of electrodes')
            # sys.exit(1)
            sequence = None
        elif len(test_same_elec) != 0:
            for i in range(len(test_same_elec)):
                self.exec_logger.error(f'An electrode index A == B detected at line {str(test_same_elec[i] + 1)}')
            # sys.exit(1)
            sequence = None

        if sequence is not None:
            self.exec_logger.info('Sequence of {:d} quadrupoles read.'.format(sequence.shape[0]))
        else:
            self.exec_logger.warning(f'Unable to load sequence {filename}')

        self.sequence = sequence


    def switch_mux(self, electrode_nr, state, role):
        """Select the right channel for the multiplexer cascade for a given electrode.
        
        Parameters
        ----------
        electrode_nr : int
            Electrode index to be switched on or off.
        state : str
            Either 'on' or 'off'.
        role : str
            Either 'A', 'B', 'M' or 'N', so we can assign it to a MUX board.
        """
        if not self.use_mux:
            pass # no MUX or don't use MUX
        elif self.sequence is None:
            self.exec_logger.warning('Unable to switch MUX without a sequence')
        else:
            # choose with MUX board
            tca = adafruit_tca9548a.TCA9548A(self.i2c, self.board_addresses[role])

            # find I2C address of the electrode and corresponding relay
            # considering that one MCP23017 can cover 16 electrodes
            electrode_nr = electrode_nr - 1  # switch to 0 indexing
            i2c_address = 7 - electrode_nr // 16  # quotient without rest of the division
            relay_nr = electrode_nr - (electrode_nr // 16) * 16
            relay_nr = relay_nr + 1  # switch back to 1 based indexing

            if i2c_address is not None:
                # select the MCP23017 of the selected MUX board
                mcp2 = MCP23017(tca[i2c_address])
                mcp2.get_pin(relay_nr - 1).direction = digitalio.Direction.OUTPUT

                if state == 'on':
                    mcp2.get_pin(relay_nr - 1).value = True
                else:
                    mcp2.get_pin(relay_nr - 1).value = False

                self.exec_logger.debug(f'Switching relay {relay_nr} {state} for electrode {electrode_nr}')
            else:
                self.exec_logger.warning(f'Unable to address electrode nr {electrode_nr}')


    def switch_mux_on(self, quadrupole):
        """ Switch on multiplexer relays for given quadrupole.
        
        Parameters
        ----------
        quadrupole : list of 4 int
            List of 4 integers representing the electrode numbers.
        """
        roles = ['A', 'B', 'M', 'N']
        # another check to be sure A != B
        if quadrupole[0] != quadrupole[1]:
            for i in range(0, 4):
                if quadrupole[i] > 0:
                    self.switch_mux(quadrupole[i], 'on', roles[i])
        else:
            self.exec_logger.error('A == B -> short circuit risk detected!')


    def switch_mux_off(self, quadrupole):
        """ Switch off multiplexer relays for given quadrupole.
        
        Parameters
        ----------
        quadrupole : list of 4 int
            List of 4 integers representing the electrode numbers.
        """
        roles = ['A', 'B', 'M', 'N']
        for i in range(0, 4):
            if quadrupole[i] > 0:
                self.switch_mux(quadrupole[i], 'off', roles[i])


    def reset_mux(self):
        """Switch off all multiplexer relays."""
        roles = ['A', 'B', 'M', 'N']
        for i in range(0, 4):
            for j in range(1, self.max_elec + 1):
                self.switch_mux(j, 'off', roles[i])
        self.exec_logger.debug('All MUX switched off.')


    def gain_auto(self, channel):
        """ Automatically set the gain on a channel

        Parameters
        ----------
        channel:

        Returns
        -------
            float
        """
        gain = 2 / 3
        if (abs(channel.voltage) < 2.040) and (abs(channel.voltage) >= 1.023):
            gain = 2
        elif (abs(channel.voltage) < 1.023) and (abs(channel.voltage) >= 0.508):
            gain = 4
        elif (abs(channel.voltage) < 0.508) and (abs(channel.voltage) >= 0.250):
            gain = 8
        elif abs(channel.voltage) < 0.256:
            gain = 16
        self.exec_logger.debug(f'Setting gain to {gain}')
        return gain
        
        
    def _compute_tx_volt(self, best_tx_injtime=0.1, strategy='vmax', tx_volt=5):
        """Estimating best Tx voltage based on different strategy.
        At first a half-cycle is made for a short duration with a fixed
        known voltage. This gives us Iab and Rab. We also measure Vmn.
        A constant c = vmn/iab is computed (only depends on geometric
        factor and ground resistivity, that doesn't change during a 
        quadrupole). Then depending on the strategy, we compute which
        vab to inject to reach the minimum/maximum Iab current or 
        min/max Vmn.
        This function also compute the polarity on Vmn (on which pin
        of the ADS1115 we need to measure Vmn to get the positive value).
        
        Parameters
        ----------
        best_tx_injtime : float, optional
            Time in milliseconds for the half-cycle used to compute Rab.
        strategy : str, optional
            Either:
            - vmin : compute Vab to reach a minimum Iab and Vmn
            - vmax : compute Vab to reach a maximum Iab and Vmn
            - constant : apply given Vab
        tx_volt : float, optional
            Voltage apply to try to guess the best voltage. 5 V applied 
            by default. If strategy "constant" is chosen, constant voltage
            to applied is "tx_volt".
        
        Returns
        -------
        vab : float
            Proposed Vab according to the given strategy.
        polarity : int
            Either 1 or -1 to know on which pin of the ADS the Vmn is measured.
        """
        
        # hardware limits
        voltage_min = 10  # mV
        voltage_max = 4500
        current_min = voltage_min / (self.r_shunt * 50)  # mA
        current_max = voltage_max / (self.r_shunt * 50)
        tx_max = 40  # volt
        
        # check of volt
        volt = tx_volt
        if volt > tx_max:
            print('sorry, cannot inject more than 40 V, set it back to 5 V')
            volt = 5
        
        # redefined the pin of the mcp (needed when relays are connected)
        self.pin0 = self.mcp.get_pin(0)
        self.pin0.direction = Direction.OUTPUT
        self.pin0.value = False
        self.pin1 = self.mcp.get_pin(1)
        self.pin1.direction = Direction.OUTPUT
        self.pin1.value = False
        
        # select a polarity to start with
        self.pin0.value = True
        self.pin1.value = False
        
        # set voltage for test
        self.DPS.write_register(0x0000, volt, 2) 
        self.DPS.write_register(0x09, 1) # DPS5005 on
        time.sleep(best_tx_injtime) # inject for given tx time
        
        # autogain
        self.ads_current = ads.ADS1115(self.i2c, gain=2/3, data_rate=860, address=self.ads_current_address)
        self.ads_voltage = ads.ADS1115(self.i2c, gain=2/3, data_rate=860, address=self.ads_voltage_address)
        #print('current P0', AnalogIn(self.ads_current, ads.P0).voltage)
        #print('voltage P0', AnalogIn(self.ads_voltage, ads.P0).voltage)
        #print('voltage P2', AnalogIn(self.ads_voltage, ads.P2).voltage)
        gain_current = self.gain_auto(AnalogIn(self.ads_current, ads.P0))
        gain_voltage0 = self.gain_auto(AnalogIn(self.ads_voltage, ads.P0))
        gain_voltage2 = self.gain_auto(AnalogIn(self.ads_voltage, ads.P2))
        gain_voltage = np.min([gain_voltage0, gain_voltage2])
        #print('gain current: {:.3f}, gain voltage: {:.3f}'.format(gain_current, gain_voltage))
        self.ads_current = ads.ADS1115(self.i2c, gain=gain_current, data_rate=860, address=self.ads_current_address)
        self.ads_voltage = ads.ADS1115(self.i2c, gain=gain_voltage, data_rate=860, address=self.ads_voltage_address)
        
        # we measure the voltage on both A0 and A2 to guess the polarity
        I = (AnalogIn(self.ads_current, ads.P0).voltage) * 1000/50/self.r_shunt # measure current
        U0 = AnalogIn(self.ads_voltage, ads.P0).voltage * 1000 # measure voltage
        U2 = AnalogIn(self.ads_voltage, ads.P2).voltage * 1000
        #print('I (mV)', I*50*self.r_shunt)
        #print('I (mA)', I)
        #print('U0 (mV)', U0)
        #print('U2 (mV)', U2)
        
        # check polarity
        polarity = 1  # by default, we guessed it right
        vmn = U0
        if U0 < 0: # we guessed it wrong, let's use a correction factor
            polarity = -1
            vmn = U2
        #print('polarity', polarity)
        
        # compute constant
        c = vmn / I
        Rab = (volt * 1000) / I
        
        self.exec_logger.debug('Rab = {:.2f} Ohms'.format(Rab))

        # implement different strategy
        if strategy == 'vmax':
            vmn_max = c * current_max
            if vmn_max < voltage_max and vmn_max > voltage_min:
                vab = current_max * Rab
                self.exec_logger.debug('target max current')
            else:
                iab = voltage_max / c
                vab = iab * Rab
                self.exec_logger.debug('target max voltage')
            if vab > 25000:
                vab = 25000
            vab = vab / 1000 * 0.9
            
        elif strategy == 'vmin':
            vmn_min = c * current_min
            if vmn_min > voltage_min and vmn_min < voltage_max:
                vab = current_min * Rab
                self.exec_logger.debug('target min current')
            else:
                iab = voltage_min / c
                vab = iab * Rab
                self.exec_logger.debug('target min voltage')
            if vab < 1000:
                vab = 1000
            vab = vab / 1000 * 1.1
        
        elif strategy == 'constant':
            vab = volt
        else:
            vab = 5
            
        #self.DPS.write_register(0x09, 0) # DPS5005 off
        self.pin0.value = False
        self.pin1.value = False
        
        return vab, polarity
        
        
    def run_measurement(self, quad=None, nb_stack=None, injection_duration=None,
                        autogain=True, strategy='constant', tx_volt=5, best_tx_injtime=0.1):
        """Do a 4 electrode measurement and measure transfer resistance obtained.

        Parameters
        ----------
        quad : iterable (list of int)
            Quadrupole to measure, just for labelling. Only switch_mux_on/off
            really create the route to the electrodes.
        nb_stack : int, optional
            Number of stacks. A stacl is considered two half-cycles (one
            positive, one negative).
        injection_duration : int, optional
            Injection time in seconds.
        autogain : bool, optional
            If True, will adapt the gain of the ADS1115 to maximize the
            resolution of the reading.
        strategy : str, optional
            (V3.0 only) If we search for best voltage (tx_volt == 0), we can choose
            different strategy:
            - vmin: find lowest voltage that gives us a signal
            - vmax: find max voltage that are in the range
            For a constant value, just set the tx_volt.
        tx_volt : float, optional
            (V3.0 only) If specified, voltage will be imposed. If 0, we will look 
            for the best voltage. If a best Tx cannot be found, no
            measurement will be taken and values will be NaN.
        best_tx_injtime : float, optional
            (V3.0 only) Injection time in seconds used for finding the best voltage.
        """
        self.exec_logger.debug('Starting measurement')
        self.exec_logger.info('Waiting for data')

        # TODO here we can add the current_injected or voltage_injected in mA or mV
        # check arguments
        if quad is None:
            quad = [0, 0, 0, 0]

        
        if self.on_pi:
            
            # check arguments
            if nb_stack is None:
                nb_stack = self.settings['nb_stack']
            if injection_duration is None:
                injection_duration = self.settings['injection_duration']
            tx_volt = float(tx_volt)

            # inner variable initialization
            sum_i = 0
            sum_vmn = 0
            sum_ps = 0

            # let's define the pin again as if we run through measure()
            # as it's run in another thread, it doesn't consider these
            # and this can lead to short circuit!
            self.pin0 = self.mcp.get_pin(0)
            self.pin0.direction = Direction.OUTPUT
            self.pin0.value = False
            self.pin1 = self.mcp.get_pin(1)
            self.pin1.direction = Direction.OUTPUT
            self.pin1.value = False
            
            # get best voltage to inject AND polarity
            if self.idps:
                tx_volt, polarity = self._compute_tx_volt(
                    best_tx_injtime=best_tx_injtime, strategy=strategy, tx_volt=tx_volt)
                self.exec_logger.debug('Best vab found is {:.3}V'.format(tx_volt))
            else:
                polarity = 1
            
            # first reset the gain to 2/3 before trying to find best gain (mode 0 is continuous)
            self.ads_current = ads.ADS1115(self.i2c, gain=2 / 3, data_rate=860, address=self.ads_current_address, mode=0)
            self.ads_voltage = ads.ADS1115(self.i2c, gain=2 / 3, data_rate=860, address=self.ads_voltage_address, mode=0)
            
            # turn on the power supply
            oor = False
            if self.idps:
                if np.isnan(tx_volt) == False:
                    self.DPS.write_register(0x0000, tx_volt, 2) # set tx voltage in V
                    self.DPS.write_register(0x09, 1) # DPS5005 on
                    time.sleep(0.05)
                else:
                    self.exec_logger.debug('No best voltage found, will not take measurement')
                    oor = True
                    
            if oor == False:  # we found a vab in the range so we measure
                if autogain:
                    # compute autogain
                    self.pin0.value = True
                    self.pin1.value = False
                    time.sleep(injection_duration)
                    gain_current = self.gain_auto(AnalogIn(self.ads_current, ads.P0))
                    if polarity > 0:
                        gain_voltage = self.gain_auto(AnalogIn(self.ads_voltage, ads.P0))
                    else:
                        gain_voltage = self.gain_auto(AnalogIn(self.ads_voltage, ads.P2))
                    self.pin0.value = False
                    self.pin1.value = False
                    self.exec_logger.debug('Gain current: {:.3f}, gain voltage: {:.3f}'.format(gain_current, gain_voltage))
                    self.ads_current = ads.ADS1115(self.i2c, gain=gain_current, data_rate=860, address=self.ads_current_address, mode=0)
                    self.ads_voltage = ads.ADS1115(self.i2c, gain=gain_voltage, data_rate=860, address=self.ads_voltage_address, mode=0)

                self.pin0.value = False
                self.pin1.value = False
                
                # one stack = 2 half-cycles (one positive, one negative)
                pinMN = 0 if polarity > 0 else 2
                
                # sampling for each stack at the end of the injection
                sampling_interval = 10  # ms
                self.nb_samples = int(injection_duration * 1000 // sampling_interval) + 1

                # full data for waveform
                fulldata = []
                
                #  we sample every 10 ms (as using AnalogIn for both current
                # and voltage takes about 7 ms). When we go over the injection
                # duration, we break the loop and truncate the meas arrays
                # only the last values in meas will be taken into account
                start_time = time.time()  # start counter
                for n in range(0, nb_stack * 2):  # for each half-cycles
                    # current injection
                    if (n % 2) == 0:
                        self.pin0.value = True
                        self.pin1.value = False
                    else:
                        self.pin0.value = False
                        self.pin1.value = True  # current injection nr2
                    self.exec_logger.debug(str(n) + ' ' + str(self.pin0.value) + ' ' + str(self.pin1.value))

                    # measurement of current i and voltage u during injection
                    meas = np.zeros((self.nb_samples, 3)) * np.nan
                    start_delay = time.time()  # stating measurement time
                    dt = 0
                    for k in range(0, self.nb_samples):
                        # reading current value on ADS channels
                        meas[k, 0] = (AnalogIn(self.ads_current, ads.P0).voltage * 1000) / (50 * self.r_shunt)
                        if self.board_version == '22.11':
                            if pinMN == 0:
                                meas[k, 1] = AnalogIn(self.ads_voltage, ads.P0).voltage * 1000
                            else:
                                meas[k, 1] = AnalogIn(self.ads_voltage, ads.P2).voltage * 1000 *-1
                        elif self.board_version == '22.10':
                            meas[k, 1] = -AnalogIn(self.ads_voltage, ads.P0, ads.P1).voltage * self.coef_p2 * 1000
                        #else:
                        #   self.exec_logger.debug('Unknown board')
                        time.sleep(sampling_interval / 1000)
                        dt = time.time() - start_delay  # real injection time (s)
                        meas[k, 2] = time.time() - start_time
                        if dt > (injection_duration - 0 * sampling_interval /1000):
                            break
                    
                    # stop current injection
                    self.pin0.value = False
                    self.pin1.value = False
                    end_delay = time.time()

                    # truncate the meas array if we didn't fill the last samples
                    meas = meas[:k+1]
                    
                    # measurement of current i and voltage u during off time
                    measpp = np.zeros((meas.shape[0], 3)) * np.nan
                    start_delay = time.time()  # stating measurement time
                    dt = 0
                    for k in range(0, measpp.shape[0]):
                        # reading current value on ADS channels
                        measpp[k, 0] = (AnalogIn(self.ads_current, ads.P0).voltage * 1000) / (50 * self.r_shunt)
                        if self.board_version == '22.11':
                            if pinMN == 0:
                                measpp[k, 1] = AnalogIn(self.ads_voltage, ads.P0).voltage * 1000
                            else:
                                measpp[k, 1] = AnalogIn(self.ads_voltage, ads.P2).voltage * 1000 *-1
                        elif self.board_version == '22.10':
                            measpp[k, 1] = -AnalogIn(self.ads_voltage, ads.P0, ads.P1).voltage * self.coef_p2 * 1000
                        else:
                            self.exec_logger.debug('unknown board')
                        time.sleep(sampling_interval / 1000)
                        dt = time.time() - start_delay  # real injection time (s)
                        measpp[k, 2] = time.time() - start_time
                        if dt > (injection_duration - 0 * sampling_interval /1000):
                            break
                    
                    end_delay = time.time()
                    
                    # truncate the meas array if we didn't fill the last samples
                    measpp = measpp[:k+1]
                    
                    # we alternate on which ADS1115 pin we measure because of sign of voltage
                    if pinMN == 0:
                        pinMN = 2
                    else:
                        pinMN = 0
                    
                    # store data for full wave form
                    fulldata.append(meas)
                    fulldata.append(measpp)
                
                # TODO get battery voltage and warn if battery is running low
                # TODO send a message on SOH stating the battery level
                    
                # let's do some calculation (out of the stacking loop)
                for n, meas in enumerate(fulldata[::2]):
                    # take average from the samples per stack, then sum them all
                    # average for the last third of the stacked values
                    #  is done outside the loop
                    sum_i = sum_i + (np.mean(meas[-int(meas.shape[0]//3):, 0]))
                    vmn1 = np.mean(meas[-int(meas.shape[0]//3), 1])
                    if (n % 2) == 0:
                        sum_vmn = sum_vmn - vmn1
                        sum_ps = sum_ps + vmn1
                    else:
                        sum_vmn = sum_vmn + vmn1
                        sum_ps = sum_ps + vmn1

            else:
                sum_i = np.nan
                sum_vmn = np.nan
                sum_ps = np.nan
                
            if self.idps:
                self.DPS.write_register(0x0000, 0, 2)  # reset to 0 volt
                self.DPS.write_register(0x09, 0) # DPS5005 off
                
            # reshape full data to an array of good size
            # we need an array of regular size to save in the csv
            if oor == False:
                fulldata = np.vstack(fulldata)
                # we create a big enough array given nb_samples, number of
                # half-cycles (1 stack = 2 half-cycles), and twice as we 
                # measure decay as well
                a = np.zeros((nb_stack * self.nb_samples * 2 * 2, 3)) * np.nan
                a[:fulldata.shape[0], :] = fulldata
                fulldata = a
            else:
                np.array([[]])


            # create a dictionary and compute averaged values from all stacks
            d = {
                "time": datetime.now().isoformat(),
                "A": quad[0],
                "B": quad[1],
                "M": quad[2],
                "N": quad[3],
                "inj time [ms]": (end_delay - start_delay) * 1000 if oor == False else 0,
                "Vmn [mV]": sum_vmn / (2 * nb_stack),
                "I [mA]": sum_i / (2 * nb_stack),
                "R [ohm]": sum_vmn / sum_i,
                "Ps [mV]": sum_ps / (2 * nb_stack),
                "nbStack": nb_stack,
                "Tx [V]": tx_volt if oor == False else 0,
                "CPU temp [degC]": CPUTemperature().temperature,
                "Nb samples [-]": self.nb_samples,
                "fulldata": fulldata,
            }
            

        else:  # for testing, generate random data
            d = {'time': datetime.now().isoformat(), 'A': quad[0], 'B': quad[1], 'M': quad[2], 'N': quad[3],
                 'R [ohm]': np.abs(np.random.randn(1)).tolist()}

        # round number to two decimal for nicer string output
        output = [f'{k}\t' for k in d.keys()]
        output = str(output)[:-1] + '\n'
        for k in d.keys():
            if isinstance(d[k], float):
                val = np.round(d[k], 2)
            else:
                val = d[k]
                output += f'{val}\t'
        output = output[:-1]

        # to the data logger
        dd = d.copy()
        dd.pop('fulldata')  # too much for logger
        dd.update({'A': str(dd['A'])})
        dd.update({'B': str(dd['B'])})
        dd.update({'M': str(dd['M'])})
        dd.update({'N': str(dd['N'])})
        self.data_logger.info(json.dumps(dd))

        return d


    def rs_check(self, tx_volt=12):
        """ Check contact resistance.
        """
        # create custom sequence where MN == AB
        # we only check the electrodes which are in the sequence (not all might be connected)
        if self.sequence is None or not self.use_mux:
            quads = np.array([[1, 2, 1, 2]], dtype=np.uint32)
        else:
            elec = np.sort(np.unique(self.sequence.flatten()))  # assumed order
            quads = np.vstack([
                elec[:-1],
                elec[1:],
                elec[:-1],
                elec[1:],
            ]).T
        if self.idps:
            quads[:, 2:] = 0  # we don't open Vmn to prevent burning the MN part
            # as it has a smaller range of accepted voltage

        # create filename to store RS
        export_path_rs = self.settings['export_path'].replace('.csv', '') \
                         + '_' + datetime.now().strftime('%Y%m%dT%H%M%S') + '_rs.csv'

        # perform RS check
        # self.run = True
        self.status = 'running'

        if self.on_pi:
            # make sure all mux are off to start with
            self.reset_mux()

            # measure all quad of the RS sequence
            for i in range(0, quads.shape[0]):
                quad = quads[i, :]  # quadrupole
                self.switch_mux_on(quad)  # put before raising the pins (otherwise conflict i2c)
                d = self.run_measurement(quad=quad, nb_stack=1, injection_duration=1, tx_volt=tx_volt, autogain=False)
                
                if self.idps:
                    voltage = tx_volt * 1000.0 # imposed voltage on dps5005
                else:
                    voltage = d['Vmn [mV]']
                current = d['I [mA]']
                
                # compute resistance measured (= contact resistance)
                resist = abs(voltage / current) /1000.
                #print(str(quad) + '> I: {:>10.3f} mA, V: {:>10.3f} mV, R: {:>10.3f} kOhm'.format(
                #    current, voltage, resist))
                msg = f'Contact resistance {str(quad):s}: I: {current * 1000.:>10.3f} mA, ' \
                          f'V: {voltage :>10.3f} mV, ' \
                          f'R: {resist :>10.3f} kOhm'

                self.exec_logger.debug(msg)
                
                # if contact resistance = 0 -> we have a short circuit!!
                if resist < 1e-5:
                    msg = '!!!SHORT CIRCUIT!!! {:s}: {:.3f} kOhm'.format(
                        str(quad), resist)
                    self.exec_logger.warning(msg)
                    print(msg)
                    
                # save data and print in a text file
                self.append_and_save(export_path_rs, {
                    'A': quad[0],
                    'B': quad[1],
                    'RS [kOhm]': resist,
                })
                
                # close mux path and put pin back to GND
                self.switch_mux_off(quad)
                
            self.reset_mux()

        else:
            pass
            
        self.status = 'idle'
        # self.run = False

    #
    #         # TODO if interrupted, we would need to restore the values
    #         # TODO or we offer the possibility in 'run_measurement' to have rs_check each time?

    @staticmethod
    def append_and_save(filename, last_measurement):
        """Append and save last measurement dataframe.

        Parameters
        ----------
        filename : str
            filename to save the last measurement dataframe
        last_measurement : dict
            Last measurement taken in the form of a python dictionary
        """
        last_measurement = deepcopy(last_measurement)
        if 'fulldata' in last_measurement:
            d = last_measurement['fulldata']
            n = d.shape[0]
            if n > 1:
                idic = dict(zip(['i' + str(i) for i in range(n)], d[:,0]))
                udic = dict(zip(['u' + str(i) for i in range(n)], d[:,1]))
                tdic = dict(zip(['t' + str(i) for i in range(n)], d[:,2]))
                last_measurement.update(idic)
                last_measurement.update(udic)
                last_measurement.update(tdic)
            last_measurement.pop('fulldata')


        if os.path.isfile(filename):
            # Load data file and append data to it
            with open(filename, 'a') as f:
                w = csv.DictWriter(f, last_measurement.keys())
                w.writerow(last_measurement)
                # last_measurement.to_csv(f, header=False)
        else:
            # create data file and add headers
            with open(filename, 'a') as f:
                w = csv.DictWriter(f, last_measurement.keys())
                w.writeheader()
                w.writerow(last_measurement)
                # last_measurement.to_csv(f, header=True)

    def process_commands(self, command):
        try:
            cmd_id = None
            decoded_message = json.loads(command)
            cmd_id = decoded_message.pop('cmd_id', None)
            cmd = decoded_message.pop('cmd', None)
            args = decoded_message.pop('args', None)
            status = False
            e = None
            if cmd is not None and cmd_id is not None:
                if cmd == 'update_settings' and args is not None:
                    self._update_acquisition_settings(args)
                    status = True
                elif cmd == 'set_sequence' and args is not None:
                    try:
                        self.sequence = np.loadtxt(StringIO(args)).astype('uint32')
                        status = True
                    except Exception as e:
                        self.exec_logger.warning(f'Unable to set sequence: {e}')
                        status = False
                elif cmd == 'start':
                    self.measure(cmd_id)
                    while not self.status == 'idle':
                        time.sleep(0.1)
                    status = True
                elif cmd == 'stop':
                    self.stop()
                    status = True
                elif cmd == 'load_sequence':
                    try:
                        self.load_sequence(args)
                        status = True
                    except Exception as e:
                        self.exec_logger.warning(f'Unable to load sequence: {e}')
                        status = False
                elif cmd == 'rs_check':
                    try:
                        self.rs_check()
                        status = True
                    except Exception as e:
                        print('error====', e)
                        self.exec_logger.warning(f'Unable to run rs-check: {e}')
                else:
                    self.exec_logger.warning(f'Unknown command {cmd} - cmd_id: {cmd_id}')
        except Exception as e:
            self.exec_logger.warning(f'Unable to decode command {command}: {e}')
            status = False
        finally:
            reply = {'cmd_id': cmd_id, 'status': status}
            reply = json.dumps(reply)
            self.exec_logger.debug(f'Execution report: {reply}')

    def measure(self, cmd_id=None):
        """Run the sequence in a separate thread. Can be stopped by 'OhmPi.stop()'.
        """
        # self.run = True
        self.status = 'running'
        self.exec_logger.debug(f'Status: {self.status}')
        self.exec_logger.debug(f'Measuring sequence: {self.sequence}')

        def func():
            for g in range(0, self.settings["nbr_meas"]):  # for time-lapse monitoring
                if self.status != 'running':
                    self.exec_logger.warning('Data acquisition interrupted')
                    break
                t0 = time.time()

                # create filename with timestamp
                filename = self.settings["export_path"].replace('.csv',
                                                                f'_{datetime.now().strftime("%Y%m%dT%H%M%S")}.csv')
                self.exec_logger.debug(f'Saving to {filename}')

                # make sure all multiplexer are off
                self.reset_mux()

                # measure all quadrupole of the sequence
                if self.sequence is None:
                    n = 1
                else:
                    n = self.sequence.shape[0]
                for i in range(0, n):
                    if self.sequence is None:
                        quad = np.array([0, 0, 0, 0])
                    else:
                        quad = self.sequence[i, :]  # quadrupole
                    if self.status == 'stopping':
                        break

                    # call the switch_mux function to switch to the right electrodes
                    self.switch_mux_on(quad)

                    # run a measurement
                    if self.on_pi:
                        acquired_data = self.run_measurement(quad, **kwargs)
                    else:  # for testing, generate random data
                        acquired_data = {
                            'A': [quad[0]], 'B': [quad[1]], 'M': [quad[2]], 'N': [quad[3]],
                            'R [ohm]': np.abs(np.random.randn(1))
                        }

                    # switch mux off
                    self.switch_mux_off(quad)

                    # add command_id in dataset
                    acquired_data.update({'cmd_id': cmd_id})
                    # log data to the data logger
                    self.data_logger.info(f'{acquired_data}')
                    print(f'{acquired_data}')
                    # save data and print in a text file
                    self.append_and_save(filename, acquired_data)
                    self.exec_logger.debug(f'{i+1:d}/{n:d}')

                # compute time needed to take measurement and subtract it from interval
                # between two sequence run (= sequence_delay)
                measuring_time = time.time() - t0
                sleep_time = self.settings["sequence_delay"] - measuring_time

                if sleep_time < 0:
                    # it means that the measuring time took longer than the sequence delay
                    sleep_time = 0
                    self.exec_logger.warning('The measuring time is longer than the sequence delay. '
                                             'Increase the sequence delay')

                # sleeping time between sequence
                if self.settings["nbr_meas"] > 1:
                    time.sleep(sleep_time)  # waiting for next measurement (time-lapse)
            self.status = 'idle'

        self.thread = threading.Thread(target=func)
        self.thread.start()

    def stop(self):
        """Stop the acquisition.
        """
        self.status = 'stopping'
        if self.thread is not None:
            self.thread.join()
        self.exec_logger.debug(f'Status: {self.status}')

    def quit(self):
        """Quit OhmPi.
        """
        self.cmd_listen = False
        if self.cmd_thread is not None:
            self.cmd_thread.join()
        self.exec_logger.debug(f'Stopped listening to tcp port.')
        exit()


VERSION = '2.1.5'

print(colored(r' ________________________________' + '\n' +
              r'|  _  | | | ||  \/  || ___ \_   _|' + '\n' +
              r'| | | | |_| || .  . || |_/ / | |' + '\n' +
              r'| | | |  _  || |\/| ||  __/  | |' + '\n' +
              r'\ \_/ / | | || |  | || |    _| |_' + '\n' +
              r' \___/\_| |_/\_|  |_/\_|    \___/ ', 'red'))
print('OhmPi start')
print('Version:', VERSION)
platform, on_pi = OhmPi.get_platform()
if on_pi:
    print(colored(f'Running on {platform} platform', 'green'))
    # TODO: check model for compatible platforms (exclude Raspberry Pi versions that are not supported...)
    #       and emit a warning otherwise
    if not arm64_imports:
        print(colored(f'Warning: Required packages are missing.\n'
                      f'Please run ./env.sh at command prompt to update your virtual environment\n', 'yellow'))
else:
    print(colored(f'Not running on the Raspberry Pi platform.\nFor simulation purposes only...', 'yellow'))

current_time = datetime.now()
print(current_time.strftime("%Y-%m-%d %H:%M:%S"))

# for testing
if __name__ == "__main__":
    
    # to run from 'python ohmpi.py'
    #ohmpi = OhmPi(config='ohmpi_param.json')
    #ohmpi.run_measurement()
    #ohmpi.measure()
    #ohmpi.read_quad('breadboard.txt')
    #ohmpi.measure()
    #time.sleep(20)
    #ohmpi.stop()
    
    # to start interface (also python ohmpi.py)
    Popen(['python', CONTROL_CONFIG['interface']])
    print('done')

