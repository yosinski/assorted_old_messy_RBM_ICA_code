#! /usr/bin/env ipythonpl

'''
Research code

Jason Yosinski
'''

import pdb
import os, sys
from numpy import *
from matplotlib import pyplot
from PIL import Image

from sklearn.decomposition import FastICA

from rbm.ResultsManager import resman
from rbm.pca import PCA
from rbm.utils import tile_raster_images, load_mnist_data, loadUpsonData, saveToFile
from mnistIca import testIca



if __name__ == '__main__':
    '''Demonstrate ICA on the Upson data set.'''

    resman.start('junk', diary = False)

    imgDim = 10    # 2, 4, 10, 15, 28
    datasets = loadUpsonData('../data/upson_rovio_1/train_%d_50000.pkl.gz' % imgDim,
                             '../data/upson_rovio_1/test_%d_50000.pkl.gz' % imgDim)
    testIca(datasets = datasets,
            savedir = resman.rundir,     # comment out to show plots instead of saving
            smallImgHack = False,
            quickHack = False,
            )
    resman.stop()