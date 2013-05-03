#! /usr/bin/env python

import sys
import imp
import ipdb as pdb
import argparse
import types

#from utils import loadFromFile
#from squaresRbm import loadPickledData
from GitResultsManager import resman
#from util.plotting import plot3DShapeFromFlattened
from util.dataPrep import PCAWhiteningDataNormalizer  #, printDataStats



class Layer(object):

    trainable = False      # default
    
    def __init__(self, params):
        self.name = params['name']
        self.layerType = params['type']

        # Calculated when layer is created
        self.inputSize = None     # size of input
        self.outputSize = None    # size of output



class NonDataLayer(Layer):

    isDataLayer = False

    def __init__(self, params):
        super(NonDataLayer, self).__init__(params)

        # Here we keep track of two important quantities:
        # 1. how many patches each layer can see (needed when
        #    determining how large of data samples are needed for
        #    training this layer), and
        # 2. the distance, in number of patchs, to the nearest
        #    neighbor in both i and j. This is needed for calculating
        #    (1) on higher layers.
        self.seesPatches = None      # tuple, number of patches in the data layer this layer is exposed to
        self.distToNeighbor = None   # tuple, number of patches that the nearest neighbor is in i and j

    def calculateOutputSize(self, inputSize):
        assert isinstance(inputSize, tuple), 'inputSize must be a tuple but it is %s' % repr(inputSize)
        return self._calculateOutputSize(inputSize)

    def _calculateOutputSize(self, inputSize):
        '''Default pass through version. Override in derived classes
        if desired. This method may assume inputSize is a tuple.'''
        return inputSize

    def calculateSeesPatches(self, prevLayerSees, prevDistToNeighbor):
        assert isinstance(prevLayerSees, tuple), 'prevLayerSees must be a tuple but it is %s' % repr(prevLayerSees)
        assert isinstance(prevDistToNeighbor, tuple), 'prevDistToNeighbor must be a tuple but it is %s' % repr(prevDistToNeighbor)
        assert len(prevLayerSees) == len(prevDistToNeighbor)
        return self._calculateSeesPatches(prevLayerSees, prevDistToNeighbor)

    def _calculateSeesPatches(self, prevLayerSees, prevDistToNeighbor):
        '''Default pass through version. Override in derived classes
        if desired. This method may assume both inputs are tuples.'''
        return prevLayerSees

    def calculateDistToNeighbor(self, prevDistToNeighbor):
        assert isinstance(prevDistToNeighbor, tuple), 'prevDistToNeighbor must be a tuple but it is %s' % repr(prevDistToNeighbor)
        return self._calculateDistToNeighbor(prevDistToNeighbor)

    def _calculateDistToNeighbor(self, prevDistToNeighbor):
        '''Default pass through version. Override in derived classes
        if desired. This method may assume prevDistToNeighbor is a
        tuple.'''
        return prevDistToNeighbor

    def forwardProp(self, data):
        '''data is one example per column'''
        if self.trainable and not self.isInitialized:
            raise Exception('Must initialize %s layer first' % self.name)
        if self.trainable and not self.isTrained:
            print 'WARNING: forwardProp through untrained layer, might not be desired'
        dimension, numExamples = data.shape
        if dimension != prod(self.inputSize):
            raise Exception('Layer %s expects examples of shape %s = %s rows but got %s data matrix'
                            % (self.name, self.inputSize, prod(self.inputSize), data.shape))
        return self._forwardProp(data)

    def _forwardProp(self, data):
        '''Default pass through version. Override in derived classes
        if desired.'''
        return data



class TrainableLayer(NonDataLayer):

    trainable = True

    def __init__(self, params):
        super(TrainableLayer, self).__init__(params)
        self.isInitialized = False
        self.isTrained = False

    def initialize(self):
        if self.isInitialized:
            raise Exception('Layer was already initialized')
        self._initialize()
        self.isInitialized = True

    def _initialize(self):
        '''Default no-op version. Override in derived class.'''
        pass

    def train(self, data):
        if self.isTrained:
            raise Exception('Layer was already trained')
        self._train(data)
        self.isTrained = True

    def _train(self, data):
        '''Default no-op version. Override in derived class.'''
        pass
        



