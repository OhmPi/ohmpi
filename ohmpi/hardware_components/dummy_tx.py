from ohmpi.config import HARDWARE_CONFIG
import time
import os
import numpy as np
from ohmpi.hardware_components import TxAbstract

TX_CONFIG = HARDWARE_CONFIG['tx']

# hardware characteristics and limitations
# voltages are given in mV, currents in mA, sampling rates in Hz and data_rate in S/s
SPECS = {'rx': {'model': {'default': os.path.basename(__file__).rstrip('.py')},
                'sampling_rate': {'min': 2., 'default': 10., 'max': 100.},
                'data_rate': {'default': 860.},
                'bias':  {'min': -5000., 'default': 0., 'max': 5000.},
                'coef_p2': {'default': 1.00},
                'mcp_address': {'default': 0x27},
                'ads_address': {'default': 0x49},
                'voltage_min': {'default': 10.0},
                'voltage_max': {'default': 5000.0},  # [mV]
                'dg411_gain_ratio': {'default': 1/2},  # lowest resistor value over sum of resistor values
                'vmn_hardware_offset': {'default': 2500.},
                },
         'tx': {'model': {'default': os.path.basename(__file__).rstrip('.py')},
                'adc_voltage_min': {'default': 10.},  # Minimum voltage value used in vmin strategy
                'adc_voltage_max': {'default': 4500.},  # Maximum voltage on ads1115 used to measure current
                'voltage_max': {'min': 0., 'default': 12., 'max': 50.},  # Maximum input voltage
                'data_rate': {'default': 860.},
                'mcp_address': {'default': 0x21},
                'ads_address': {'default': 0x48},
                'compatible_power_sources': {'default': ['pwr_batt', 'dps5005']},
                'r_shunt':  {'min': 0.001, 'default': 2.},
                'activation_delay': {'default': 0.010},  # Max turn on time of OMRON G5LE-1 5VDC relays
                'release_delay': {'default': 0.005},  # Max turn off time of OMRON G5LE-1 5VDC relays = 1ms
                'pwr_latency': {'default': 4.}
                }}

# ADC for current
current_adc_voltage_min = 10.  # mV
current_adc_voltage_max = 4500. # mV

# DPS
dps_voltage_max = 50.  # V
dps_default_voltage = 5.  # V
dps_switch_on_warmup = 4.  # seconds
tx_low_battery = 12. # V

TX_CONFIG['current_min'] = np.min([current_adc_voltage_min / (TX_CONFIG['r_shunt'] * 50), TX_CONFIG.pop('current_min', np.inf)])  # mA
TX_CONFIG['current_max'] = np.min([current_adc_voltage_max / (TX_CONFIG['r_shunt'] * 50), TX_CONFIG.pop('current_max', np.inf)])  # mA
TX_CONFIG['voltage_max'] = np.min([dps_voltage_max, TX_CONFIG.pop('voltage_max', np.inf)])  # V
TX_CONFIG['default_voltage'] = np.min([TX_CONFIG.pop('default_voltage', dps_default_voltage), TX_CONFIG['voltage_max']])  # V
TX_CONFIG['dps_switch_on_warm_up'] = TX_CONFIG.pop('dps_switch_on_warmup', dps_switch_on_warmup)
TX_CONFIG['low_battery'] = TX_CONFIG.pop('low_battery', tx_low_battery)

class Tx(TxAbstract):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._voltage = kwargs.pop('voltage', TX_CONFIG['default_voltage'])

        self._adc_gain = 1.

        class Pin(object):
            def __init__(self, val):
                self.value = val
        
        self.pin0 = Pin(False)
        self.pin1 = Pin(False)

        self.polarity = 0
        time.sleep(TX_CONFIG['dps_switch_on_warm_up'])
        self.exec_logger.info(f'TX battery: {self.tx_bat:.1f} V')

    def inject(self, polarity=1, injection_duration=None, switch_pwr=False):
        self.polarity = polarity
        # TxAbstract.inject(self, polarity=polarity, injection_duration=injection_duration, switch_pwr=switch_pwr)

    @property
    def adc_gain(self):
        return self._adc_gain

    @adc_gain.setter
    def adc_gain(self, value):
        self._adc_gain = value
        self.exec_logger.debug(f'Setting TX ADC gain to {value}')

    def adc_gain_auto(self):
        gain = 1.
        self.exec_logger.debug(f'Setting TX ADC gain automatically to {gain}')
        self.adc_gain = gain
    
    def gain_auto(self):
        self._adc_gain_auto()

    def current_pulse(self, **kwargs):
        super().current_pulse(**kwargs)
        self.exec_logger.warning(f'Current pulse is not implemented for the {TX_CONFIG["model"]} board')

    @property
    def current(self):
        """ Gets the current IAB in Amps
        """
        current = np.abs(np.random.normal(0.7, 0.2))
        self.exec_logger.debug(f'Reading random current on TX. Returning {current} A')
        return current

    @ current.setter
    def current(self, value):
        assert TX_CONFIG['current_min'] <= value <= TX_CONFIG['current_max']
        self.exec_logger.warning(f'Current pulse is not implemented for the {TX_CONFIG["model"]} board')

    @property
    def voltage(self):
        return self._voltage
    @voltage.setter
    def voltage(self, value):
        if value > TX_CONFIG['voltage_max']:
            self.exec_logger.warning(f'Sorry, cannot inject more than {TX_CONFIG["voltage_max"]} V, '
                                     f'set it back to {TX_CONFIG["default_voltage"]} V (default value).')
            value = TX_CONFIG['default_voltage']
        if value < 0.:
            self.exec_logger.warning(f'Voltage should be given as a positive number. '
                                     f'Set polarity to -1 to reverse voltage...')
            value = np.abs(value)
        self._voltage=value

    @property
    def tx_bat(self):
        tx_bat = np.random.uniform(10.9, 13.4)
        if tx_bat < 12.:
            self.soh_logger.debug(f'Low TX Battery: {tx_bat:.1f} V')
        return tx_bat
    
    @property
    def polarity(self):
        return self._polarity

    @polarity.setter
    def polarity(self, polarity):
        assert polarity in [-1, 0, 1]
        self._polarity = polarity
        if polarity == 1:
            self.pin0.value = True
            self.pin1.value = False
        elif polarity == -1:
            self.pin0.value = False
            self.pin1.value = True
        else:
            self.pin0.value = False
            self.pin1.value = False

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
        kwargs = locals()
        kwargs.pop('self')
        kwargs.pop('__class__')
        print(kwargs)
        super().voltage_pulse(**kwargs)

