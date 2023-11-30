import json
from ohmpi.config import (OHMPI_CONFIG,EXEC_LOGGING_CONFIG, DATA_LOGGING_CONFIG, SOH_LOGGING_CONFIG, MQTT_LOGGING_CONFIG,
                          MQTT_CONTROL_CONFIG)
from os import path, mkdir, statvfs
from time import gmtime
import logging
from ohmpi.mqtt_handler import MQTTHandler
from ohmpi.compressed_sized_timed_rotating_handler import CompressedSizedTimedRotatingFileHandler
import sys
from termcolor import colored
import traceback
from ohmpi.hardware_system import OhmPiHardware
from ohmpi.logging_setup import setup_loggers
from ohmpi.config import HARDWARE_CONFIG

logging_suffix = ''
MQTT_LOGGING_CONFIG.update({'test_topic': f'ohmpi_{OHMPI_CONFIG["id"]}/test'})
MQTT_LOGGING_CONFIG.update({'test_logging_level': logging.DEBUG})

TEST_LOGGING_CONFIG = {
    'logging_level': logging.INFO,
    'logging_to_console': True,
    'log_file_logging_level': logging.DEBUG,
    'file_name': f'test{logging_suffix}.log',
    'max_bytes': 16777216,
    'backup_count': 1024,
    'when': 'd',
    'interval': 1
}

for k, v in HARDWARE_CONFIG.items():
    if k == 'mux':
        HARDWARE_CONFIG[k]['default'].update({'connect': False})
    else:
        HARDWARE_CONFIG[k].update({'connect': False})

def test_i2c_devices_on_bus(i2c_addr, bus):
    i2c_addresses_on_bus = bus.scan()
    print(i2c_addresses_on_bus)
    if i2c_addr in i2c_addresses_on_bus:
        return True
    else:
        return False

def setup_test_logger(mqtt=True):
    msg = ''
    # Message logging setup
    log_path = path.join(path.dirname(__file__), 'logs')
    if not path.isdir(log_path):
        mkdir(log_path)
    test_log_filename = path.join(log_path, TEST_LOGGING_CONFIG['file_name'])

    test_logger = logging.getLogger('test_logger')

    # TEST logging setup
    # Set message logging format and level
    log_format = '%(asctime)-15s | %(process)d | %(levelname)s: %(message)s'
    logging_to_console = TEST_LOGGING_CONFIG['logging_to_console']
    test_handler = CompressedSizedTimedRotatingFileHandler(test_log_filename,
                                                           max_bytes=TEST_LOGGING_CONFIG['max_bytes'],
                                                           backup_count=TEST_LOGGING_CONFIG['backup_count'],
                                                           when=TEST_LOGGING_CONFIG['when'],
                                                           interval=TEST_LOGGING_CONFIG['interval'])
    test_formatter = logging.Formatter(log_format)
    test_formatter.converter = gmtime
    test_formatter.datefmt = '%Y-%m-%d %H:%M:%S UTC'
    test_handler.setFormatter(test_formatter)
    test_logger.addHandler(test_handler)
    test_logger.setLevel(TEST_LOGGING_CONFIG['log_file_logging_level'])

    if logging_to_console:
        console_test_handler = logging.StreamHandler(sys.stdout)
        console_test_handler.setLevel(TEST_LOGGING_CONFIG['logging_level'])
        console_test_handler.setFormatter(test_formatter)
        test_logger.addHandler(console_test_handler)

    if mqtt:
        mqtt_settings = MQTT_LOGGING_CONFIG.copy()
        mqtt_test_logging_level = mqtt_settings.pop('test_logging_level', logging.DEBUG)
        [mqtt_settings.pop(i, None) for i in ['client_id', 'exec_topic', 'data_topic', 'test_topic',
                                              'data_logging_level', 'exec_logging_level']]
        mqtt_settings.update({'topic': MQTT_LOGGING_CONFIG['test_topic']})
        # TODO: handle the case of MQTT broker down or temporarily unavailable
        try:
            mqtt_test_handler = MQTTHandler(**mqtt_settings)
            mqtt_test_handler.setLevel(mqtt_test_logging_level)
            mqtt_test_handler.setFormatter(test_formatter)
            test_logger.addHandler(mqtt_test_handler)
            msg += colored(f"\n\u2611 Publishes execution as {MQTT_LOGGING_CONFIG['test_topic']} topic on the "
                           f"{MQTT_LOGGING_CONFIG['hostname']} broker", 'blue')
        except Exception as e:
            msg += colored(f'\nWarning: Unable to connect to test topic on broker\n{e}', 'yellow')
            mqtt = False

    # try:
    #     init_logging( test_logger,
    #                  TEST_LOGGING_CONFIG['logging_level'], log_path, data_log_filename)
    # except Exception as err:
    #     msg += colored(f'\n\u26A0 ERROR: Could not initialize logging!\n{err}', 'red')

    return test_logger, test_log_filename, TEST_LOGGING_CONFIG['logging_level'], msg

