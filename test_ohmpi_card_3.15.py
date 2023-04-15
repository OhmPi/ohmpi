import sys
sys.path.extend(['/home/su530201/PycharmProjects/ohmpi_reversaal/OhmPi'])
from OhmPi.hardware.ohmpi_card_3_15 import Tx
from OhmPi.hardware.ohmpi_card_3_15 import Rx
from OhmPi.logging_setup import create_stdout_logger

exec_logger = create_stdout_logger(name='exec')
soh_logger = create_stdout_logger(name='soh')

print('\nCreating TX...')
tx = Tx(exec_logger= exec_logger, soh_logger= soh_logger)
print('\nCreating RX...')
rx = Rx(exec_logger= exec_logger, soh_logger= soh_logger)
