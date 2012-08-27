#! /usr/bin/env python


import os, pdb, gzip
from PIL import Image
from numpy import *
import cPickle as pickle

pathToData = '../data/atari/mspacman'

def getFilesIn(dir):
    fileList = []
    for dd,junk,files in os.walk(dir, followlinks=True):
        for file in files:
            fileList.append(os.path.join(dd, file))
    return fileList



def randomSampleMatrix(filterNames, Nw = 10, Nsamples = 10):
    files = getFilesIn(pathToData)

    filteredFiles = []
    for filterName in filterNames:
        filteredFiles += filter(lambda x : filterName in x, files)

    filteredFiles = list(set(filteredFiles))
    filteredFiles.sort()

    Nimages = len(filteredFiles)
    if Nimages == 0:
        raise Exception('Nimages == 0, maybe try running from a different directory?')
    
    im = Image.open(filteredFiles[0])
    size = im.size

    # select random windows
    maxJ = size[0] - Nw
    maxI = size[1] - Nw
    randomSamples = vstack((random.randint(0, Nw, Nsamples),
                            random.randint(0, maxI+1, Nsamples),
                            random.randint(0, maxJ+1, Nsamples))).T
    randomSamples.sort(0)   # for efficient loading and unloading of images into memory. Re-randomize before returing
    
    imageMatrix = zeros((Nsamples, Nw * Nw), dtype = float32)
    
    imIdx = None
    for count, sample in enumerate(randomSamples):
        idx, ii, jj = sample
        if imIdx != idx:
            #print 'loading', idx
            im = Image.open(filteredFiles[idx]).convert('L')
            imIdx = idx
            if size != im.size:
                raise Exception('Expected everything to be the same size but %s != %s' % (repr(size), repr(im.size)))
            #im.show()
        cropped = im.crop((jj, ii, jj + Nw, ii + Nw))
        imageMatrix[count,:] = cropped.getdata()
        #cropped.show()

    imageMatrix /= 255   # normalize to 0-1 range
    random.shuffle(imageMatrix)
    return imageMatrix



def saveToFile(filename, obj):
    ff = gzip.open(filename, 'wb')
    pickle.dump(obj, ff, protocol = -1)
    print 'saved to', filename
    ff.close()



def main():
    print 'Looking for data in: ', pathToData
    random.seed(0)

    trainFilter = ['frame_000001', 'frame_000002', 'frame_000003']
    testFilter  = ['frame_000004', 'frame_000005', 'frame_000006']

    saveToFile(pathToData + 'train_02_50.pkl.gz',    randomSampleMatrix(trainFilter, Nw = 02, Nsamples = 50))
    saveToFile(pathToData + 'test_02_50.pkl.gz',     randomSampleMatrix(testFilter,  Nw = 02, Nsamples = 50))
    saveToFile(pathToData + 'train_02_50000.pkl.gz', randomSampleMatrix(trainFilter, Nw = 02, Nsamples = 50000))
    saveToFile(pathToData + 'test_02_50000.pkl.gz',  randomSampleMatrix(testFilter,  Nw = 02, Nsamples = 50000))

    saveToFile(pathToData + 'train_04_50.pkl.gz',    randomSampleMatrix(trainFilter, Nw = 04, Nsamples = 50))
    saveToFile(pathToData + 'test_04_50.pkl.gz',     randomSampleMatrix(testFilter,  Nw = 04, Nsamples = 50))
    saveToFile(pathToData + 'train_04_50000.pkl.gz', randomSampleMatrix(trainFilter, Nw = 04, Nsamples = 50000))
    saveToFile(pathToData + 'test_04_50000.pkl.gz',  randomSampleMatrix(testFilter,  Nw = 04, Nsamples = 50000))

    saveToFile(pathToData + 'train_10_50.pkl.gz',    randomSampleMatrix(trainFilter, Nw = 10, Nsamples = 50))
    saveToFile(pathToData + 'test_10_50.pkl.gz',     randomSampleMatrix(testFilter,  Nw = 10, Nsamples = 50))
    saveToFile(pathToData + 'train_10_50000.pkl.gz', randomSampleMatrix(trainFilter, Nw = 10, Nsamples = 50000))
    saveToFile(pathToData + 'test_10_50000.pkl.gz',  randomSampleMatrix(testFilter,  Nw = 10, Nsamples = 50000))

    saveToFile(pathToData + 'train_15_50.pkl.gz',    randomSampleMatrix(trainFilter, Nw = 15, Nsamples = 50))
    saveToFile(pathToData + 'test_15_50.pkl.gz',     randomSampleMatrix(testFilter,  Nw = 15, Nsamples = 50))
    saveToFile(pathToData + 'train_15_50000.pkl.gz', randomSampleMatrix(trainFilter, Nw = 15, Nsamples = 50000))
    saveToFile(pathToData + 'test_15_50000.pkl.gz',  randomSampleMatrix(testFilter,  Nw = 15, Nsamples = 50000))
    
    saveToFile(pathToData + 'train_28_50.pkl.gz',    randomSampleMatrix(trainFilter, Nw = 28, Nsamples = 50))
    saveToFile(pathToData + 'test_28_50.pkl.gz',     randomSampleMatrix(testFilter,  Nw = 28, Nsamples = 50))
    saveToFile(pathToData + 'train_28_50000.pkl.gz', randomSampleMatrix(trainFilter, Nw = 28, Nsamples = 50000))
    saveToFile(pathToData + 'test_28_50000.pkl.gz',  randomSampleMatrix(testFilter,  Nw = 28, Nsamples = 50000))



if __name__ == '__main__':
    main()