from ohmpi.hardware_components import CtlAbstract
import board  # noqa
import busio  # noqa
import os
from ohmpi.utils import get_platform
from gpiozero import CPUTemperature  # noqa


class Ctl(CtlAbstract):
    def __init__(self, **kwargs):
        kwargs.update({'board_name': os.path.basename(__file__).rstrip('.py')})
        super().__init__(**kwargs)
        self.bus = busio.I2C(board.SCL, board.SDA)  # noqa
        platform, on_pi = get_platform()
        assert on_pi
        self.board_name = platform
        self._cpu_temp_available = True
        self.max_cpu_temp = 85.  # °C

    @property
    def _cpu_temp(self):
        return CPUTemperature().temperature