#! /usr/bin/env python

'''
[JBY] Utilities for learning.
Some stuff copied from https://github.com/lisa-lab/DeepLearningTutorials/blob/master/code/utils.py
'''

''' This file contains different utility functions that are not connected 
in anyway to the networks presented in the tutorials, but rather help in 
processing the outputs into a more understandable way. 

For example ``tile_raster_images`` helps in generating a easy to grasp 
image from a set of samples or weights.
'''

import pdb
import numpy
from numpy import mgrid, array, ones, zeros, linspace, random, reshape
import Image

from mayavi import mlab
from mayavi.mlab import points3d, contour3d, plot3d
from tvtk.api import tvtk



def scale_to_unit_interval(ndar,eps=1e-8):
    ''' Scales all values in the ndarray ndar to be between 0 and 1 '''
    ndar = ndar.copy()
    ndar -= ndar.min()
    ndar *= 1.0 / (ndar.max()+eps)
    return ndar


def scale_all_rows_to_unit_interval(ndar,eps=1e-8):
    ''' Scales each row in the 2D array ndar to be between 0 and 1 '''
    assert(len(ndar.shape) == 2)
    ndar = ndar.copy()
    ndar = (ndar.T - ndar.min(axis=1)).T
    ndar = (ndar.T / (ndar.max(axis=1)+eps)).T
    return ndar


def scale_some_rows_to_unit_interval(ndar, rowIdx, eps = 1e-8):
    ''' Scales rows given by rowIdx in the 2D array ndar to be between 0 and 1'''
    assert(len(ndar.shape) == 2)
    ndar = ndar.copy()
    for ii in rowIdx:
        ndar[ii,:] -= ndar[ii,:].min()
        ndar[ii,:] /= (ndar[ii,:].max() + 1e-8)
    return ndar


