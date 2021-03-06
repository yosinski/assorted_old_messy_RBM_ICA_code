#! /usr/bin/env python

import ipdb as pdb
import os
import gc
from numpy import zeros, ones, prod, reshape, ceil, sqrt, random
from scipy.optimize import minimize
from scipy.linalg import norm
from IPython import embed

from util.dataLoaders import loadFromPklGz, saveToFile
from util.misc import dictPrettyPrint, relhack, Tic
from layers import layerClassNames, DataArrangement, Layer, DataLayer, UpsonData3, NYU2_Labeled, CS294Images, DummyDataLayer
from layers import NormalizingLayer, PCAWhiteningLayer, TicaLayer, DownsampleLayer, LcnLayer, ConcatenationLayer
from visualize import plotImageData, plotTopActivations, plotGrayActivations, plotReshapedActivations, plotActHist, plotActLines
from gradCheck import numericalCheckVectorGrad



class StackedLayers(object):

    def __init__(self, layerList):

        self.layers = []

        # 0. Check for duplicate names
        self.layerNames = [layer['name'] for layer in layerList]
        dups = set([x for x in self.layerNames if self.layerNames.count(x) > 1])
        if len(dups) > 0:
            raise Exception('Duplicate layer names: %s' % dups)

        # 1. Construct all layers
        for ii, layerDict in enumerate(layerList):
            print 'constructing layer %d:' % ii
            dictPrettyPrint(layerDict, prefix = '  ')

            layerClass = layerClassNames[layerDict['type']]
            if isinstance(layerClass, basestring):
                actualLayerClass = eval(layerDict[layerClass])
                layer = actualLayerClass(layerDict)
            else:
                layer = layerClass(layerDict)

            # Checks
            if ii == 0 and not layer.isDataLayer:
                raise Exception('First layer must be data layer, but it is %s' % repr(layer))
            if ii != 0 and layer.isDataLayer:
                raise Exception('Only the first layer can be a data layer, but layer %d is %s' % (ii, repr(layer)))

            # Populate inputSize, outputSize, seesPatches, and distToNeighbor
            if ii == 0:
                # For data layer
                layer.outputSize = layer.getOutputSize()
                layer.seesPatches = layer.calculateSeesPatches()  # no input needed for DataLayer
            else:
                prevLayer = self.layers[ii-1]

                # only for non-data layers
                layer.inputSize    = prevLayer.outputSize
                layer.outputSize   = layer.calculateOutputSize(layer.inputSize)
                if prevLayer.isDataLayer:
                    prevLayerSees      = (1,) * len(prevLayer.stride)
                    prevDistToNeighbor = (1,) * len(prevLayer.stride)
                else:
                    prevLayerSees      = prevLayer.seesPatches
                    prevDistToNeighbor = prevLayer.distToNeighbor
                layer.seesPatches    = layer.calculateSeesPatches(prevLayerSees, prevDistToNeighbor)
                layer.distToNeighbor = layer.calculateDistToNeighbor(prevDistToNeighbor)

            self.layers.append(layer)

        # 2. Post construction checks...
        for ii, layer in enumerate(self.layers):
            pass
        print 'layers look good (purely cursory check)'


    def printStatus(self):
        dataLayer = self.layers[0]
        for ii, layer in reversed(list(enumerate(self.layers))):
            print 'layer %2d: %-20s' % (ii, '%s (%s)' % (layer.name, layer.layerType)),
            if ii == 0:
                st = 'outputs size %s' % repr(layer.outputSize),
            else:
                st = 'maps size %s -> %s' % (repr(layer.inputSize), repr(layer.outputSize)),
            print '%-32s' % st,

            try:
                st = 'sees %s' % repr(self._seesPixels(layer, dataLayer))
            except AttributeError:
                st = '--'
            print '%-16s' % st,
            if layer.trainable:
                print 'trained' if layer.isTrained else 'not trained'
            else:
                print '--'

    def forwardPropPixelSamples(self, data, startLayerIdx = 0, layerIdx = None, sublayer = None, quiet = False):
        '''Push the given large pixel samples through the layers startLayerIdx, startLayerIdx+1, ..., layerIdx.
        Assume the sample is from layer startLayerIdx (default: 0, or dataLayer).
        If layerIdx is None, set layerIdx = max.
        If sublayer is None, set sublayer = max.
        '''

        if layerIdx is None: layerIdx = len(self.layers)-1
        if sublayer is None: sublayer = self.layers[layerIdx].nSublayers-1

        layer = self.layers[layerIdx]
        dataLayer = self.layers[0]

        dataArrangement = DataArrangement(sliceShape = layer.seesPatches, nSlices = data.shape[1])
        dataPatches = self.getSampledAndStackedPatches(data, layer, dataLayer)

        return self.forwardProp(dataPatches, dataArrangement, startLayerIdx, layerIdx, sublayer, quiet = quiet)
            
    def forwardProp(self, data, dataArrangement, startLayerIdx = 0, layerIdx = None, sublayer = None, quiet = False):
        '''Push the given data through the layers 0, 1, ..., layerIdx.
        If layerIdx is None, set layerIdx = max.
        If sublayer is None, set sublayer = max.
        '''

        if layerIdx is None: layerIdx = len(self.layers)-1
        if sublayer is None: sublayer = self.layers[layerIdx].nSublayers-1

        if not quiet:
            print 'forwardProp from layer %d through %d (s%d)' % (startLayerIdx+1, layerIdx, sublayer)
        currentRep = data
        currentArrangement = dataArrangement
        for ii in range(startLayerIdx+1, layerIdx+1):
            layer = self.layers[ii]
            if not quiet:
                print '  fp through layer %d - %s (%s)' % (ii, layer.name, layer.layerType)
            if ii == layerIdx:
                # only pass sublayer selection to last layer
                newRep, newArrangement = layer.forwardProp(currentRep, currentArrangement, sublayer, quiet = quiet)
            else:
                newRep, newArrangement = layer.forwardProp(currentRep, currentArrangement, quiet = quiet)
            if not quiet:
                print ('    layer transformed data from\n      %s, %s ->\n      %s, %s'
                       % (currentRep.shape, currentArrangement, newRep.shape, newArrangement))
            currentRep = newRep
            currentArrangement = newArrangement
        return currentRep, currentArrangement

    def train(self, trainParams, saveDir = None, quick = False, maxlayer = -1, onlyInit = False):
        '''Train all layers.

        if onlyInit, then do initialization but skip training.'''
        
        # check to make sure each trainParam matches a known layer...
        for layerName in trainParams.keys():
            if layerName not in self.layerNames:
                raise Exception('unknown layer name in param file: %s' % layerName)
        # ...and each trainable but untrained layer has a trainParam present
        for layerIdx, layer in enumerate(self.layers):
            if layer.trainable and not layer.isTrained:
                if not layer.name in trainParams:
                    raise Exception('Param file missing training params for layer: %s' % layer.name)

        dataLayer = self.layers[0]

        if maxlayer == -1:
            maxlayer = len(self.layers)-1
        trainedSomething = False
        for layerIdx, layer in enumerate(self.layers[:maxlayer+1]):
            if layer.trainable and not layer.isTrained:
                trainedSomething = True
                print '\n' + '*' * 40
                if onlyInit:
                    print 'just initializing layer %d - %s (%s)' % (layerIdx, layer.name, layer.layerType)
                else:
                    print 'training layer %d - %s (%s)' % (layerIdx, layer.name, layer.layerType)
                print '*' * 40 + '\n'

                layerTrainParams = trainParams[layer.name]
                layer.initialize(layerTrainParams, seed = 0)

                if onlyInit:
                    continue   # Skip training

                numExamples = layerTrainParams['examples']
                if quick and numExamples > 1000:
                    numExamples = 1000
                    print 'QUICK MODE: chopping training examples to 1000!'

                # Make sure layer.sees, data.stride, and data.patchSize are all same len
                assert len(layer.seesPatches) == len(dataLayer.patchSize)
                assert len(layer.seesPatches) == len(dataLayer.stride)

                # Get data
                print 'gc.collect found', gc.collect(), 'objects'
                trainRawDataLargePatches, trainRawDataPatches = self.getDataForLayer(layerIdx, numExamples)
                print 'Memory used to store trainRawDataLargePatches: %g MB' % (trainRawDataLargePatches.nbytes/1e6)
                print 'Memory used to store trainRawDataPatches:      %g MB' % (trainRawDataPatches.nbytes/1e6)
                del trainRawDataLargePatches
                print 'gc.collect found', gc.collect(), 'objects'

                # Push data through N-1 layers
                dataArrangementLayer0 = DataArrangement(sliceShape = layer.seesPatches, nSlices = numExamples)
                tic = Tic('forward prop')
                trainPrevLayerData, dataArrangementPrevLayer = self.forwardProp(trainRawDataPatches, dataArrangementLayer0, layerIdx=layerIdx-1)
                tic()
                print 'Memory used to store trainPrevLayerData: %g MB' % (trainPrevLayerData.nbytes/1e6)

                # Free the raw patches from memory
                del trainRawDataPatches
                print 'gc.collect found', gc.collect(), 'objects'

                # Train layer
                tic = Tic('train')
                layer.train(trainPrevLayerData, dataArrangementPrevLayer, layerTrainParams, quick = quick)
                tic()
                print 'training done for layer %d - %s (%s)' % (layerIdx, layer.name, layer.layerType)
                
                # Checkpoint and plot
                if saveDir:
                    fileFinal = os.path.join(saveDir, 'stackedLayers.pkl.gz')
                    fileTmp = fileFinal + '.tmp'
                    print 'Saving checkpoint...'
                    saveToFile(fileTmp, self)
                    os.rename(fileTmp, fileFinal)
                    print 'Saving these StackedLayers...'
                    self.printStatus()
                    print '... to %s' % fileFinal

                    print '\n   ' + '*' * 20
                    print '   * vis layer %d - %s (%s)' % (layerIdx, layer.name, layer.layerType)
                    print '   ' + '*' * 20 + '\n'
                    tic = Tic('vis')
                    #prefix = 'layer_%02d_%s_' % (layerIdx, layer.name)
                    #layer.plot(trainPrevLayerData, dataArrangementPrevLayer, saveDir, prefix)
                    self.visLayer(layerIdx, saveDir = saveDir, quick = quick)
                    tic()
                    print


        if not trainedSomething:
            print '\nNothing to train. Maybe it was already finished?'

    def _seesPixels(self, layer, dataLayer):
        seesPixels = tuple([ps + st * (sp-1) for sp,ps,st in zip(layer.seesPatches,dataLayer.patchSize, dataLayer.stride)])
        return seesPixels

    def getDataForLayer(self, layerIdx, numExamples):
        layer = self.layers[layerIdx]
        dataLayer = self.layers[0]
        
        # How many pixels this layer sees at once
        seesPixels = self._seesPixels(layer, dataLayer)

        tic = Tic('get patches')
        rawDataLargePatches = dataLayer.getData(seesPixels, numExamples, seed = 0)
        tic()

        rawDataPatches = self.getSampledAndStackedPatches(rawDataLargePatches, layer, dataLayer)

        return rawDataLargePatches, rawDataPatches

    def getSampledAndStackedPatches(self, largePatches, layer, dataLayer):
        seesPixels = self._seesPixels(layer, dataLayer)
        numExamples = largePatches.shape[1]

        # Reshape into patches
        stackedPatches = zeros((prod(dataLayer.patchSize), prod(layer.seesPatches)*numExamples))

        # BEGIN: 2D data assumption
        # Note: this only works for 2D data! Add other cases if needed.
        assert len(layer.seesPatches) == 2, 'Only works for 2D data for now!'
        counter = 0
        sp0,sp1 = layer.seesPatches
        ps0,ps1 = dataLayer.patchSize
        st0,st1 = dataLayer.stride
        for largePatchIdx in xrange(largePatches.shape[1]):
            thisLargePatch = reshape(largePatches[:,largePatchIdx], seesPixels)
            # Note: this code flattens in the default numpy
            # flattening order: C-order, or row-major order.
            for ii in xrange(sp0):
                for jj in xrange(sp1):
                    stackedPatches[:,counter] = thisLargePatch[(ii*st0):(ii*st0+ps0),(jj*st1):(jj*st1+ps1)].flatten()
                    counter += 1
        # just check last patch
        assert stackedPatches.shape[0] == len(thisLargePatch[(ii*st0):(ii*st0+ps0),(jj*st1):(jj*st1+ps1)].flatten())
        assert stackedPatches.shape[1] == counter
        # END: 2D data assumption

        return stackedPatches

    def optimalInputForUnit(self, unitIdx, startLayerIdx = 0, layerIdx = None, sublayer = None):
        if layerIdx is None: layerIdx = len(self.layers)-1
        layer = self.layers[layerIdx]
        if sublayer is None: sublayer = layer.nSublayers - 1  # max by default
        dataLayer = self.layers[0]

        seesPixels = self._seesPixels(layer, dataLayer)

        if self.layers[startLayerIdx].seesPatches != dataLayer.seesPatches:
            raise Exception('Probably starting too high in the network')

        x0 = ones(seesPixels)
        #currentRep, currentArrangement = self.forwardPropPixelSamples(data, startLayerIdx = 0, layerIdx = None, sublayer = None):
        #activationFunction = lambda x : self.forwardPropPixelSamples(x, startLayerIdx, layerIdx, sublayer)[0].flatten()[unitIdx]
        def activationFunction(xx):
            pixelPatch = reshape(xx.copy(), (prod(seesPixels), 1))
            pixelPatch /= (norm(pixelPatch) + 1e-12)
            rep, arrangement = self.forwardPropPixelSamples(pixelPatch, startLayerIdx = startLayerIdx,
                                                            layerIdx = layerIdx, sublayer = sublayer, quiet = True)
            return -rep.flatten()[unitIdx]   # negate to maximize!
        
        results = minimize(activationFunction,
                           x0.flatten(),
                           jac = False,    # have to estimate gradient
                           method = 'L-BFGS-B',
                           options = {'maxiter': 50, 'disp': False})
        xOpt = results['x']

        return xOpt
    
    def visLayer(self, layerIdx, sublayer = None, startLayerIdx = 0, numExamples = 100000, saveDir = None, show = False, quick = False):
        layer     = self.layers[layerIdx]
        if sublayer is None: sublayer = layer.nSublayers - 1  # max by default
        dataLayer = self.layers[0]

        prefix = 'layer_%02d_%s_' % (layerIdx, layer.name)
        if layer.nSublayers > 1: prefix += 's%d_' % sublayer
        seesPixels = self._seesPixels(layer, dataLayer)

        if quick:
            numExamples = 1000
            print 'QUICK MODE: chopping visLayer examples to 1000!'

        NODATAYET = True
        if NODATAYET:
            # Get data and forward prop
            rawDataLargePatches, rawDataPatches = self.getDataForLayer(layerIdx, numExamples)
            dataArrangementLayer0 = DataArrangement(sliceShape = layer.seesPatches, nSlices = numExamples)
        
            tic = Tic('forward prop')
            prevLayerData, dataArrangementPrevLayer = self.forwardProp(rawDataPatches, dataArrangementLayer0, layerIdx=layerIdx-1)
            activations, dataArrangement = self.forwardProp(prevLayerData, dataArrangementPrevLayer,
                                                            startLayerIdx = layerIdx-1, layerIdx=layerIdx, sublayer=sublayer)
            tic()

        # 0. Inputs
        plotImageData(rawDataLargePatches, seesPixels, saveDir, prefix = prefix + '0_input',
                      tileShape = (10,10), show = show)

        # 1. Top activations
        plotTopActivations(activations, rawDataLargePatches, seesPixels, saveDir = saveDir,
                           nActivations = 50, nSamples = 20, prefix = prefix + '1_topact', show = show)

        # 2. Numerically optimized inputs
        if layer.layerType == 'tica' and sublayer == 0:
            embeddingShape = layer.tica.hiddenLayerShape
        else:
            embeddingShape = layer.outputSize

        optInputs = zeros((prod(seesPixels), prod(embeddingShape)))
        unitsToVis = prod(embeddingShape)
        QUICKHACK = True
        if QUICKHACK:
            unitsToVis = 0
            print 'QUICKHACK: only visualizing first %d units!' % unitsToVis
        for ii in range(unitsToVis):
            optInputs[:,ii] = self.optimalInputForUnit(ii, startLayerIdx = startLayerIdx, layerIdx = layerIdx, sublayer = sublayer)
        tileShape = embeddingShape
        if len(tileShape) == 1:
            # single dimensional, so no meaningful embedding. Reshape to rougly 1.5:1 aspect ratio
            totalNum = prod(tileShape)
            rows = int(sqrt(totalNum * 1.5)) + 1
            tileShape = (int(ceil(totalNum/float(rows))), rows)
        plotImageData(optInputs, seesPixels, saveDir, prefix = prefix + '2_numopt',
                      tileShape = tileShape, show = show, onlyRescaled = True)

        # 3. layer activations
        plotActHist(activations, saveDir = saveDir, prefix = prefix + '3_acthist', show = show)
        plotActLines(activations, saveDir = saveDir, prefix = prefix + '3_actlines', show = show)

        # 4. layer activations
        plotGrayActivations(activations, number = 500, saveDir = saveDir, prefix = prefix + '4_actunroll', show = show)

        # 5. reshaped activations
        if len(embeddingShape) > 1:
            # Doesn't really make sense for 1D embeddings / non-embedded data
            plotReshapedActivations(activations, tileShape = (20,30), embeddingShape = embeddingShape,
                                    prefix = prefix + '5_actembed', saveDir = saveDir, show = show)

        # 6. Custom stuff per layer
        layer.plot(prevLayerData, dataArrangementPrevLayer, saveDir = saveDir, prefix = prefix + '9_layer_')

        

    def visAll(self, saveDir = None):
        for layerIdx, layer in enumerate(self.layers):
            if layer.trainable and not layer.isTrained:
                print '\nvis layer %2d: %s is trainable but not trained, so stopping' % (layerIdx, layer.name)
                return

            if layer.layerType in ('tica', 'downsample', 'lcn'):
                for sublayer in range(layer.nSublayers):
                    print '\nvis layer %2d (s%d): %s' % (layerIdx, sublayer, layer.name)
                    self.visLayer(layerIdx, sublayer, startLayerIdx = 1, saveDir = saveDir)    # hardcoded to 1!!