######################
# Data
######################

class DataLayer(Layer):

    isDataLayer = True

    def __init__(self, params):
        super(DataLayer, self).__init__(params)

        self.imageSize = params['imageSize']
        self.patchSize = params['patchSize']
        self.stride = params['stride']

        # Only 2D data types for now (color is fine though)
        assert len(self.imageSize) == 2
        assert len(self.patchSize) == 2
        assert len(self.stride) == 2
        assert len(self.imageSize) == len(self.stride), 'imageSize and stride must be same length'

    def numPatches(self):
        '''How many patches fit within the data. Rounds down.'''
        return tuple([(ims-ps)/st+1 for ims,ps,st in zip(self.imageSize, self.patchSize, self.stride)])

    def getOutputSize(self):
        raise Exception('must implement in derived class')



class UpsonData3(DataLayer):

    def __init__(self, params):
        super(UpsonData3, self).__init__(params)

        self.colors = params['colors']

        assert self.colors in (1,3)

    def getOutputSize(self):
        if self.colors == 1:
            return self.patchSize
        else:
            return (self.patchSize[0], self.patchSize[1], 3)



######################
# Whitening
######################

class WhiteningLayer(TrainableLayer):

    def __init__(self, params):
        super(WhiteningLayer, self).__init__(params)



class PCAWhiteningLayer(WhiteningLayer):

    def __init__(self, params):
        super(PCAWhiteningLayer, self).__init__(params)
        self.pcaWhiteningDataNormalizer = None

    def _train(self, data):
        self.pcaWhiteningDataNormalizer = PCAWhiteningDataNormalizer(data)

    def _forwardProp(self, data):
        dataWhite, junk = whiteningStage.raw2normalized(data, unitNorm = True)
        return dataWhite



######################
# Learning
######################

class TicaLayer(TrainableLayer):

    def __init__(self, params):
        super(TicaLayer, self).__init__(params)

        self.hiddenSize = params['hiddenSize']
        self.neighborhood = params['neighborhood']
        self.lambd = params['lambd']
        self.epsilon = params['epsilon']
        self.tica = None

        assert isinstance(self.hiddenSize, tuple)
        assert len(self.neighborhood) == 4
        assert self.neighborhood[3] == 0   # shrink not supported yet (changes output size)

    def _calculateOutputSize(self, inputSize):
        return self.hiddenSize

    def _train(self, data, trainParam):
        logDir = trainParam.get('logDir', None)
        # Learn model
        tica = TICA(nInputs            = self.numInputs,
                    hiddenLayerShape   = self.hiddenSize,
                    neighborhoodParams = self.neighborhood,
                    lambd              = self.lambd,
                    epsilon            = self.epsilon)

        beginTotalCost, beginPoolingCost, beginReconstructionCost, grad = tica.cost(tica.WW, nextLayerData)

        tic = time.time()
        tica.learn(data, maxFun = trainParam['maxFuncCalls'])
        execTime = time.time() - tic
        if logDir:
            saveToFile(os.path.join(logDir, 'tica.pkl.gz'), tica)    # save learned model

        endTotalCost, endPoolingCost, endReconstructionCost, grad = tica.cost(tica.WW, data)

        print 'beginTotalCost, beginPoolingCost, beginReconstructionCost, endTotalCost, endPoolingCost, endReconstructionCost, execTime ='
        print [beginTotalCost, beginPoolingCost, beginReconstructionCost, endTotalCost, endPoolingCost, endReconstructionCost, execTime]

        # Plot some results
        #plotImageRicaWW(tica.WW, imgShape, saveDir, tileShape = hiddenLayerShape, prefix = pc('WW_iterFinal'))
        if logDir:
            tica.plotResults(logDir, tica, data, self.numInputs, self.hiddenSize)

        self.tica = tica


    def _forwardProp(self, data):
        hidden, absPooledActivations = self.tica(data)
        return absPooledActivations



######################
# Downsampling, LCN, Concatenation
######################

