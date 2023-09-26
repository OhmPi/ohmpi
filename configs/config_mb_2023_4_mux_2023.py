import logging
from ohmpi.utils import get_platform

from paho.mqtt.client import MQTTv31

_, on_pi = get_platform()
# DEFINE THE ID OF YOUR OhmPi
ohmpi_id = '0001' if on_pi else 'XXXX'
# DEFINE YOUR MQTT BROKER (DEFAULT: 'localhost')
mqtt_broker = 'localhost' if on_pi else 'NAME_YOUR_BROKER_WHEN_IN_SIMULATION_MODE_HERE'
# DEFINE THE SUFFIX TO ADD TO YOUR LOGS FILES
logging_suffix = ''

# OhmPi configuration
OHMPI_CONFIG = {
    'id': ohmpi_id,  # Unique identifier of the OhmPi board (string)
    'settings': 'ohmpi_settings.json',  # INSERT YOUR FAVORITE SETTINGS FILE HERE
}

HARDWARE_CONFIG = {
    'ctl': {'model': 'raspberry_pi'},
    'pwr': {'model': 'pwr_batt', 'voltage': 12.},
    'tx':  {'model': 'mb_2023_0_X',
             'mcp_board_address': 0x20,
             'voltage_max': 12.,  # Maximum voltage supported by the TX board [V]
             'current_max': 4800 / 50 / 2,  # Maximum current supported by the TX board [mA]
             'r_shunt': 2  # Shunt resistance in Ohms
            },
    'rx':  {'model': 'mb_2023_0_X',
             'coef_p2': 2.50,  # slope for current conversion for ADS.P2, measurement in V/V
             'nb_samples': 20,  # Max value 10 # was named integer before...
            },
    'mux':  # default properties are system properties that will be
            # overwritten by board properties defined at the board level within the board model file
            # both will be overwritten by properties specified in the board dict below. Use with caution...
            {'boards':
                    {'mux_1':
                         {'model': 'mux_2023_0_X',  # 'ohmpi_i2c_mux64_v1.01',
                          'tca_address': 0x70,
                          'roles': {'A': 'X'},
                          'cabling': {(i, j): ('mux_1', i) for j in ['A'] for i in range(1, 65)},
                          'voltage_max': 12.},
                     'mux_2':
                         {'model': 'mux_2023_0_X',  # 'ohmpi_i2c_mux64_v1.01',
                          'tca_address': 0x71,
                          'roles': {'B': 'X'},
                          'cabling': {(i, j): ('mux_2', i) for j in ['B'] for i in range(1, 65)},
                          'voltage_max': 12.},
                     'mux_3':
                         {'model': 'mux_2023_0_X',  # 'ohmpi_i2c_mux64_v1.01',
                          'tca_address': 0x72,
                          'roles': {'M': 'X'},
                          'cabling': {(i, j): ('mux_3', i) for j in ['M'] for i in range(1, 65)},
                          'voltage_max': 12.},
                     'mux_4':
                         {'model': 'mux_2023_0_X',  # 'ohmpi_i2c_mux64_v1.01',
                          'tca_address': 0x73,
                          'roles': {'N': 'X'},
                          'cabling': {(i, j): ('mux_4', i) for j in ['N'] for i in range(1, 65)},
                          'voltage_max': 12.},
                     },
             'default': {'connection': 'i2c',
                         'voltage_max': 100.,
                         'current_max': 3.}
             }
}

# SET THE LOGGING LEVELS, MQTT BROKERS AND MQTT OPTIONS ACCORDING TO YOUR NEEDS
# Execution logging configuration
EXEC_LOGGING_CONFIG = {
    'logging_level': logging.INFO,
    'log_file_logging_level': logging.DEBUG,
    'logging_to_console': True,
    'file_name': f'exec{logging_suffix}.log',
    'max_bytes': 262144,
    'backup_count': 30,
    'when': 'd',
    'interval': 1
}

# Data logging configuration
DATA_LOGGING_CONFIG = {
    'logging_level': logging.INFO,
    'logging_to_console': True,
    'file_name': f'data{logging_suffix}.log',
    'max_bytes': 16777216,
    'backup_count': 1024,
    'when': 'd',
    'interval': 1
}

# State of Health logging configuration (For a future release)
SOH_LOGGING_CONFIG = {
    'logging_level': logging.INFO,
    'logging_to_console': True,
    'log_file_logging_level': logging.DEBUG,
    'file_name': f'soh{logging_suffix}.log',
    'max_bytes': 16777216,
    'backup_count': 1024,
    'when': 'd',
    'interval': 1
}

# MQTT logging configuration parameters
MQTT_LOGGING_CONFIG = {
    'hostname': mqtt_broker,
    'port': 1883,
    'qos': 2,
    'retain': False,
    'keepalive': 60,
    'will': None,
    'auth': {'username': 'mqtt_user', 'password': 'mqtt_password'},
    'tls': None,
    'protocol': MQTTv31,
    'transport': 'tcp',
    'client_id': f'{OHMPI_CONFIG["id"]}',
    'exec_topic': f'ohmpi_{OHMPI_CONFIG["id"]}/exec',
    'exec_logging_level': logging.DEBUG,
    'data_topic': f'ohmpi_{OHMPI_CONFIG["id"]}/data',
    'data_logging_level': DATA_LOGGING_CONFIG['logging_level'],
    'soh_topic': f'ohmpi_{OHMPI_CONFIG["id"]}/soh',
    'soh_logging_level': SOH_LOGGING_CONFIG['logging_level']
}

# MQTT control configuration parameters
MQTT_CONTROL_CONFIG = {
    'hostname': mqtt_broker,
    'port': 1883,
    'qos': 2,
    'retain': False,
    'keepalive': 60,
    'will': None,
    'auth': {'username': 'mqtt_user', 'password': 'mqtt_password'},
    'tls': None,
    'protocol': MQTTv31,
    'transport': 'tcp',
    'client_id': f'{OHMPI_CONFIG["id"]}',
    'ctrl_topic': f'ohmpi_{OHMPI_CONFIG["id"]}/ctrl'
}
