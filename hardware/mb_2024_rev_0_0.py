import importlib
from ..config import OHMPI_CONFIG
import adafruit_ads1x15.ads1115 as ads  # noqa
from adafruit_ads1x15.analog_in import AnalogIn  # noqa
from adafruit_mcp230xx.mcp23008 import MCP23008  # noqa
from digitalio import Direction  # noqa
import minimalmodbus  # noqa
import time
import numpy as np
from hardware import TxAbstract, RxAbstract
controller_module = importlib.import_module(f'{OHMPI_CONFIG["hardware"]["controller"]["model"]}')

TX_CONFIG = OHMPI_CONFIG['hardware']['TX']
RX_CONFIG = OHMPI_CONFIG['hardware']['RX']

# hardware limits
voltage_min = 10.  # mV
voltage_max = 4500.
RX_CONFIG['voltage_min'] = voltage_min  # mV
RX_CONFIG['voltage_max'] = voltage_max
TX_CONFIG['current_min'] = voltage_min / (TX_CONFIG['R_shunt'] * 50)  # mA
TX_CONFIG['current_max'] = voltage_max / (TX_CONFIG['R_shunt'] * 50)
TX_CONFIG['default_voltage'] = 5.  # V
TX_CONFIG['voltage_max'] = 50.  # V
TX_CONFIG['dps_switch_on_warm_up'] = 4. # 4 seconds

def _gain_auto(channel):
    """Automatically sets the gain on a channel

    Parameters
    ----------
    channel : ads.ADS1x15
        Instance of ADS where voltage is measured.

    Returns
    -------
    gain : float
        Gain to be applied on ADS1115.
    """

    gain = 2 / 3
    if (abs(channel.voltage) < 2.040) and (abs(channel.voltage) >= 1.0):
        gain = 2
    elif (abs(channel.voltage) < 1.0) and (abs(channel.voltage) >= 0.500):
        gain = 4
    elif (abs(channel.voltage) < 0.500) and (abs(channel.voltage) >= 0.250):
        gain = 8
    elif abs(channel.voltage) < 0.250:
        gain = 16
    return gain

