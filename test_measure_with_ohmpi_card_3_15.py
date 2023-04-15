import numpy as np
import matplotlib.pyplot as plt
from utils import change_config
change_config('config_ohmpi_card_3_15.py', verbose=False)
from OhmPi.measure import OhmPiHardware

k = OhmPiHardware()
k._vab_pulse(vab=12, length=1., sampling_rate=k.rx.sampling_rate, polarity=1)
r = k.readings[:,2]/k.readings[:,1]
print(f'Mean resistance: {np.mean(r):.3f} Ohms, Dev. {100*np.std(r)/np.mean(r):.1f} %')
print(f'sampling rate: {k.rx.sampling_rate:.1f} ms, mean sample spacing: {np.mean(np.diff(k.readings[:,0]))*1000.:.1f} ms')
change_config('config_default.py', verbose=False)
