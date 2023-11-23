import os
import datetime
import numpy as np
from ohmpi.hardware_components import MuxAbstract
import adafruit_tca9548a  # noqa
from adafruit_mcp230xx.mcp23017 import MCP23017  # noqa
from digitalio import Direction  # noqa
from busio import I2C  # noqa
from ohmpi.utils import enforce_specs

# hardware characteristics and limitations
SPECS = {'model': {'default': os.path.basename(__file__).rstrip('.py')},
         'id': {'default': 'mux_??'},
         'voltage_max': {'default': 50.},
         'current_max': {'default': 3.},
         'activation_delay': {'default': 0.01},
         'release_delay': {'default': 0.005}
         }

# defaults to 4 roles cabling electrodes from 1 to 8
default_mux_cabling = {(elec, role): ('mux_1', elec) for role in ['A', 'B', 'M', 'N'] for elec in range(1, 9)}

inner_cabling = {'4_roles': {(1, 'X'): {'MCP': 0, 'MCP_GPIO': 0}, (1, 'Y'): {'MCP': 0, 'MCP_GPIO': 8},
                             (2, 'X'): {'MCP': 0, 'MCP_GPIO': 1}, (2, 'Y'): {'MCP': 0, 'MCP_GPIO': 9},
                             (3, 'X'): {'MCP': 0, 'MCP_GPIO': 2}, (3, 'Y'): {'MCP': 0, 'MCP_GPIO': 10},
                             (4, 'X'): {'MCP': 0, 'MCP_GPIO': 3}, (4, 'Y'): {'MCP': 0, 'MCP_GPIO': 11},
                             (5, 'X'): {'MCP': 0, 'MCP_GPIO': 4}, (5, 'Y'): {'MCP': 0, 'MCP_GPIO': 12},
                             (6, 'X'): {'MCP': 0, 'MCP_GPIO': 5}, (6, 'Y'): {'MCP': 0, 'MCP_GPIO': 13},
                             (7, 'X'): {'MCP': 0, 'MCP_GPIO': 6}, (7, 'Y'): {'MCP': 0, 'MCP_GPIO': 14},
                             (8, 'X'): {'MCP': 0, 'MCP_GPIO': 7}, (8, 'Y'): {'MCP': 0, 'MCP_GPIO': 15},
                             (1, 'XX'): {'MCP': 1, 'MCP_GPIO': 7}, (1, 'YY'): {'MCP': 1, 'MCP_GPIO': 15},
                             (2, 'XX'): {'MCP': 1, 'MCP_GPIO': 6}, (2, 'YY'): {'MCP': 1, 'MCP_GPIO': 14},
                             (3, 'XX'): {'MCP': 1, 'MCP_GPIO': 5}, (3, 'YY'): {'MCP': 1, 'MCP_GPIO': 13},
                             (4, 'XX'): {'MCP': 1, 'MCP_GPIO': 4}, (4, 'YY'): {'MCP': 1, 'MCP_GPIO': 12},
                             (5, 'XX'): {'MCP': 1, 'MCP_GPIO': 3}, (5, 'YY'): {'MCP': 1, 'MCP_GPIO': 11},
                             (6, 'XX'): {'MCP': 1, 'MCP_GPIO': 2}, (6, 'YY'): {'MCP': 1, 'MCP_GPIO': 10},
                             (7, 'XX'): {'MCP': 1, 'MCP_GPIO': 1}, (7, 'YY'): {'MCP': 1, 'MCP_GPIO': 9},
                             (8, 'XX'): {'MCP': 1, 'MCP_GPIO': 0}, (8, 'YY'): {'MCP': 1, 'MCP_GPIO': 8}},
                 '2_roles':  # TODO: WARNING check 2_roles table, it has not been verified yet !!!
                            {(1, 'X'): {'MCP': 0, 'MCP_GPIO': 0}, (1, 'Y'): {'MCP': 0, 'MCP_GPIO': 8},
                             (2, 'X'): {'MCP': 0, 'MCP_GPIO': 1}, (2, 'Y'): {'MCP': 0, 'MCP_GPIO': 9},
                             (3, 'X'): {'MCP': 0, 'MCP_GPIO': 2}, (3, 'Y'): {'MCP': 0, 'MCP_GPIO': 10},
                             (4, 'X'): {'MCP': 0, 'MCP_GPIO': 3}, (4, 'Y'): {'MCP': 0, 'MCP_GPIO': 11},
                             (5, 'X'): {'MCP': 0, 'MCP_GPIO': 4}, (5, 'Y'): {'MCP': 0, 'MCP_GPIO': 12},
                             (6, 'X'): {'MCP': 0, 'MCP_GPIO': 5}, (6, 'Y'): {'MCP': 0, 'MCP_GPIO': 13},
                             (7, 'X'): {'MCP': 0, 'MCP_GPIO': 6}, (7, 'Y'): {'MCP': 0, 'MCP_GPIO': 14},
                             (8, 'X'): {'MCP': 0, 'MCP_GPIO': 7}, (8, 'Y'): {'MCP': 0, 'MCP_GPIO': 15},
                             (16, 'X'): {'MCP': 1, 'MCP_GPIO': 7}, (16, 'Y'): {'MCP': 1, 'MCP_GPIO': 15},
                             (15, 'X'): {'MCP': 1, 'MCP_GPIO': 6}, (15, 'Y'): {'MCP': 1, 'MCP_GPIO': 14},
                             (14, 'X'): {'MCP': 1, 'MCP_GPIO': 5}, (14, 'Y'): {'MCP': 1, 'MCP_GPIO': 13},
                             (13, 'X'): {'MCP': 1, 'MCP_GPIO': 4}, (13, 'Y'): {'MCP': 1, 'MCP_GPIO': 12},
                             (12, 'X'): {'MCP': 1, 'MCP_GPIO': 3}, (12, 'Y'): {'MCP': 1, 'MCP_GPIO': 11},
                             (11, 'X'): {'MCP': 1, 'MCP_GPIO': 2}, (11, 'Y'): {'MCP': 1, 'MCP_GPIO': 10},
                             (10, 'X'): {'MCP': 1, 'MCP_GPIO': 1}, (10, 'Y'): {'MCP': 1, 'MCP_GPIO': 9},
                             (9, 'X'): {'MCP': 1, 'MCP_GPIO': 0}, (9, 'Y'): {'MCP': 1, 'MCP_GPIO': 8}}
                 }


