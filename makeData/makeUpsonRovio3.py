#! /usr/bin/env python

import os, pdb, gzip
from PIL import Image
from numpy import *
import cPickle as pickle
import ipdb as pdb
from util.dataLoaders import saveToFile
from makeUpsonRovio1 import getFilesIn


trainFilter = ['u2_backward_0_person',
               'u2_backward_2',
               'u2_forward_1',
               'u2_stationary_0_person',
               'u2_strafe_r_0',
               'u2_strafe_r_2',
               'u2_turn_r_0',
               'u3_green_circle_close_1',
               'u3_green_circle_far_1',
               'u3_green_star_close_1',
               'u3_green_star_far_1',
               'u3_red_circle_close_1',
               'u3_red_circle_far_1',
               'u3_red_star_close_1',
               'u3_red_star_far_1',
               ]

#print 'TODO: Fix symlink bug where no old data is being included??'
# ipdb> labelMatrix.sum(1)
#array([ 519.,    0.,  487.,  513.,  449.,  551.,    0.,    0.,    0.,
#                  0.,    0.,    0.,    0.])

testFilter  = ['u2_backward_1',
               'u2_backward_3',
               'u2_forward_0_person',
               'u2_stationary_1',
               'u2_strafe_r_1',
               'u2_strafe_r_3',
               'u2_turn_r_1',
               'u3_green_circle_close_2',
               'u3_green_circle_far_2',
               'u3_green_circle_far_high',
               'u3_green_star_close_2',
               'u3_green_star_far_2',
               'u3_green_star_far_high',
               'u3_red_circle_close_2',
               'u3_red_circle_far_2',
               'u3_red_circle_far_high',
               'u3_red_star_close_2',
               'u3_red_star_far_2',
               'u3_red_star_far_high'
               ]

exploreFilter = ['u3_all_shapes_tour',
                 'u3_jason_laptop',
                 ]

labelStrings = ['circle',
                'star',
                'red',
                'green',
                'close',
                'far',
                'high',
                'backward',
                'forward',
                'stationary',
                'strafe',
                'turn',
                'person']




def randomSampleMatrixWithLabels(filterNames, color, Nw = (10,10), Nsamples = 10, seed = None, rng = None,
                                 imgDirectory = '../data/upson_rovio_3/imgfiles'):
    '''color = True or False
    It is an error to give both a seed and an rng'''

    if seed is not None and rng is not None:
        raise Exception('must specify at most one of (seed, rng)')

    if rng is None:
        rng = random.RandomState(seed)      # if seed is None, this takes its seed from timer

    files = getFilesIn(imgDirectory)

    filteredFiles = []
    for filterName in filterNames:
        filteredFiles += filter(lambda x : filterName in x, files)

    #print 'CHECK: does this include symlinked files??'
    #pdb.set_trace()

    filteredFiles = list(set(filteredFiles))
    filteredFiles.sort()

    Nimages = len(filteredFiles)
    if Nimages == 0:
        raise Exception('Nimages == 0, maybe try running from a different directory?')
    
    im = Image.open(filteredFiles[0])
    size = im.size

    # select random windows
    maxJ = size[0] - Nw[1]   # size in x = j direction
    maxI = size[1] - Nw[0]   # size in y = i direction
    randomSamples = vstack((rng.randint(0, Nimages, Nsamples),
                            rng.randint(0, maxI+1, Nsamples),
                            rng.randint(0, maxJ+1, Nsamples))).T
    # for efficient loading and unloading of images into memory. Re-randomize before returing
    randomSamples = randomSamples[argsort(randomSamples[:,0]), :]
    
    if color:
        imageMatrix = zeros((Nsamples, Nw[0] * Nw[1] * 3), dtype = float32)
    else:
        imageMatrix = zeros((Nsamples, Nw[0] * Nw[1]), dtype = float32)
    labelMatrix = zeros((Nsamples, len(labelStrings)))
    
    imIdx = None
    for count, sample in enumerate(randomSamples):
        idx, ii, jj = sample
        if imIdx != idx:
            #print 'loading', idx
            if color:
                im = Image.open(filteredFiles[idx])
            else:
                im = Image.open(filteredFiles[idx]).convert('L')
            filename = os.path.basename(filteredFiles[idx])
            labels = array([st in filename for st in labelStrings], dtype=int)
            imIdx = idx
            if size != im.size:
                raise Exception('Expected everything to be the same size but %s != %s' % (repr(size), repr(im.size)))
            #im.show()

        cropped = im.crop((jj, ii, jj + Nw[1], ii + Nw[0]))
        # For color images, flattens to [ii_r ii_g ii_b ii+1_r ii+1_g ii+1_b ...]
        imageMatrix[count,:] = array(cropped.getdata()).flatten()
        labelMatrix[count,:] = labels[:]
        #cropped.show()

    imageMatrix /= 255   # normalize to 0-1 range

    # shuffle both matrices together
    shufIdx = rng.permutation(range(Nsamples))
    imageMatrix = imageMatrix[shufIdx,:]
    labelMatrix = labelMatrix[shufIdx,:]

    return imageMatrix, labelMatrix, labelStrings



