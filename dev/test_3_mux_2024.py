import time
from ohmpi.utils import change_config
from ohmpi.plots import plot_exec_log
import logging
change_config('../configs/config_mb_2023_3_mux_2024.py', verbose=False)
from ohmpi.hardware_components.mux_2024_rev_0_0 import Mux, MUX_CONFIG
from ohmpi.hardware_components import raspberry_pi_i2c as ctl_module
from ohmpi.config import HARDWARE_CONFIG

stand_alone_mux = False
part_of_hardware_system = False
within_ohmpi = True
# Stand alone mux
if stand_alone_mux:
    mux_id = 'mux_04'
    first = 24
    print(MUX_CONFIG)
    MUX_CONFIG.update(HARDWARE_CONFIG['mux']['boards'][mux_id])
    MUX_CONFIG.update({'id': mux_id})
    MUX_CONFIG['ctl'] = ctl_module.Ctl()
    mux = Mux(**MUX_CONFIG)
    mux.switch_one(elec=1+first, role='M', state='on')
    time.sleep(1)
    mux.switch_one(elec=1+first, role='M', state='off')
    mux.switch({'A': [1], 'B': [2], 'M': [3], 'N': [4]}, state='on')
    time.sleep(2)
    # mux.switch({'A': [1], 'B': [4], 'M': [2], 'N': [3]}, state='off')
    mux.reset()
    mux.test({'A': [i+first for i in range(1, 9)], 'B': [i+first for i in range(1, 9)],
              'M': [i+first for i in range(1, 9)], 'N': [i+first for i in range(1, 9)]}, activation_time=.1)

# mux as part of a OhmPiHardware system
if part_of_hardware_system:
    from ohmpi.hardware_system import OhmPiHardware
    print('Starting test of mux as part of a OhmPiHardware system.')

    k = OhmPiHardware()
    k.exec_logger.setLevel(logging.DEBUG)

    # Test mux switching
    k.reset_mux()
    k.switch_mux(electrodes=[1, 4, 2, 3], roles=['A', 'B', 'M', 'N'], state='on')
    time.sleep(1.)
    k.switch_mux(electrodes=[1, 4, 2, 3], roles=['A', 'B', 'M', 'N'], state='off')

if within_ohmpi:
    from ohmpi.ohmpi import OhmPi
    print('Starting test of mux within OhmPi.')
    k = OhmPi()
    A, B, M, N = (10, 13, 12, 11)
    k.reset_mux()
    k._hw.switch_mux([A, B, M, N], state='on')
    k._hw.vab_square_wave(12.,12., cycles=2)
    k._hw.switch_mux([A, B, M, N], state='off')
    k._hw.calibrate_rx_bias()  # electrodes 1 4 2 3 should be connected to a reference circuit
    # print(f'Resistance: {k._hw.last_rho :.2f} ohm, dev. {k._hw.last_dev:.2f} %, rx bias: {k._hw.rx._bias:.2f} mV')
    # k._hw._plot_readings()
    k.run_measurement([A, B, M, N], injection_duration=6.)
    # k._hw._plot_readings()
    print(f'Resistance: {k._hw.last_rho :.2f} ohm, dev. {k._hw.last_dev:.2f} %, rx bias: {k._hw.rx._bias:.2f} mV')
    k._hw._plot_readings(save_fig=True)
    # plot_exec_log('ohmpi/logs/exec.log')
change_config('../configs/config_default.py', verbose=False)
