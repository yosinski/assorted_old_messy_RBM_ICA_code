#! /usr/bin/env python

import os, errno
import time



def mkdir_p(path):
    '''Behaves like `mkdir -P` on Linux.
    From: http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python'''
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise



def dictPrettyPrint(dd, prefix = '', width = 20):
    '''Prints a dict in key:   val format, one per line.'''
    for key in sorted(dd.keys()):
        keystr = '%s:' % (key if isinstance(key,basestring) else repr(key))
        valstr = '%s' % repr(dd[key])
        formatstr = '%%-%ds %%s' % width
        print prefix + (formatstr % (keystr, valstr))



def importFromFile(filename, objectName):
    try:
        with open(filename, 'r') as ff:
            fileText = ff.read()
    except IOError:
        print 'Could not open file "%s". Are you sure it exists?' % filename
        raise

    try:
        exec(compile(fileText, 'contents of file: %s' % filename, 'exec'))
    except:
        print 'Tried to execute file "%s" but got this error:' % filename
        raise
        
    if not objectName in locals():
        raise Exception('file "%s" did not define the %s variable' % (layerFilename, objectName))

    return locals()[objectName]



def relhack():
    '''Utter Hack to reload local modules (modules with relative filenames and
    paths in home directory).
    '''
    import sys
    from os.path import expanduser
    homedir = expanduser("~")
    toReload = set()
    sysmoditems = list(sys.modules.iteritems())
    for name,mod in sysmoditems:
        if mod is not None:
            filename = getattr(mod, '__file__', None)
            if filename:
                if (filename[0] != '/' or homedir in filename) and not '__' in mod.__name__:
                    toReload.add(mod)
                    #print 'Adding:', mod.__name__, '   ', filename
    for mod in toReload:
        print 'Reloading: %s' % repr(mod)
        reload(mod)



def getFilesIn(dir):
    fileList = []
    for dd,junk,files in os.walk(dir, followlinks=True):
        for file in files:
            fileList.append(os.path.join(dd, file))
    return fileList



class Stopwatch(object):
    def __init__(self):
        self._start = time.time()

    def elapsed(self):
        return time.time() - self._start

globalStopwatch = Stopwatch()

def makePt(st, stopwatch = None):
    '''Prepend the time since the start of the run to the given string'''

    if string is None:
        stopwatch = globalStopwatch
    
    return '%05.3f_%s' % (stopwatch.elapsed(), st)

pt = lambda st : makePt(st)



class Counter(object):
    def __init__(self):
        self._count = -1

    def count(self):
        self._count += 1
        return self._count

globalCounter = Counter()

def makePc(st, counter = None):
    '''Prepend a counter since the start of the run to the given string'''

    if counter is None:
        counter = globalCounter
    
    return '%03d_%s' % (counter.count(), st)

class MakePc(object):
    def __init__(self, counter = None):
        if counter is None:
            counter = globalCounter
        self.counter = counter

    def __call__(self, st):
        return '%03d_%s' % (self.counter.count(), st)
    
pc = lambda st : makePc(st)



class Tic(object):
    def __init__(self, descrip = ''):
        self._descrip = descrip
        self._startw = time.time()
        self._startc = time.clock()

    def __call__(self):
        print 'Time to %s: %.3fs (wall) %.3fs (cpu)' % (self._descrip, time.time()-self._startw, time.clock()-self._startc)