class OhmPiTests():
    """
    OhmPiTests class .
    """
    def __init__(self, mqtt=True, config=None):
        # set loggers
        self.test_logger, _, _, _ = setup_test_logger(mqtt=mqtt)
        self.exec_logger, _, self.data_logger, _, self.soh_logger, _, _, msg = setup_loggers(mqtt=mqtt)
        print(msg)

        # specify loggers when instancing the hardware
        self._hw = OhmPiHardware(**{'exec_logger': self.exec_logger, 'data_logger': self.data_logger,
                                    'soh_logger': self.soh_logger}, hardware_config=HARDWARE_CONFIG)

        self.exec_logger.info('Hardware configured...')
        self.exec_logger.info('OhmPi tests ready to start...')

    def test_connections(self):
        pass

    def test_tx_connection(self, devices=['mcp','ads']):
        for device in devices:
            if f'{device}_address' in self._hw.tx.specs:
                if test_i2c_devices_on_bus(self._hw.tx.specs[f'{device}_address'], self._hw.tx.connection):
                    self.test_logger.info(f"TX connections: MCP device with address {hex(self._hw.tx.specs[f'{device}_address'])} accessible on I2C bus.")
            else:
                pass

    def test_rx_connection(self, devices=['mcp','ads']):
        for device in devices:
            if f'{device}_address' in self._hw.rx.specs:
                if test_i2c_devices_on_bus(self._hw.rx.specs[f'{device}_address'], self._hw.rx.connection):
                    self.test_logger.info(f"RX connections: MCP device with address {hex(self._hw.tx.specs[f'{device}_address'])} accessible on I2C bus.")
            else:
                pass
    def test_mux_connection(self, devices=['mcp', 'mux_tca']):
        for mux_id, mux in self._hw.mux_boards.items():
            if mux.model == 'mux_2024_0_X':
                print(mux.model)
                for mcp_address in mux._mcp_addresses:
                    print(mcp_address)
                    if mcp_address is not None:
                        if test_i2c_devices_on_bus(mcp_address, mux.connection):
                            self.test_logger.info(
                                f"MUX connections: {mux_id} with address {hex(mcp_address)} accessible on I2C bus.")
                        else:
                            self.test_logger.info(f"MUX connections{mux_id} with address {hex(mcp_address)} NOT accessible on I2C bus.")
            elif  mux.model == 'mux_2023_0_X':
                if f'mux_tca_address' in mux.specs:
                    if test_i2c_devices_on_bus(mux.specs['mux_tca_address'], mux.connection):
                        self.test_logger.info(f"MUX connections: {mux_id} with address {hex(mux.specs['mux_tca_address'])} accessible on I2C bus.")

    def test_pwr_connection(self):
        if self._hw.tx.pwr.voltage_adjustable:
            try:
                pass
            except:
                traceback.print_exc()
        else:
            self.exec_logger.info('Pwr cannot be tested with this system configuration.')

    def test_vmn_hardware_offset(self):
        test_result = False
        quad = [0, 0, 0, 0]
        tx_volt = 5.
        injection_duration = .5
        duty_cycle = .5 # or 0
        nb_stack = 2
        delay = injection_duration * 2/3
        if self.switch_mux_on(quad):
            self._hw.vab_square_wave(tx_volt, cycle_duration=injection_duration * 2 / duty_cycle, cycles=nb_stack,
                                     duty_cycle=duty_cycle)
        Vmn = self._hw.last_vmn(delay=delay)
        Vmn_std = self._hw.last_vmn_dev(delay=delay)

        Vmn_deviation_from_offset = abs(1 - Vmn / self._hw.rx._vmn_hardware_offset) *100

        self.test_logger.info(f"Test Vmn hardware offset: Vmn offset deviation from config = {Vmn_deviation_from_offset: %.3f} %")
        if Vmn_deviation_from_offset <= 10.:
            test_result = True

        return test_result


    def test_r_shunt(self):
        if self._hw.tx.pwr.voltage_adjustable:
            pass
        else:
            self.exec_logger.info('r_shunt cannot be tested with this system configuration.')

    def test_mqtt_broker(self):
        pass

    def test_mux(self):
        self._hw.test_mux()