def tile_raster_images(X, img_shape, tile_shape, tile_spacing = (0,0), 
                       scale_rows_to_unit_interval = True, scale_colors_together = False,
                       output_pixel_vals = True, hilights = None):
    '''
    Transform an array with one flattened image per row, into an array in 
    which images are reshaped and layed out like tiles on a floor.

    This function is useful for visualizing datasets whose rows are images, 
    and also columns of matrices for transforming those rows 
    (such as the first layer of a neural net).

    :type X: a 2-D ndarray or a tuple of 4 channels, elements of which can 
    be 2-D ndarrays or None;
    :param X: a 2-D array in which every row is a flattened image.

    :type img_shape: tuple; (height, width)
    :param img_shape: the original shape of each image

    :type tile_shape: tuple; (rows, cols)
    :param tile_shape: the number of images to tile (rows, cols)
    
    :param output_pixel_vals: if output should be pixel values (i.e. int8
    values) or floats

    :param scale_rows_to_unit_interval: if the values need to be scaled before
    being plotted to [0,1] or not

    :param hilights: list of hilights to apply to each tile. 


    :returns: array suitable for viewing as an image.  
    (See:`PIL.Image.fromarray`.)
    :rtype: a 2-d array with same dtype as X.

    '''

    assert(len(img_shape) == 2 or (len(img_shape) == 3 and img_shape[2] == 3)) # grayscale or RGB color
    assert len(tile_shape) == 2
    assert len(tile_spacing) == 2

    isColor = len(img_shape) == 3

    if hilights is not None:
        assert hilights.shape[0] == X.shape[0]
        if len(hilights.shape) == 1:
            hilightIsColor = False
        elif hilights.shape[1] == 3:
            hilightIsColor = True
        else:
            raise Exception('expected hilights.shape to be (X,) or (X,3), but it is %s' % hilights.shape)

        if not isColor and hilightIsColor:
            # promote data to be color
            promotedX = numpy.repeat(X, 3, axis=1)
            promotedImgShape = (img_shape[0], img_shape[1], 3)
            return tile_raster_images(promotedX, promotedImgShape, tile_shape, tile_spacing,
                                      scale_rows_to_unit_interval, scale_colors_together,
                                      output_pixel_vals, hilights)
        if isColor and not hilightIsColor:
            # promote hilight to be color
            promotedHilight = tile(numpy.atleast_2d(hilights).T, (1,3))
            return tile_raster_images(X, img_shape, tile_shape, tile_spacing,
                                      scale_rows_to_unit_interval, scale_colors_together,
                                      output_pixel_vals, promotedHilight)

        # Now this must be true
        assert isColor == hilightIsColor

    #pdb.set_trace()

    # The expression below can be re-written in a more C style as 
    # follows : 
    #
    # out_shape    = [0,0]
    # out_shape[0] = (img_shape[0]+tile_spacing[0])*tile_shape[0] -
    #                tile_spacing[0]
    # out_shape[1] = (img_shape[1]+tile_spacing[1])*tile_shape[1] -
    #                tile_spacing[1]
    out_shape = [(ishp + tsp) * tshp for ishp, tshp, tsp 
                        in zip(img_shape, tile_shape, tile_spacing)]

    if isColor:
        # massage to expected tuple form
        #assert(X.shape[1] % 3 == 0)
        #nPerChannel = X.shape[1] / 3

        if output_pixel_vals:
            dt = 'uint8'
        else:
            dt = X.dtype
        if str(dt) not in ('uint8', 'float32'):
            raise Exception('color only works for uint8 or float32 dtype, not %s' % dt)

        if scale_rows_to_unit_interval and scale_colors_together:
            X = scale_all_rows_to_unit_interval(X)

        X = X.reshape(X.shape[0], img_shape[0], img_shape[1], img_shape[2])
        X = (X[:,:,:,0].reshape(X.shape[0], img_shape[0] * img_shape[1]),
             X[:,:,:,1].reshape(X.shape[0], img_shape[0] * img_shape[1]),
             X[:,:,:,2].reshape(X.shape[0], img_shape[0] * img_shape[1]),
             None, #numpy.ones(X[:,0:nPerChannel].shape, dtype=dt), # hardcode complete opacity
             )
        if hilights is not None:
            hilights = (hilights[:,0], hilights[:,1], hilights[:,2], None)


    if isinstance(X, tuple):
        assert len(X) == 4
        if hilights is None: hilights = (None, None, None, None)
        # Create an output numpy ndarray to store the image
        if output_pixel_vals:
            #out_array = numpy.zeros((out_shape[0], out_shape[1], 4), dtype='uint8')
            out_array = numpy.ones((out_shape[0], out_shape[1], 4), dtype='uint8') * 51
        else:
            #out_array = numpy.zeros((out_shape[0], out_shape[1], 4), dtype=X.dtype)
            out_array = numpy.ones((out_shape[0], out_shape[1], 4), dtype=X.dtype) * .2

        #colors default to 0, alpha defaults to 1 (opaque)
        if output_pixel_vals:
            channel_defaults = [51,51,51,255]
        else:
            channel_defaults = [.2,.2,.2,1.]

        for i in xrange(4):
            if X[i] is None:
                # if channel is None, fill it with zeros of the correct 
                # dtype (unless it's the alpha channel)
                dt = out_array.dtype
                if output_pixel_vals:
                    dt = 'uint8'
                #if i == 3:
                #    # alpha channel
                #    out_array[:,:,i] = numpy.ones(out_shape, dtype=dt)+channel_defaults[i]
                #    pdb.set_trace()
                #else:
                out_array[:,:,i] = numpy.zeros(out_shape, dtype=dt)+channel_defaults[i]
            else:
                # use a recurrent call to compute the channel and store it 
                # in the output
                doScaleRows = scale_rows_to_unit_interval
                if isColor and scale_colors_together:
                    # already scaled whole rows
                    doScaleRows = False
                out_array[:,:,i] = tile_raster_images(X[i], img_shape[0:2], tile_shape,
                                                      tile_spacing, doScaleRows, False,
                                                      output_pixel_vals, hilights[i])
        return out_array

    else:
        # if we are dealing with only one channel 
        H, W = img_shape
        Hs, Ws = tile_spacing

        # generate a matrix to store the output
        dt = X.dtype
        if output_pixel_vals:
            dt = 'uint8'
            #out_array = numpy.zeros(out_shape, dtype=dt)
            out_array = numpy.ones(out_shape, dtype=dt) * 51
        else:
            out_array = numpy.ones(out_shape, dtype=dt) * .2


        for tile_row in xrange(tile_shape[0]):
            for tile_col in xrange(tile_shape[1]):
                if tile_row * tile_shape[1] + tile_col < X.shape[0]:
                    if scale_rows_to_unit_interval and not (isColor and scale_colors_together):
                        # if we should scale values to be between 0 and 1 
                        # do this by calling the `scale_to_unit_interval`
                        # function
                        this_img = scale_to_unit_interval(X[tile_row * tile_shape[1] + tile_col].reshape(img_shape))
                    else:
                        this_img = X[tile_row * tile_shape[1] + tile_col].reshape(img_shape)
                    # add the slice to the corresponding position in the 
                    # output array
                    c = 1
                    if output_pixel_vals:
                        c = 255
                    # Set slightly bigger region to hilight color
                    if hilights is not None:
                        out_array[
                            tile_row * (H+Hs):tile_row*(H+Hs)+H+Hs,
                            tile_col * (W+Ws):tile_col*(W+Ws)+W+Ws
                            ] \
                            = hilights[tile_row * tile_shape[1] + tile_col] * c
                    out_array[
                        tile_row * (H+Hs)+Hs/2:tile_row*(H+Hs)+H+Hs/2,
                        tile_col * (W+Ws)+Ws/2:tile_col*(W+Ws)+W+Ws/2
                        ] \
                        = this_img * c
        return out_array



