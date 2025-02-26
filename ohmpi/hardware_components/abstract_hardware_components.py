from abc import ABC, abstractmethod
import numpy as np
import time
from threading import Event, Barrier, BrokenBarrierError
from ohmpi.logging_setup import create_stdout_logger
from ohmpi.utils import enforce_specs

SPECS = {'ctl': {'model': {'default': 'unknown CTL hardware'},
                 'exec_logger': {'default': None},
                 'soh_logger': {'default': None},
                 'connect': {'default': True},
                 'connection': {'default': None}},
         'pwr': {'model': {'default': 'unknown PWR hardware'},
                 'exec_logger': {'default': None},
                 'soh_logger': {'default': None},
                 'current_min': {'default': 0.},
                 'current_max': {'default': 0.},
                 'voltage_min': {'default': 0.},
                 'voltage_max': {'default': 0.},
                 'power_max': {'default': 0.},
                 'voltage_adjustable': {'default': False},
                 'current_adjustable': {'default': False},
                 'connect': {'default': True},
                 'connection': {'default': None},
                 'interface_name':{'default': None}},
         'mux': {'model': {'default': 'unknown MUX hardware'},
                 'exec_logger': {'default': None},
                 'soh_logger': {'default': None},
                 'id': {'default': None},
                 'connect': {'default': True},
                 'connection': {'default': None},
                 'cabling': {'default': None},
                 'addresses': {'default': None},
                 'barrier': {'default': Barrier(1)},
                 'activation_delay': {'default': 0.},  # in s
                 'release_delay': {'default': 0.}},  # in s
        'tx':   {'model': {'default':  'unknown TX hardware'},
                 'injection_duration': {'default': 1.},
                 'exec_logger': {'default': None},
                 'soh_logger': {'default': None},
                 'connect': {'default': True},
                 'connection': {'default': None},
                 'pwr': {'default': None},
                 'latency': {'default': 0.},
                 'tx_sync': {'default': Event()}},
        'rx':   {'model': {'default':  'unknown RX hardware'},
                 'exec_logger': {'default': None},
                 'soh_logger': {'default': None},
                 'connect': {'default': True},
                 'connection': {'default': None},
                 'sampling_rate': {'default': 1., 'max': np.inf},
                 'latency': {'default': 0.},
                 'voltage_max': {'default': 0.},
                 'bias': {'default': 0.},
                 'vmn_hardware_offset': {'default': 0.}}
        }


class CtlAbstract(ABC):
    """CTlAbstract Class
    Abstract class for controller"""
    def __init__(self, **kwargs):
        for key in SPECS['ctl'].keys():
            kwargs = enforce_specs(kwargs, SPECS['ctl'], key)
        self.model = kwargs['model']
        self.interfaces = dict()
        self.interfaces['none'] = None
        self.exec_logger = kwargs['exec_logger']
        if self.exec_logger is None:
            self.exec_logger = create_stdout_logger('exec_ctl')
        self.soh_logger = kwargs['soh_logger']
        if self.soh_logger is None:
            self.soh_logger = create_stdout_logger('soh_ctl')
        self.exec_logger.debug(f'{self.model} Ctl initialization')
        self._cpu_temp_available = False
        self.max_cpu_temp = np.inf
        self.connect = kwargs['connect']
        self.connection = kwargs['connection']
        self.specs = kwargs

    @property
    def cpu_temperature(self):
        if not self._cpu_temp_available:
            self.exec_logger.warning(f'CPU temperature reading is not available for {self.model}')
            cpu_temp = np.nan
        else:
            cpu_temp = self._cpu_temp
            if cpu_temp > self.max_cpu_temp:
                self.soh_logger.warning(f'CPU temperature of {self.model} is over the limit!')
        return cpu_temp

    @property
    @abstractmethod
    def _cpu_temp(self):
        pass