def check_2AE_backprop(checkHinting = False):
    random.seed(0)

    dimInput = 3
    dimRep1  = 2
    dimRep2  = 4
    numExamples = 5

    ll = []
    ll.append({'name':      'data',
               'type':      'data',
               'dataClass': 'DummyDataLayer',
               'outputSize': (dimInput,),
               #'imageSize': (512,512),
               #'patchSize': (8,8),
               #'stride':    (4,4),
               #'colors':    1,
               })
    ll.append({'name':         'ae1',
               'type':         'ae',
               'hiddenSize':   dimRep1,
               'beta':         3.0,
               'rho':          .01,
               'lambd':        .0001,
               })
    ll.append({'name':         'ae2',
               'type':         'ae',
               'hiddenSize':   dimRep2,
               'beta':         3.0,
               'rho':          .01,
               'lambd':        .0001,
               })

    sl = StackedLayers(ll)

    # random data
    XX = random.normal(.5, .25, (dimInput, numExamples))

    tp = {}
    tp['ae1'] = {'examples': 0,
                'initb1': 'zero',        # 'zero' for 0s, or 'approx' for an approx value to start at avg activation of rho
                'initW2asW1_T': False,
                'method': 'lbfgs',
                'maxFuncCalls': 300,
             }
    tp['ae2'] = tp['ae1']

    sl.train(tp, onlyInit = True)

    # Make biases non-zero for more generality
    sl.layers[1].b1 = random.normal(0, .1, sl.layers[1].b1.shape)
    sl.layers[1].b2 = random.normal(0, .1, sl.layers[1].b2.shape)
    sl.layers[2].b1 = random.normal(0, .1, sl.layers[2].b1.shape)
    sl.layers[2].b2 = random.normal(0, .1, sl.layers[2].b2.shape)
    
    #sl.forwardProp(XX, DataArrangement((1,), numExamples))

    singleExampleArrangement = DataArrangement((1,), 1)

    repUnit = 1  # which highest level unit to consider
    activationFunction = lambda xx : float(sl.forwardProp(xx, singleExampleArrangement, quiet = True)[0][repUnit])

    xx = XX[:,0]

    print 'sl.forwardProp: act is', activationFunction(xx)

    def actAndGrad(xx):
        reps = [(xx, None)]
        # Forward prop
        for ii in range(2):
            if checkHinting:
                rep,newDA,hint = sl.layers[ii+1].forwardProp(reps[ii][0], singleExampleArrangement, quiet = True, outputBpHint = True)
                reps.append((rep, hint))
            else:
                rep,newDA = sl.layers[ii+1].forwardProp(reps[ii][0], singleExampleArrangement, quiet = True)
                reps.append((rep, None))

        # Back prop to calculate gradient
        dqda_top = zeros(dimRep2)
        dqda_top[repUnit] = 1
        dqdas = [None, None, dqda_top]
        for ii in reversed(range(2)):
            rep = reps[ii][0]
            bpHint = reps[ii+1][1]
            if checkHinting:
                dqda,newDA = sl.layers[ii+1].backProp(dqdas[ii+1], rep, singleExampleArrangement, quiet = True,
                                                      verifyBpHint = True, bpHint = bpHint)
            else:
                dqda,newDA = sl.layers[ii+1].backProp(dqdas[ii+1], rep, singleExampleArrangement, quiet = True)
            dqdas[ii] = dqda
        return float(reps[-1][0][repUnit]), dqdas[0].flatten()

    print 'manual forwardProp: act is', actAndGrad(xx)[0]
    
    numericalCheckVectorGrad(actAndGrad, xx)



def tests():
    check_2AE_backprop(checkHinting = False)
    check_2AE_backprop(checkHinting = True)



if __name__ == '__main__':
    tests()