class Tx(TxAbstract):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._voltage = kwargs.pop('voltage', TX_CONFIG['default_voltage'])
        self.controller = kwargs.pop('controller', controller_module.Controller())

        # I2C connexion to MCP23008, for current injection
        self.mcp_board = MCP23008(self.controller.bus, address=TX_CONFIG['mcp_board_address'])

        # ADS1115 for current measurement (AB)
        self._adc_gain = 2/3
        self.ads_current_address = 0x48
        self.ads_current = ads.ADS1115(self.controller.bus, gain=self.adc_gain, data_rate=860,
                                       address=self.ads_current_address)

        # Relays for pulse polarity
        self.pin0 = self.mcp_board.get_pin(0)
        self.pin0.direction = Direction.OUTPUT
        self.pin1 = self.mcp_board.get_pin(1)
        self.pin1.direction = Direction.OUTPUT
        self.polarity = 0

        # DPH 5005 Digital Power Supply
        self.pin2 = self.mcp_board.get_pin(2)  # dps +
        self.pin2.direction = Direction.OUTPUT
        self.pin3 = self.mcp_board.get_pin(3)  # dps -
        self.pin3.direction = Direction.OUTPUT
        self.turn_on()
        time.sleep(TX_CONFIG['dps_switch_on_warm_up'])
        self.DPS = minimalmodbus.Instrument(port='/dev/ttyUSB0', slaveaddress=1)  # port name, address (decimal)
        self.DPS.serial.baudrate = 9600  # Baud rate 9600 as listed in doc
        self.DPS.serial.bytesize = 8  #
        self.DPS.serial.timeout = 1.  # greater than 0.5 for it to work
        self.DPS.debug = False  #
        self.DPS.serial.parity = 'N'  # No parity
        self.DPS.mode = minimalmodbus.MODE_RTU  # RTU mode
        self.DPS.write_register(0x0001, 1000, 0)  # max current allowed (100 mA for relays)
        # (last number) 0 is for mA, 3 is for A

        # I2C connexion to MCP23008, for current injection
        self.pin4 = self.mcp_board.get_pin(4)  # Ohmpi_run
        self.pin4.direction = Direction.OUTPUT
        self.pin4.value = True

        tx_bat = self.DPS.read_register(0x05, 2)
        if self.exec_logger is not None:
            self.exec_logger.info(f'TX battery: {tx_bat:.1f} V')
        if tx_bat < 12.:
            if self.soh_logger is not None:
                self.soh_logger.debug(f'Low TX Battery: {tx_bat:.1f} V')  # TODO: SOH logger
        self.turn_off()

    @property
    def adc_gain(self):
        return self._adc_gain

    @adc_gain.setter
    def adc_gain(self, value):
        assert value in [2/3, 2, 4, 8, 16]
        self._adc_gain = value
        self.ads_current = ads.ADS1115(self.controller.bus, gain=self.adc_gain, data_rate=860,
                                       address=self.ads_current_address)
        self.exec_logger.debug(f'Setting TX ADC gain to {value}')

    def adc_gain_auto(self):
        gain = _gain_auto(AnalogIn(self.ads_current, ads.P0))
        self.exec_logger.debug(f'Setting TX ADC gain automatically to {gain}')
        self.adc_gain = gain

    def current_pulse(self, **kwargs):
        super().current_pulse(**kwargs)
        self.exec_logger.warning(f'Current pulse is not implemented for the {TX_CONFIG["model"]} board')

    @property
    def current(self):
        """ Gets the current IAB in Amps
        """
        return AnalogIn(self.ads_current, ads.P0).voltage * 1000. / (50 * TX_CONFIG['R_shunt'])  # noqa measure current

    @ current.setter
    def current(self, value):
        assert TX_CONFIG['current_min'] <= value <= TX_CONFIG['current_max']
        self.exec_logger.warning(f'Current pulse is not implemented for the {TX_CONFIG["model"]} board')

    def inject(self, state='on'):
        super().inject(state=state)
        if state=='on':
            self.DPS.write_register(0x09, 1)  # DPS5005 on
        else:
            self.DPS.write_register(0x09, 0)  # DPS5005 off

    @property
    def polarity(self):
        return super().polarity

    @polarity.setter
    def polarity(self, value):
        super().polarity(value)
        if value==1:
            self.pin0.value = True
            self.pin1.value = False
        elif value==-1:
            self.pin0.value = False
            self.pin1.value = True
        else:
            self.pin0.value = False
            self.pin1.value = False
        #time.sleep(0.001) # TODO: check max switching time of relays

    @property
    def voltage(self):
        return self._voltage
    @voltage.setter
    def voltage(self, value):
        if value > TX_CONFIG['voltage_max']:
            self.exec_logger.warning(f'Sorry, cannot inject more than {TX_CONFIG["voltage_max"]} V, '
                                     f'set it back to {TX_CONFIG["default_voltage"]} V (default value).')
            value = TX_CONFIG['default_voltage']
        self.DPS.write_register(0x0000, value, 2)

    def turn_off(self):
        super().turn_off()
        self.pin2.value = False
        self.pin3.value = False

    def turn_on(self):
        super().turn_on()
        self.pin2.value = True
        self.pin3.value = True

    def voltage_pulse(self, voltage=TX_CONFIG['default_voltage'], length=None, polarity=None):
        """ Generates a square voltage pulse

        Parameters
        ----------
        voltage: float, optional
            Voltage to apply in volts, tx_v_def is applied if omitted.
        length: float, optional
            Length of the pulse in seconds
        polarity: 1,0,-1
            Polarity of the pulse
        """

        if length is None:
            length = self.inj_time
        if polarity is None:
            polarity = self.polarity
        self.polarity = polarity
        self.voltage(voltage)
        self.exec_logger.debug(f'Voltage pulse of {polarity*voltage:.3f} V for {length:.3f} s')
        self.inject(state='on')
        time.sleep(length)
        self.inject(state='off')

class Rx(RxAbstract):
    def __init__(self, **kwargs):
        self.controller = kwargs.pop('controller', controller_module.Controller())
        self._adc_gain = [2/3, 2/3]
        super().__init__(**kwargs)
        self.ads_voltage_address = 0x49
        # ADS1115 for voltage measurement (MN)
        self.ads_voltage = ads.ADS1115(self.controller.bus, gain=2/3, data_rate=860, address=self.ads_voltage_address)


    @property
    def adc_gain(self):
        return self._adc_gain


    @adc_gain.setter
    def adc_gain(self, value):
        assert value in [2 / 3, 2, 4, 8, 16]
        self._adc_gain = value
        self.ads_voltage = ads.ADS1115(self.controller.bus, gain=self.adc_gain, data_rate=860,
                                       address=self.ads_voltage_address)
        self.exec_logger.debug(f'Setting RX ADC gain to {value}')


    def adc_gain_auto(self):
        gain_0 = _gain_auto(AnalogIn(self.ads_voltage, ads.P0))
        gain_2 = _gain_auto(AnalogIn(self.ads_voltage, ads.P2))
        gain = np.min([gain_0, gain_2])[0]
        self.exec_logger.debug(f'Setting TX ADC gain automatically to {gain}')
        self.adc_gain = gain

    @property
    def voltage(self):
        """ Gets the voltage VMN in Volts
        """
        u0 = AnalogIn(self.ads_voltage, ads.P0).voltage * 1000.
        u2 = AnalogIn(self.ads_voltage, ads.P2).voltage * 1000.
        self.exec_logger.debug(f'Reading voltages {u0} V and {u2} V on RX. Returning {np.max([u0, u2])} V')
        return np.max([u0,u2])