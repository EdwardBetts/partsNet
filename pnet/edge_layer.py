from __future__ import division, print_function, absolute_import 

import amitgroup as ag
import numpy as np
from pnet.layer import Layer

@Layer.register('edge-layer')
class EdgeLayer(Layer):
    def __init__(self, **kwargs):
        self._edge_settings = kwargs 

    def extract(self, X):
        assert X.ndim == 3
        return ag.features.bedges(X, **self._edge_settings)

    def save_to_dict(self):
        d = {}
        d['edge_settings'] = self._edge_settings
        return d

    @classmethod
    def load_from_dict(cls, d):
        obj = cls(**d['edge_settings'])       
        return obj

