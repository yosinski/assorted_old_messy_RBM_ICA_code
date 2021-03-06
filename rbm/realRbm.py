#! /usr/bin/env python

'''
Research code

Jason Yosinski
'''

import sys
from numpy import *

from upsonRbm import loadUpsonData
from rbm import test_rbm
from ResultsManager import resman
from pca import PCA



if __name__ == '__main__':
    resman.start('junk', diary = True)
    datasets = loadUpsonData('../data/upson_rovio_1/train_15_50000.pkl.gz',
                             '../data/upson_rovio_1/test_15_50000.pkl.gz')

    #meanTrain = mean(datasets[0][0])
    #stdTrain  = std(datasets[0][0])
    #datasets[0][0] = (datasets[0][0] - meanTrain) / stdTrain
    #datasets[2][0] = (datasets[2][0] - meanTrain) / stdTrain

    pca = PCA(datasets[0][0])
    datasets[0][0] = pca.toZca(datasets[0][0], None, epsilon = .1)
    datasets[2][0] = pca.toZca(datasets[2][0], None, epsilon = .1)

    print 'done loading.'
    
    test_rbm(datasets = datasets,
             training_epochs = 45,
             img_dim = 15,   # must match actual size of training data
             n_hidden = int(sys.argv[1]),
             learning_rate = float(sys.argv[2]),
             output_dir = resman.rundir,
             quickHack = False,
             visibleModel = 'real',
             initWfactor = .01,
             pcaDims = None)
    resman.stop()