class Mux(MuxAbstract):
    def __init__(self, **kwargs):
        if 'model' not in kwargs.keys():
            for key in SPECS.keys():
                kwargs = enforce_specs(kwargs, SPECS, key)
            subclass_init = False
        else:
            subclass_init = True
        super().__init__(**kwargs)
        if not subclass_init:
            self.exec_logger.event(f'{self.model}: {self.board_id}\tmux_init\tbegin\t{datetime.datetime.utcnow()}')
        assert isinstance(self.connection, I2C)
        self.exec_logger.debug(f'configuration: {kwargs}')
        self._roles = kwargs.pop('roles', None)
        if self._roles is None:
            self._roles = {'A': 'X', 'B': 'Y', 'M': 'XX', 'N': 'YY'}  # NOTE: defaults to 4-roles
        if np.all([j in self._roles.values() for j in set([i[1] for i in list(inner_cabling['4_roles'].keys())])]):
            self._mode = '4_roles'
        elif np.all([j in self._roles.values() for j in set([i[1] for i in list(inner_cabling['2_roles'].keys())])]):
            self._mode = '2_roles'
        else:
            self.exec_logger.error(f'Invalid role assignment for {self.model}: {self._roles} !')
            self._mode = ''

        # Setup TCA
        tca_address = kwargs.pop('tca_address', None)
        tca_channel = kwargs.pop('tca_channel', 0)
        if tca_address is None:
            self._tca = self.connection
        else:
            self._tca = adafruit_tca9548a.TCA9548A(self.connection, tca_address)[tca_channel]

        # Setup MCPs
        self._mcp_jumper_pos = {'addr2': kwargs.pop('addr2', None), 'addr1': kwargs.pop('addr1', None)}
        self._mcp_addresses = (kwargs.pop('mcp_0', None), kwargs.pop('mcp_1', None))
        if self._mcp_addresses[0] is None and self._mcp_addresses[1] is None:
            if self._mcp_jumper_pos['addr2'] is not None and self._mcp_jumper_pos['addr1'] is not None:
                self._mcp_jumper_pos_to_addr()
                self.exec_logger.debug(f"{self.board_id} assigned mcp_addresses {self._mcp_addresses[0]} and "
                                       f"{self._mcp_addresses[1]} from jumper positions.")
            else:
                self.exec_logger.debug(f'MCP addresses nor jumper positions for {self.board_id} not in config file...')
                # TODO: if no addresses defined, should abort or should we set default mcp addresses?
        for addr in self._mcp_addresses:
            assert addr in ['0x20', '0x21', '0x22', '0x23', '0x24', '0x25', '0x26', '0x27']
        self._mcp = [None, None]
        self.reset()

        if self.addresses is None:
            self._get_addresses()

        self.exec_logger.debug(f'{self.board_id} addresses: {self.addresses}')
        if not subclass_init:  # TODO: try to only log this event and not the one created by super()
            self.exec_logger.event(f'{self.model}: {self.board_id}\tmux_init\tend\t{datetime.datetime.utcnow()}')

    def _get_addresses(self):
        """ Converts inner cabling addressing into (electrodes, role) addressing """
        ic = inner_cabling[self._mode]
        self.addresses = {}
        d = {}
        for k, v in self.cabling.items():
            d.update({k: ic[(v[0], self._roles[k[1]])]})
        self.addresses = d

    def reset(self):
        self._mcp[0] = MCP23017(self._tca, address=int(self._mcp_addresses[0], 16))
        self._mcp[1] = MCP23017(self._tca, address=int(self._mcp_addresses[1], 16))

    def switch_one(self, elec=None, role=None, state=None):
        MuxAbstract.switch_one(self, elec=elec, role=role, state=state)

        def activate_relay(mcp, mcp_pin, value=True):
            pin_enable = mcp.get_pin(mcp_pin)
            pin_enable.direction = Direction.OUTPUT
            pin_enable.value = value

        d = self.addresses[elec, role]
        if state == 'on':
            activate_relay(self._mcp[d['MCP']], d['MCP_GPIO'], True)
            # time.sleep(MUX_CONFIG['activation_delay'])  # NOTE: moved to MuxAbstract switch
        if state == 'off':
            activate_relay(self._mcp[d['MCP']], d['MCP_GPIO'], False)
            # time.sleep(MUX_CONFIG['release_delay'])  # NOTE: moved to MuxAbstract switch

    def _mcp_jumper_pos_to_addr(self):
        d = {'up': 0, 'down': 1}
        mcp_0 = hex(int(f"0100{d[self._mcp_jumper_pos['addr2']]}{d[self._mcp_jumper_pos['addr1']]}0", 2))
        mcp_1 = hex(int(f"0100{d[self._mcp_jumper_pos['addr2']]}{d[self._mcp_jumper_pos['addr1']]}1", 2))
        self._mcp_addresses = (mcp_0, mcp_1)