class PwrAbstract(ABC):
    """PwrAbstract Class
        Abstract class for Power module"""
    def __init__(self, **kwargs):
        for key in SPECS['pwr'].keys():
            kwargs = enforce_specs(kwargs, SPECS['pwr'], key)
        self.model = kwargs['model']
        self.exec_logger = kwargs['exec_logger']
        if self.exec_logger is None:
            self.exec_logger = create_stdout_logger('exec_pwr')
        self.soh_logger = kwargs['soh_logger']
        if self.soh_logger is None:
            self.soh_logger = create_stdout_logger('soh_pwr')
        self.voltage_adjustable = kwargs['voltage_adjustable']
        self._voltage = np.nan
        self.current_adjustable = kwargs['current_adjustable']
        self._current = np.nan
        self._pwr_state = 'off'
        self._current_min = kwargs['current_min']
        self._current_max = kwargs['current_max']
        self._voltage_min = kwargs['voltage_min']
        self._voltage_max = kwargs['voltage_max']
        self.switchable = False
        self.interface_name = kwargs['interface_name']
        self.connection = kwargs['connection']
        self._battery_voltage = np.nan
        self._pwr_discharge_latency = np.nan
        self.connect = kwargs['connect']
        self.specs = kwargs

    @property
    @abstractmethod
    def current(self):
        # add actions to read the DPS current
        return self._current

    @current.setter
    @abstractmethod
    def current(self, value, **kwargs):
        # add actions to set the DPS current
        pass
    #
    # @abstractmethod
    # def turn_off(self):
    #     self.exec_logger.debug(f'Switching {self.model} off')
    #     self._state = 'off'
    #
    # @abstractmethod
    # def turn_on(self):
    #     self.exec_logger.debug(f'Switching {self.model} on')
    #     self._state = 'on'

    @property
    def pwr_state(self):
        return self._pwr_state

    @pwr_state.setter
    def pwr_state(self, state):
        if state == 'on':
            self._pwr_state = 'on'
            self.exec_logger.debug(f'{self.model} cannot be switched on')
        elif state == 'off':
            self._pwr_state = 'off'
            self.exec_logger.debug(f'{self.model} cannot be switched off')

    def reload_settings(self):
        pass

    @property
    @abstractmethod
    def voltage(self):
        # add actions to read the DPS voltage
        return self._voltage

    @voltage.setter
    @abstractmethod
    def voltage(self, value):
        assert isinstance(value, float)
        if not self.voltage_adjustable:
            self.exec_logger.debug(f'Voltage cannot be set on {self.model}...')
        else:
            assert self._voltage_min <= value <= self._voltage_max
            # add actions to set the DPS voltage
            self._voltage = value

    def battery_voltage(self):
        # add actions to read the DPS voltage
        self.exec_logger.debug(f'Battery voltage cannot be read on {self.model}...')
        return self._battery_voltage

    def reset_voltage(self):
        if not self.voltage_adjustable:
            self.exec_logger.debug(f'Voltage cannot be set on {self.model}...')
        else:
            self.voltage = self._voltage_min


