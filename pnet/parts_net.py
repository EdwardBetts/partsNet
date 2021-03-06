from __future__ import division, print_function, absolute_import 

import numpy as np
import amitgroup as ag
from pnet.layer import Layer

@Layer.register('parts-net')
class PartsNet(Layer):
    def __init__(self, layers):
        self._layers = layers
        self._train_info = {}

    @property
    def layers(self):
        return self._layers

    def train(self, X, Y=None):
        curX = X
        shapes = []
        for l, layer in enumerate(self._layers):
            #print("part-net")
            #print(layer)
            #print(np.array(curX).shape)
            #if isinstance(curX,tuple):
            #    print(curX[0].shape)
            #    print(curX[1])
            if not (not layer.supervised or (layer.supervised and Y is not None)):
                break
            print(layer)
            print(layer.trained)
            if not layer.trained:
                ag.info('Training layer {}...'.format(l))
                layer.train(curX, Y=Y, OriginalX=X)
                ag.info('Done.')
            print(layer)
            if layer.name == 'raondom-partition-svm-layer':
                curX = layer.extract(curX, Y = Y)
            else:
                curX = layer.extract(curX)
            if isinstance(curX, tuple):
                sh = curX[0].shape[1:-1] + (curX[1],)
            else:
                sh = curX.shape[1:]
            print(sh)
            shapes.append(sh)

        self._train_info['shapes'] = shapes

    def test(self, X, Y):
        Yhat = self.extract(X,Y)
        return Yhat == Y

    def classify(self, X, Y = None):
        return self.extract(X, Y, classify=True)
    
    def extract(self, X, Y = None, classify=False):
        curX = X
        for layer in self._layers:
            if layer.name == 'raondom-partition-svm-layer':
                curX = layer.extract(curX, Y)
            elif not layer.classifier or classify:
                curX = layer.extract(curX)
                if 0:
                    if isinstance(curX,tuple):
                        #print(curX[0].shape)
                        pass
                    else:
                        pass
                        #print(curX.shape)
        #print(curX.shape) 
        return curX

    def infoplot(self, vz):
        vz.title('Layers')

        vz.text('Layer shapes')
        for i, (layer, shape) in enumerate(zip(self.layers, self._train_info['shapes'])):
            vz.log(i, shape, layer.name)

        # Plot some information
        for i, layer in enumerate(self.layers):
            vz.section('Layer #{} : {}'.format(i, layer.name))
            layer.infoplot(vz)

    def save_to_dict(self):
        d = {}
        d['layers'] = []
        for layer in self._layers:
            layer_dict = layer.save_to_dict()
            layer_dict['name'] = layer.name
            d['layers'].append(layer_dict)

        return d

    @classmethod
    def load_from_dict(cls, d):
        layers = []
        for layer_dict in d['layers']:
            layer = Layer.getclass(layer_dict['name']).load_from_dict(layer_dict)
            layers.append(layer)
        obj = cls(layers)
        return obj
