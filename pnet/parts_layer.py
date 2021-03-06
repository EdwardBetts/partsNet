from __future__ import division, print_function, absolute_import 

# TODO: Temp
import matplotlib as mpl
mpl.use('Agg')

from scipy.special import logit
import numpy as np
import itertools as itr
import amitgroup as ag
from pnet.layer import Layer
import pnet

# TODO: Use later
if 0:
    def _threshold_in_counts(self, threshold, num_edges):
        size = self.settings['part_size']
        frame = self.settings['patch_frame']
        return max(1, int(threshold * (size[0] - 2*frame) * (size[1] - 2*frame) * num_edges))

@Layer.register('parts-layer')
class PartsLayer(Layer):
    def __init__(self, num_parts, part_shape, settings={}):
        #, outer_frame=1, threshold=1):
        self._num_parts = num_parts
        self._part_shape = part_shape
        #self._outer_frame = outer_frame
        #self._threshold = threshold
        self._settings = settings
        self._train_info = {}
        self._parts = None
        self._weights = None

    def extract(self, X):
        assert self._parts is not None, "Must be trained before calling extract"
        th = self._settings['threshold']
        part_logits = np.rollaxis(logit(self._parts).astype(np.float64), 0, 4)
        constant_terms = np.apply_over_axes(np.sum, np.log(1-self._parts).astype(np.float64), [1, 2, 3]).ravel()

        from pnet.cyfuncs import code_index_map_multi
        #print(X.shape)
        feature_map = code_index_map_multi(X, part_logits, constant_terms, th,
                                           outer_frame=self._settings['outer_frame'], 
                                           min_llh=self._settings.get('min_llh', -np.inf),
                                           n_coded=self._settings.get('n_coded', 1))

        #print(feature_map.shape)
        #print(feature_map.dtype)
        #print(self._num_parts.dtype)
        return (feature_map, self._num_parts)
    @property
    def trained(self):
        return self._parts is not None 

    def train(self, X, Y=None, OriginalX = None):
        #assert Y is None
        ag.info('Extracting patches')
        patches, patches_original = self._get_patches(X,OriginalX)
        ag.info('Done extracting patches')
        ag.info('Training patches', patches.shape)
        return self.train_from_samples(patches,patches_original)

    def train_from_samples(self, patches,patches_original):
        #from pnet.latent_bernoulli_mm import LatentBernoulliMM
        from pnet.bernoullimm import BernoulliMM
        min_prob = self._settings.get('min_prob', 0.01)
        flatpatches = patches.reshape((patches.shape[0], -1))
        
        if 1:
            mm = BernoulliMM(n_components=self._num_parts, n_iter=20, tol=1e-15,n_init=2, random_state=self._settings.get('em_seed',0), min_prob=min_prob, verbose=False)
            mm.fit(flatpatches)
            print(mm.fit(flatpatches))
            #print('AIC', mm.aic(flatpatches))
            #print('BIC', mm.bic(flatpatches))
            
            if 0:
                # Draw samples
                #size = (20, 20)
                import gv
                import os
                N = 10000
                D = np.prod(self._part_shape)
                size = (20, 20)
                grid = gv.plot.ImageGrid(size[0], size[1], self._part_shape)
                samp = mm.sample(n_samples=np.prod(size)).reshape((-1,) + self._part_shape)
                samples = mm.sample(n_samples=N).reshape((-1,) + self._part_shape)
                print('samples', samples.shape)

                types = np.asarray(list(gv.multirange(*[2]*D))).reshape((-1,) + self._part_shape)
                th = np.clip(types, 0.01, 0.99)

                t = th[:,np.newaxis]
                x = samples[np.newaxis]

                llh0 = x * np.log(t) + (1 - x) * np.log(1 - t)
                counts0 = np.bincount(np.argmax(llh0.sum(-1).sum(-1), 0), minlength=th.shape[0])
                
                x1 = patches[np.newaxis,...,0]
                llh1 = x1 * np.log(t) + (1 - x1) * np.log(1 - t)
                counts1 = np.bincount(np.argmax(llh1.sum(-1).sum(-1), 0), minlength=th.shape[0])

                #import pdb; pdb.set_trace()

                w0 = counts0 / counts0.sum()
                w1 = counts1 / counts1.sum()

                print('w0', w0)
                print('w1', w1) 
                #import pdb; pdb.set_trace()


            #import pdb; pdb.set_trace()
            self._parts = mm.means_.reshape((self._num_parts,)+patches.shape[1:])
            self._weights = mm.weights_
        else:
            #mm = ag.stats.BernoulliMixture(self._num_parts, flatpatches, max_iter=2000)
            #mm.run_EM(1e-6, min_probability=min_prob)
            #self._parts = mm.templates.reshape((self._num_parts,)+patches.shape[1:])
            #self._weights = mm.weights
            from pnet.bernoulli import em
            ret = em(flatpatches, self._num_parts,20,numpy_rng=self._settings.get('em_seed',0),verbose=True)
            self._parts = ret[1].reshape((self._num_parts,) + patches.shape[1:])
            self._weights = np.arange(self._num_parts)
        if 0:
            predictedGroups = mm.predict(flatpatches) 
        
        # Calculate entropy of parts
        Hall = (self._parts * np.log(self._parts) + (1 - self._parts) * np.log(1 - self._parts))
        H = -np.apply_over_axes(np.mean, Hall, [1, 2, 3])[:,0,0,0]

        # Sort by entropy
        #II = np.argsort(H)

        #self._parts[:] = self._parts[II]
        #self._train_info['entropy'] = H[II]
        #self._weights[:] = self._weights[II]

    def _get_patches(self, X, OriginalX):
        assert (X.ndim == 4 or X.ndim == 5)
        if X.ndim == 4:
            return self._get_grey_patches(X, OriginalX)
        else:
            return self._get_color_patches(X, OriginalX)

    def _get_grey_patches(self, X, OriginalX):
        assert X.ndim == 4
        samples_per_image = self._settings.get('samples_per_image', 20) 
        fr = self._settings['outer_frame']
        patches = []
        patches_original = []
        rs = np.random.RandomState(self._settings.get('patch_extraction_seed', 0))

        th = self._settings['threshold']

        for i in range(X.shape[0]):
            Xi = X[i]
            OriginalXi = OriginalX[i]
            # How many patches could we extract?
            w, h = [Xi.shape[i]-self._part_shape[i]+1 for i in range(2)]

            # TODO: Maybe shuffle an iterator of the indices?
            indices = list(itr.product(range(w-1), range(h-1)))
            rs.shuffle(indices)
            i_iter = itr.cycle(iter(indices))

            for sample in range(samples_per_image):
                N = 200
                for tries in range(N):
                    x, y = next(i_iter)
                    selection = [slice(x, x+self._part_shape[0]), slice(y, y+self._part_shape[1])]

                    patch = Xi[selection]
                    #edgepatch_nospread = edges_nospread[selection]
                    if fr == 0:
                        tot = patch.sum()
                    else:
                        tot = patch[fr:-fr,fr:-fr].sum()

                    if th <= tot: 
                        patches.append(patch)
                        vispatch = OriginalXi[selection]
                        span = vispatch.min(),vispatch.max()
                        if span[1]-span[0] > 0:
                            vispatch = (vispatch - span[0])/(span[1] - span[0])
                        patches_original.append(vispatch)
                        if len(patches) >= self._settings.get('max_samples', np.inf):
                            return np.asarray(patches),np.asarray(patches_original)
                        break

                    if tries == N-1:
                        ag.info('WARNING: {} tries'.format(N))

        return np.asarray(patches),np.asarray(patches_original)

    def _get_color_patches(self, X, OriginalX):
        assert X.ndim == 5
        assert OriginalX.ndim == 4
        channel = X.shape[-1]

        samples_per_image = self._settings.get('samples_per_image', 20) 
        fr = self._settings['outer_frame']
        patches = []
        patches_original = []
        rs = np.random.RandomState(self._settings.get('patch_extraction_seed', 0))

        th = self._settings['threshold']

        for i in range(X.shape[0]):
            Xi = X[i]
            OriginalXi = OriginalX[i]
            # How many patches could we extract?
            w, h = [Xi.shape[j]-self._part_shape[j]+1 for j in range(2)]

            # TODO: Maybe shuffle an iterator of the indices?
            indices = list(itr.product(range(w-1), range(h-1)))
            rs.shuffle(indices)
            i_iter = itr.cycle(iter(indices))

            for sample in range(samples_per_image):
                N = 200
                for tries in range(N):
                    x, y = next(i_iter)
                    selection = [slice(x, x+self._part_shape[0]), slice(y, y+self._part_shape[1])]

                    patch = Xi[selection]
                    #edgepatch_nospread = edges_nospread[selection]
                    if fr == 0:
                        tot = patch.sum()
                    else:
                        tot = patch[fr:-fr,fr:-fr].sum()

                    if th <= tot * channel: 
                        patches.append(patch)
                        vispatch = OriginalXi[selection]
                        span = vispatch.min(),vispatch.max()
                        if span[1]-span[0] > 0:
                            vispatch = (vispatch - span[0])/(span[1] - span[0])
                        patches_original.append(vispatch)
                        if len(patches) >= self._settings.get('max_samples', np.inf):
                            return np.asarray(patches),np.asarray(patches_original)
                        break

                    if tries == N-1:
                        ag.info('WARNING: {} tries'.format(N))

        return np.asarray(patches),np.asarray(patches_original)

    def infoplot(self, vz):
        from pylab import cm
        D = self._parts.shape[-1]
        N = self._num_parts
        # Plot all the parts
        grid = pnet.plot.ImageGrid(N, D, self._part_shape)

        print('SHAPE', self._parts.shape)

        cdict1 = {'red':  ((0.0, 0.0, 0.0),
                           (0.5, 0.0, 0.0),
                           (1.0, 1.0, 1.0)),

                 'green': ((0.0, 0.4, 0.4),
                           (0.5, 0.0, 0.0),
                           (1.0, 1.0, 1.0)),

                 'blue':  ((0.0, 1.0, 1.0),
                           (0.5, 0.0, 0.0),
                           (1.0, 0.4, 0.4))
                }

        from matplotlib.colors import LinearSegmentedColormap
        C = LinearSegmentedColormap('BlueRed1', cdict1)

        for i in range(N):
            for j in range(D):
                grid.set_image(self._parts[i,...,j], i, j, cmap=C)#cm.BrBG)

        grid.save(vz.generate_filename(), scale=5)

        #vz.log('weights:', self._weights)
        #vz.log('entropy', self._train_info['entropy'])

        import pylab as plt
        plt.figure(figsize=(6, 3))
        plt.plot(self._weights, label='weight')
        plt.savefig(vz.generate_filename(ext='svg'))

        vz.log('weights span', self._weights.min(), self._weights.max()) 

        import pylab as plt
        plt.figure(figsize=(6, 3))
        plt.plot(self._train_info['entropy'])
        plt.savefig(vz.generate_filename(ext='svg'))

        vz.log('median entropy', np.median(self._train_info['entropy']))

    def save_to_dict(self):
        d = {}
        d['num_parts'] = self._num_parts
        d['part_shape'] = self._part_shape
        d['settings'] = self._settings
        d['parts'] = self._parts
        d['weights'] = self._weights
        return d

    @classmethod
    def load_from_dict(cls, d):
        obj = cls(d['num_parts'], d['part_shape'], settings=d['settings'])
        obj._parts = d['parts']
        obj._weights = d['weights']
        return obj