class MuxAbstract(ABC):
    """MUXAbstract Class
        Abstract class for MUX"""
    def __init__(self, **kwargs):
        for key in SPECS['mux'].keys():
            kwargs = enforce_specs(kwargs, SPECS['mux'], key)
        self.model = kwargs['model']
        self.exec_logger = kwargs['exec_logger']
        if self.exec_logger is None:
            self.exec_logger = create_stdout_logger('exec_mux')
        self.soh_logger = kwargs['soh_logger']
        if self.soh_logger is None:
            self.soh_logger = create_stdout_logger('soh_mux')
        self.board_id = kwargs['id']
        if self.board_id is None:
            self.exec_logger.error(f'MUX {self.model} should have an id !')
        self.exec_logger.debug(f'MUX {self.model}: {self.board_id} initialization')
        self.connection = kwargs['connection']
        cabling = kwargs['cabling']
        self.cabling = {}
        if cabling is not None:
            for k, v in cabling.items():
                if v[0] == self.board_id:
                    self.cabling.update({k: (v[1], k[1])})
        self.exec_logger.debug(f'{self.board_id} cabling: {self.cabling}')
        self.addresses = kwargs['addresses']
        self._barrier = kwargs['barrier']
        self._activation_delay = kwargs['activation_delay']
        self._release_delay = kwargs['release_delay']
        self.connect = kwargs['connect']
        self.specs = kwargs

    @abstractmethod
    def _get_addresses(self):
        pass

    @property
    def barrier(self):
        return self._barrier

    @barrier.setter
    def barrier(self, value):
        assert isinstance(value, Barrier)
        self._barrier = value

    @abstractmethod
    def reset(self):
        pass

    def switch(self, elec_dict=None, state='off', bypass_check=False, bypass_ab_check=False):  # TODO: generalize for other roles
        """Switch a given list of electrodes with different roles.
        Electrodes with a value of 0 will be ignored.

        Parameters
        ----------
        elec_dict : dictionary, optional
            Dictionary of the form: {role: [list of electrodes]}.
        state : str, optional
            Either 'on' or 'off'.
        bypass_check: bool, optional
            Bypasses checks for A==M or A==M or B==M or B==N (i.e. used for rs-check)
        bypass_ab_check: bool, optional
            Bypasses checks for A==B (i.e. used for testing r_shunt). Should be used with caution.
        """
        status = True
        if elec_dict is not None:
            self.exec_logger.debug(f'Switching {self.model} ')
            # check to prevent A == B (SHORT-CIRCUIT)
            if 'A' in elec_dict.keys() and 'B' in elec_dict.keys():
                if bypass_ab_check:
                    self.exec_logger.warning(f'Bypassing AB check: {bypass_ab_check}')
                else:
                    out = np.in1d(elec_dict['A'], elec_dict['B'])
                    if out.any() and state == 'on':  # noqa
                        self.exec_logger.error('Trying to switch on some electrodes with both A and B roles. '
                                               'This would create a short-circuit! Switching aborted.')
                        status = False
                        return status

            # check that none of M or N are the same as A or B
            # as to prevent burning the MN part which cannot take
            # the full voltage of the DPS
            if 'A' in elec_dict.keys() and 'B' in elec_dict.keys() and 'M' in elec_dict.keys() \
                    and 'N' in elec_dict.keys():
                if bypass_check:
                    self.exec_logger.debug(f'Bypassing :{bypass_check}')
                elif (np.in1d(elec_dict['M'], elec_dict['A']).any()  # noqa
                        or np.in1d(elec_dict['M'], elec_dict['B']).any()  # noqa
                        or np.in1d(elec_dict['N'], elec_dict['A']).any()  # noqa
                        or np.in1d(elec_dict['N'], elec_dict['B']).any()) and state=='on':  # noqa
                    self.exec_logger.error('Trying to switch on some electrodes with both M or N role and A or B role. '
                                           'This could create an over-voltage in the RX! Switching aborted.')
                    self.barrier.abort()
                    status = False
                    return status

            # if all ok, then wait for the barrier to open, then switch the electrodes
            self.exec_logger.debug(f'{self.board_id} waiting to switch.')
            try:
                self.barrier.wait()
                for role in elec_dict:
                    for elec in elec_dict[role]:
                        if elec > 0:  # Is this condition related to electrodes to infinity?
                            if (elec, role) in self.cabling.keys():
                                self.switch_one(elec, role, state)
                                status &= True
                            else:
                                self.exec_logger.debug(f'{self.board_id} skipping switching {(elec, role)} because it '
                                                       f'is not in board cabling.')
                                status = False
                self.exec_logger.debug(f'{self.board_id} switching done.')
            except BrokenBarrierError:
                self.exec_logger.debug(f'Barrier error {self.board_id} switching aborted.')
                status = False
        else:
            self.exec_logger.warning(f'Missing argument for {self.model}.switch: elec_dict is None.')
            status = False
        if state == 'on':
            time.sleep(self._activation_delay)
        elif state == 'off':
            time.sleep(self._release_delay)
        return status

    @abstractmethod
    def switch_one(self, elec=None, role=None, state=None):
        """Switches one single relay.

        Parameters
        ----------
        elec :
        role :
        state : str, optional
            Either 'on' or 'off'.
        """
        self.exec_logger.debug(f'switching {state} electrode {elec} with role {role}')

    def test(self, elec_dict, activation_time=1.):
        """Method to test the multiplexer.

        Parameters
        ----------
        elec_dict : dictionary, optional
            Dictionary of the form: {role: [list of electrodes]}.
        activation_time : float, optional
            Time in seconds during which the relays are activated.
        """
        self.exec_logger.debug(f'Starting {self.model} test...')
        self.reset()

        for role in elec_dict.keys():
            for elec in elec_dict[role]:
                self.switch_one(elec, role, 'on')
                time.sleep(activation_time)
                self.switch_one(elec, role, 'off')
                time.sleep(activation_time)
        self.exec_logger.debug('Test finished.')


