from ohmpi.hardware_components.abstract_hardware_components import PwrAbstract
import numpy as np
import os
from ohmpi.utils import enforce_specs

# hardware characteristics and limitations
SPECS = {'model': {'default': os.path.basename(__file__).rstrip('.py')},
         'voltage': {'default': 12., 'max': 12., 'min': 12.},
         }


class Pwr(PwrAbstract):
    def __init__(self, **kwargs):
        if 'model' not in kwargs.keys():
            for key in SPECS.keys():
                kwargs = enforce_specs(kwargs, SPECS, key)
            subclass_init = False
        else:
            subclass_init = True
        voltage = kwargs.pop('voltage', 12.)
        super().__init__(**kwargs)
        self.voltage_adjustable = False
        self._voltage = voltage
        self.current_adjustable = False
        self._current = np.nan
        self._state = 'on'

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value, **kwargs):
        self.exec_logger.debug(f'Current cannot be set on {self.model}')

    def turn_off(self):
        self.exec_logger.debug(f'{self.model} cannot be turned off')

    def turn_on(self):
        self.exec_logger.debug(f'{self.model} is always on')

    @property
    def voltage(self):
        return PwrAbstract.voltage.fget(self)

    @voltage.setter
    def voltage(self, value):
        PwrAbstract.voltage.fset(self, value)