class DownsampleLayer(NonDataLayer):

    def __init__(self, params):
        super(DownsampleLayer, self).__init__(params)

        self.factor = params['factor']

        assert len(self.factor) in (1,2)

    def _calculateOutputSize(self, inputSize):
        '''rounds down'''
        assert len(inputSize) <= 3
        if len(inputSize) == 3:
            # color images
            assert len(self.factor) == 2, 'for color images, self.factor must be length 2 (i and j factors)'
            # don't downsample third dimensions (number of colors, probably 3)
            return (inputSize[0]/self.factor[0], inputSize[1]/self.factor[1], inputSize[2])
        else:
            # linear data or single-channel images
            assert len(self.factor) == len(inputSize), 'for inputSize length 1 or 2, self.factor must match length of inputSize'
            if len(inputSize) == 1:
                return (inputSize[0]/self.factor[0],)
            else: # length 2
                return (inputSize[0]/self.factor[0], inputSize[1]/self.factor[1])

    def _forwardProp(self, data):
        dimension, numExamples = data.shape

        patches = reshape(data, self.inputShape + (numExamples,))
        # len(self.factor) is either 1 or 2
        if len(self.factor) == 1:
            downsampled = patches[::self.factor[0],:]
        else:
            downsampled = patches[::self.factor[0],::self.factor[1],:]
            
        output = reshape(downsampled, (prod(self.outputShape), numExamples))
        return output



class AvgPool(NonDataLayer):
    pass

class MaxPool(NonDataLayer):
    pass


class LcnLayer(NonDataLayer):

    def __init__(self, params):
        super(LcnLayer, self).__init__(params)
        self.gaussWidth = params['gaussWidth']

    def _forwardProp(self, data):
        dimension, numExamples = data.shape

        gaussNeighbors = neighborMatrix(self.inputSize, self.gaussWidth, gaussian=True)

        # 2. LCN
        vv = data - dot(gaussNeighbors, data)
        sig = sqrt(dot(gaussNeighbors, vv**2))
        cc = .01     # ss = sorted(sig.flatten()); ss[len(ss)/10] = 0.026 in one test. So .01 seems about right.
        yy = vv / maximum(cc, sig)

        return yy



class ConcatenationLayer(NonDataLayer):

    def __init__(self, params):
        super(ConcatenationLayer, self).__init__(params)

        self.concat = params['concat']
        self.stride = params['stride']

        assert isinstance(self.concat, tuple)
        assert isinstance(self.stride, tuple)
        assert len(self.concat) == len(self.stride)
        for ii, st in enumerate(self.stride):
            assert st >= 1 and st <= self.concat[ii], 'each element of stride must be at least one and at most %s' % self.concat

    def _calculateOutputSize(self, inputSize):
        if len(inputSize) == 3:
            # color images
            assert len(self.concat) == 2, 'for color images, self.concat must be length 2 (i and j concat factors)'
            # don't touch third dimensions (number of colors, probably 3)
            return (inputSize[0]*self.concat[0], inputSize[1]*self.concat[1], inputSize[2])
        else:
            # linear data or single-channel images
            assert len(self.concat) == len(inputSize), 'for inputSize length 1 or 2, self.concat must match length of inputSize'
            if len(inputSize) == 1:
                return (inputSize[0]*self.concat[0],)
            else: # length 2
                return (inputSize[0]*self.concat[0], inputSize[1]*self.concat[1])

    def _calculateSeesPatches(self, prevLayerSees, prevDistToNeighbor):
        assert len(prevLayerSees) == len(self.concat)
        if len(self.concat) == 1:
            return (prevLayerSees[0] + (self.concat[0]-1) * prevDistToNeighbor[0],)
        elif len(self.concat) == 2:
            return (prevLayerSees[0] + (self.concat[0]-1) * prevDistToNeighbor[0],
                    prevLayerSees[1] + (self.concat[1]-1) * prevDistToNeighbor[1])
        else:
            raise Exception('logic error')

    def _calculateDistToNeighbor(self, prevDistToNeighbor):
        assert len(prevDistToNeighbor) == len(self.concat)
        if len(self.concat) == 1:
            return (prevDistToNeighbor[0] * self.stride[0],)
        elif len(self.concat) == 2:
            return (prevDistToNeighbor[0] * self.stride[0],
                    prevDistToNeighbor[1] * self.stride[1])
        else:
            raise Exception('logic error')

    def _forwardProp(self, data):
        HERE    # ;)