class TxAbstract(ABC):
    """TxAbstract Class
        Abstract class for TX module"""
    def __init__(self, **kwargs):
        for key in SPECS['tx'].keys():
            kwargs = enforce_specs(kwargs, SPECS['tx'], key)

        self.model = kwargs['model']
        self.exec_logger = kwargs['exec_logger']
        if self.exec_logger is None:
            self.exec_logger = create_stdout_logger('exec_tx')
        self.soh_logger = kwargs['soh_logger']
        if self.soh_logger is None:
            self.soh_logger = create_stdout_logger('soh_tx')
        self.connection = kwargs['connection']
        self.pwr = kwargs['pwr']
        self._voltage = 0.
        self._polarity = 0
        self._injection_duration = kwargs['injection_duration']
        self._gain = 1.
        self._latency = kwargs['latency']
        self.tx_sync = kwargs['tx_sync']
        self.exec_logger.debug(f'{self.model} TX initialization')
        self._pwr_state = 'off'
        self.connect = kwargs['connect']
        self.specs = kwargs
        self._measuring = 'off'


    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, value):
        """
        Set gain on RX
        Parameters
        ----------
        value: float
        """
        self._gain = value
        self.exec_logger.debug(f'Setting TX gain to {value}')

    @property
    @abstractmethod
    def current(self):
        """ Gets the current IAB in Amps
        """
        pass

    @current.setter
    @abstractmethod
    def current(self, value):
        pass

    @abstractmethod
    def current_pulse(self, **kwargs):
        pass

    @abstractmethod
    def inject(self, polarity=1, injection_duration=None, switch_pwr=False):
        """Abstract method to define injection.

        Parameters
        ----------
        polarity: int, default 1
            Injection polarity, can be eiter  1, 0 or -1.
        injection_duration: float, default None
            Injection duration in seconds.
        switch_pwr: bool
            Switch on and off tx.pwr.
        """
        assert polarity in [-1, 0, 1]
        if injection_duration is None:
            injection_duration = self._injection_duration
        if np.abs(polarity) > 0:
            if switch_pwr:
                self.pwr.pwr_state('on')
            self.tx_sync.set()
            time.sleep(injection_duration)
            self.tx_sync.clear()
            if switch_pwr:
                self.pwr.pwr_state('off')
        else:
            self.tx_sync.set()
            if switch_pwr:
                self.pwr.pwr_state('off')
            time.sleep(injection_duration)
            self.tx_sync.clear()

    @property
    def injection_duration(self):
        return self._injection_duration

    @injection_duration.setter
    def injection_duration(self, value):
        assert isinstance(value, float)
        assert value > 0.
        self._injection_duration = value

    @property
    def latency(self):
        """ Gets the Tx latency """
        return self._latency

    @latency.setter
    def latency(self, value):
        """ Sets the Tx latency """
        assert isinstance(value, float)
        assert value >= 0.
        self._latency = value

    @property
    def measuring(self):
        return self._measuring

    @measuring.setter
    def measuring(self, mode="off"):
        self._measuring = mode

    def discharge_pwr(self, latency=None):
        if self.pwr.voltage_adjustable:
            if latency is None:
                latency = self.pwr._pwr_discharge_latency
            self.exec_logger.debug(f'Pwr discharge initiated for {latency} s')

            time.sleep(latency)

        else:
            self.exec_logger.debug(f'Pwr discharge not supported by {self.pwr.model}')

    @property
    def polarity(self):
        return self._polarity

    @polarity.setter
    @abstractmethod
    def polarity(self, polarity):
        """
        Sets polarity value
        Parameters
        ----------
        polarity: int
            Either -1, 0 or 1.
        """
        assert polarity in [-1, 0, 1]
        self._polarity = polarity

    @property
    @abstractmethod
    def tx_bat(self):
        pass

    @property
    def voltage(self):
        """ Gets the voltage VAB in Volts
        """
        return self._voltage

    @voltage.setter
    def voltage(self, value):
        assert value >= 0.
        self._voltage = value
        self.pwr.voltage = value

    def voltage_pulse(self, voltage=0., length=None, polarity=1):
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
            length = self.injection_duration
        self.pwr.voltage = voltage
        self.exec_logger.debug(f'Voltage pulse of {polarity * self.pwr.voltage:.3f} V for {length:.3f} s')
        self.inject(polarity=polarity, injection_duration=length)

    @property
    def pwr_state(self):
        return self._pwr_state

    @pwr_state.setter
    def pwr_state(self, state):
        if state == 'on':
            self._pwr_state = 'on'
            if not self.pwr.switchable:
                self.exec_logger.debug(f'{self.model} cannot switch on power source')
            self.pwr.reload_settings()
        elif state == 'off':
            self._pwr_state = 'off'
            self.exec_logger.debug(f'{self.model} cannot switch off power source')

    def reset_gain(self):
        self.gain = 1.