def main():
    sav = saveToFile
    rsm = randomSampleMatrixWithLabels
    flnm = '../data/upson_rovio_3/%s.pkl.gz'

    # Random Seeds: use the window width, so 50000 data set
    # contains the 50 data set, and so bw and color sample the same
    # patches. Train vs. test are different though, due to the
    # negative.

    big = 123456
    
    # grayscale
    #for Nw in [2, 4, 8, 10, 15, 20, 28, 30, 40]:
    for Nw in [2, 3, 4, 6, 8, 10, 15, 20, 25, 28, 30, 40]:
        sav(flnm % ('train_%02d_50_1c' % Nw),      rsm(trainFilter,         Nw, False, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('test_%02d_50_1c' % Nw),       rsm(testFilter,      big-Nw, False, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('explore_%02d_50_1c' % Nw),    rsm(exploreFilter, 2*big-Nw, False, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('train_%02d_50000_1c' % Nw),   rsm(trainFilter,         Nw, False, Nw = (Nw,Nw), Nsamples = 50000))
        sav(flnm % ('test_%02d_50000_1c' % Nw),    rsm(testFilter,      big-Nw, False, Nw = (Nw,Nw), Nsamples = 50000))
        sav(flnm % ('explore_%02d_50000_1c' % Nw), rsm(exploreFilter, 2*big-Nw, False, Nw = (Nw,Nw), Nsamples = 50000))

    # color (same seeds as grayscale so same patches are selected)
    #    Runs out of memory on largest: 40_50000_3c (test or train)
    #for Nw in [2, 4, 8, 10, 15, 20, 28, 30, 40]:
    for Nw in [2, 3, 4, 6, 8, 10, 15, 20, 25, 28, 30, 40]:
        sav(flnm % ('train_%02d_50_3c' % Nw),      rsm(trainFilter,         Nw, True, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('test_%02d_50_3c' % Nw),       rsm(testFilter,      big-Nw, True, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('explore_%02d_50_3c' % Nw),    rsm(exploreFilter, 2*big-Nw, True, Nw = (Nw,Nw), Nsamples = 50))
        sav(flnm % ('train_%02d_50000_3c' % Nw),   rsm(trainFilter,         Nw, True, Nw = (Nw,Nw), Nsamples = 50000))
        sav(flnm % ('test_%02d_50000_3c' % Nw),    rsm(testFilter,      big-Nw, True, Nw = (Nw,Nw), Nsamples = 50000))
        sav(flnm % ('explore_%02d_50000_3c' % Nw), rsm(exploreFilter, 2*big-Nw, True, Nw = (Nw,Nw), Nsamples = 50000))



if __name__ == '__main__':
    main()
