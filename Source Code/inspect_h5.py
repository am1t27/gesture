import h5py
import numpy as np

with h5py.File('ASLModel.h5', 'r') as f:
    print('Top level keys:', list(f.keys()))
    if 'model_weights' in f:
        print('\nLayer keys:', list(f['model_weights'].keys()))
        for layer in f['model_weights'].keys():
            grp = f['model_weights'][layer]
            subs = list(grp.keys())
            print(f'\n  Layer [{layer}]: {subs}')
            for sub in subs:
                subgrp = grp[sub]
                if hasattr(subgrp, 'keys'):
                    subsubs = list(subgrp.keys())
                    print(f'    Sub [{sub}]: {subsubs}')
                    for ss in subsubs:
                        item = subgrp[ss]
                        if hasattr(item, 'shape'):
                            print(f'      [{ss}]: shape={item.shape}')
                        else:
                            print(f'      [{ss}]: (group)')
                elif hasattr(subgrp, 'shape'):
                    print(f'    Dataset [{sub}]: shape={subgrp.shape}')