def pil_imagesc(arr, epsilon = 1e-8, saveto = None):
    '''Like imagesc for Octave/Matlab, but using PIL.'''

    imarray = numpy.array(arr, dtype = numpy.float32)
    imarray -= imarray.min()
    imarray /= (imarray.max() + epsilon)
    image = Image.fromarray(imarray * 255).convert('L')
    if saveto:
        image.save(saveto)



cubeEdges = array([[0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0],
                   [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0],
                   [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 1]])



def plot3DShapeFromFlattened(blob, blobShape,
                             saveFilename = None, smoothed = False, visSimple = True,
                             plotThresh = 0, figSize = (300,300)):
    '''Plots a flattened 3D shape of size blobShape inside a frame.'''

    if type(blobShape) is list or type(blobShape) is tuple:
        Nx,Ny,Nz = blob.shape
    else:
        Nx,Ny,Nz = blobShape,blobShape,blobShape

    return plot3DShape(reshape(blob, (Nx,Ny,Nz)), saveFilename, smoothed, visSimple,
                       plotThresh, figSize)



def plot3DShape(blob, saveFilename = None, smoothed = False, visSimple = True,
                plotThresh = 0, figSize = (300,300), plotEdges = True, rotAngle = 24):
    '''Plots a 3D shape inside a frame.'''

    Nx,Ny,Nz = blob.shape
    indexX, indexY, indexZ = mgrid[0:Nx,0:Ny,0:Nz]
    edges = (array([Nx,Ny,Nz]) * cubeEdges.T).T
    
    fig = mlab.figure(0, size = figSize)
    mlab.clf(fig)
    fig.scene.interactor.interactor_style = tvtk.InteractorStyleTerrain()
    if plotEdges:
        plot3d(edges[0,:], edges[1,:], edges[2,:], color=(.5,.5,.5),
               line_width = 0,
               representation = 'wireframe',
               opacity = 1)

    # Convert from bool to real if necessary
    if type(blob[0]) is numpy.bool_ or blob.dtype == numpy.dtype('bool'):
        blob = blob * 1

    if smoothed:
        # Pad with zeros to close, large negative values to make edges sharp
        blob = numpy.pad(blob, 1, 'constant', constant_values = (-1000,))
        contour3d(blob, extent=[0,10,0,10,0,20], contours=[.1], color=(1,1,1))
    else:
        print saveFilename
        mn = blob.min()
        mx = blob.max()
        idx = (blob > plotThresh).flatten()
        pdb.set_trace()
        print mn, mx, sum(idx)
        pdb.set_trace()
        if sum(idx) > 0:
            if visSimple:
                pts = points3d(indexX.flatten()[idx] + .5,
                               indexY.flatten()[idx] + .5,
                               indexZ.flatten()[idx] + .5,
                               ones(sum(idx)) * .9,
                               #((blob-mn) / (mx-mn) * .9)[idx],
                               color = (1,1,1),
                               mode = 'cube',
                               scale_factor = 1.0)
            else:
                pts = points3d(indexX.flatten()[idx] + .5,
                               indexY.flatten()[idx] + .5,
                               indexZ.flatten()[idx] + .5,
                               #ones(sum(idx)) * .9,
                               ((blob-mn) / (mx-mn) * .9)[idx],
                               colormap = 'bone',
                               #color = (1,1,1),
                               mode = 'cube',
                               scale_factor = 1.0)
            lut = pts.module_manager.scalar_lut_manager.lut.table.to_array()
            tt = linspace(0, 255, 256)
            lut[:, 0] = tt*0 + 255
            lut[:, 1] = tt*0 + 255
            lut[:, 2] = tt*0 + 255
            lut[:, 3] = tt
            pts.module_manager.scalar_lut_manager.lut.table = lut

    #mlab.view(57.15, 75.55, 50.35, (7.5, 7.5, 7.5)) # nice view
    #mlab.view(24, 74, 33, (5, 5, 5))      # Default older RBM
    mlab.view(rotAngle, 88, 45, (5, 5, 10))      # Good for EF

    mlab.draw()
    
    if saveFilename:
        mlab.savefig(saveFilename)