class RxAbstract(ABC):
    """RXAbstract Class
        Abstract class for RX"""
    def __init__(self, **kwargs):
        for key in SPECS['rx'].keys():
            kwargs = enforce_specs(kwargs, SPECS['rx'], key)
        self.model = kwargs['model']
        self.exec_logger = kwargs['exec_logger']
        if self.exec_logger is None:
            self.exec_logger = create_stdout_logger('exec_rx')
        self.soh_logger = kwargs['soh_logger']
        if self.soh_logger is None:
            self.soh_logger = create_stdout_logger('soh_rx')
        self.connection = kwargs['connection']
        self._sampling_rate = kwargs['sampling_rate']
        self.exec_logger.debug(f'{self.model} RX initialization')
        self._voltage_max = kwargs['voltage_max']
        self._gain = 1.
        self._max_sampling_rate = np.inf
        self._latency = kwargs['latency']
        self._bias = kwargs['bias']
        self._vmn_hardware_offset = kwargs['vmn_hardware_offset']
        self.connect = kwargs['connect']
        self.specs = kwargs

    @property
    def bias(self):
        """ Gets the RX bias """
        return self._bias

    @bias.setter
    def bias(self, value):
        """ Sets the Rx bias """
        assert isinstance(value, float)
        self._bias = value

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, value):
        """
        Sets gain on RX
        Parameters
        ----------
        value: float
        """
        self._gain = value
        self.exec_logger.debug(f'Setting RX gain to {value}')

    @abstractmethod
    def gain_auto(self):
        pass

    @property
    def latency(self):
        """ Gets the Rx latency """
        return self._latency

    @latency.setter
    def latency(self, value):
        """ Sets the Rx latency """
        assert isinstance(value, float)
        assert value >= 0.
        self._latency = value

    def reset_gain(self):
        self.gain = 1.

    @property
    def sampling_rate(self):
        return self._sampling_rate

    @sampling_rate.setter
    def sampling_rate(self, value):
        """
        Sets sampling rate
        Parameters
        ----------
        value: float, in Hz
        """
        assert value > 0.
        if value > self._max_sampling_rate:
            self.exec_logger.warning(f'{self} maximum sampling rate is {self._max_sampling_rate}. '
                                     f'Setting sampling rate to the highest allowed value.')
            value = self._max_sampling_rate
        self._sampling_rate = value
        self.exec_logger.debug(f'Sampling rate set to {value}')

    @property
    @abstractmethod
    def voltage(self):
        """ Gets the voltage VMN in Volts """
        pass
