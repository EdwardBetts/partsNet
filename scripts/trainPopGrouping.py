from __future__ import division, print_function, absolute_import 

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('model', metavar='<parts net file>', type=argparse.FileType('wb'), help='Filename of model file')
parser.add_argument('--log', action='store_true')

args = parser.parse_args()

if args.log:
    from pnet.vzlog import default as vz
import numpy as np
import amitgroup as ag
import sys
ag.set_verbose(True)

from pnet.bernoullimm import BernoulliMM
import pnet
from sklearn.svm import LinearSVC 


layers = [
    #pnet.IntensityThresholdLayer(),
    
    pnet.EdgeLayer(k=5, radius=1, spread='orthogonal', minimum_contrast=0.05),
    #pnet.IntensityThresholdLayer(),
    pnet.PartsLayer(100, (6, 6), settings=dict(outer_frame=0, 
                                              threshold=40, 
                                              samples_per_image=40, 
                                              max_samples=10000, 
                                              min_prob=0.005,
                                              )),
    
    pnet.ExtensionPartsLayer(num_parts = 100, num_components = 10, part_shape = (12,12),lowerLayerShape = (6,6)), 
    pnet.PoolingLayer(shape=(8,8), strides=(8, 8)),
    #pnet.MixtureClassificationLayer(n_components=1, min_prob=0.0001,block_size=200),
    #pnet.ExtensionPoolingLayer(n_parts = 1000, grouping_type='mixture_model',pooling_type = 'distance', pooling_distance = 5, weights_file = './weights100Hidden_pool8*8.npy',save_weights_file = None, settings = {}),
    pnet.ExtensionPoolingLayer(n_parts = 1000, grouping_type='mixture_model',pooling_type = 'distance', pooling_distance = 5, weights_file = None, save_weights_file = "./mixtureweights100Hidden_pool8*8.npy", settings = {}),
    pnet.SVMClassificationLayer(C=1.0)
]

net = pnet.PartsNet(layers)

digits = range(10)
ims = ag.io.load_mnist('training', selection=slice(200), return_labels=False)

#print(net.sizes(X[[0]]))

net.train(ims)

sup_ims = []
sup_labels = []
# Load supervised training data
for d in digits:
    ims0 = ag.io.load_mnist('training', [d], selection=slice(100), return_labels=False)
    sup_ims.append(ims0)
    sup_labels.append(d * np.ones(len(ims0), dtype=np.int64))

sup_ims = np.concatenate(sup_ims, axis=0)
sup_labels = np.concatenate(sup_labels, axis=0)

net.train(sup_ims, sup_labels)


net.save(args.model)

if args.log:
    net.infoplot(vz)
    vz.finalize()