def justPlotBoolArray(blob, figSize = (300,300)):
    '''Plots a 3D boolean array with points where array is True'''

    Nx,Ny,Nz = blob.shape

    indexX, indexY, indexZ = mgrid[0:Nx,0:Ny,0:Nz]
    
    fig = mlab.figure(0, size = figSize)
    mlab.clf(fig)
    fig.scene.interactor.interactor_style = tvtk.InteractorStyleTerrain()

    idx = blob
    print idx.sum(), 'points'
    
    if idx.sum() > 0:
        idxFlat = idx.flatten()
        pts = points3d(indexX.flatten()[idxFlat] + .5,
                       indexY.flatten()[idxFlat] + .5,
                       indexZ.flatten()[idxFlat] + .5,
                       ones(sum(idxFlat)) * .9,
                       #((blob-mn) / (mx-mn) * .9)[idx],
                       color = (1,1,1),
                       mode = 'cube',
                       scale_factor = 1.0)
        lut = pts.module_manager.scalar_lut_manager.lut.table.to_array()
        tt = linspace(0, 255, 256)
        lut[:, 0] = tt*0 + 255
        lut[:, 1] = tt*0 + 255
        lut[:, 2] = tt*0 + 255
        lut[:, 3] = tt
        pts.module_manager.scalar_lut_manager.lut.table = lut

    #mlab.view(57.15, 75.55, 50.35, (7.5, 7.5, 7.5)) # nice view
    #mlab.view(24, 74, 33, (5, 5, 5))      # Default older RBM
    mlab.view(24, 88, 45, (5, 5, 10))      # Good for EF

    mlab.draw()
