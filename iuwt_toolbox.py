import numpy as np
from scipy import ndimage
from scipy.optimize import curve_fit
from scipy.signal import fftconvolve
import time
import pylab as pb

try:
    import pycuda.autoinit
    import pycuda.gpuarray as gpuarray
    from scikits.cuda.fft import Plan
    from scikits.cuda.fft import fft
    from scikits.cuda.fft import ifft
except:
    print "Pycuda unavailable - GPU mode will fail."

def fft_convolve(in1, in2, use_gpu=False, conv_mode="linear"):
    """
    This function determines the convolution of two inputs using the FFT. Contains an implementation for both CPU
    and GPU.

    INPUTS:
    in1         (no default):           Array containing one set of data, possibly an image.
    in2         (no default):           Gpuarray containing the FFT of the PSF.
    use_gpu     (default = True):       Boolean parameter which allows specification of GPU use.
    conv_mode   (default = "linear")    Mode specifier for the convolution.
    """

    # NOTE: Circular convolution assumes a periodic repetition of the input. This can cause edge effects. Linear
    # convolution pads the input with zeros to avoid this problem but is consequently heavier on computation and
    # memory.

    if use_gpu:
        if conv_mode=="linear":
            fft_in1 = gpu_r2c_fft(in1, padded=True, load_gpu=True)
            fft_in2 = in2

            conv_in1_in2 = fft_in1*fft_in2

            conv_in1_in2 = gpu_c2r_ifft(conv_in1_in2, is_padded=True)

            return conv_in1_in2
        elif conv_mode=="circular":
            fft_in1 = gpu_r2c_fft(in1, padded=False, load_gpu=True)
            fft_in2 = in2

            conv_in1_in2 = fft_in1*fft_in2

            conv_in1_in2 = (gpu_c2r_ifft(conv_in1_in2, is_padded=False))

            return conv_in1_in2
    else:
        if conv_mode=="linear":
            return fftconvolve(in1, in2, mode='same')
        elif conv_mode=="circular":
            return np.real(np.fft.fftshift(np.fft.ifft2(in2*np.fft.fft2(in1))))

def gpu_r2c_fft(in1, padded=True, load_gpu=False):
    """
    This function makes use of the scikits implementation of the FFT for GPUs to take the real to complex FFT.

    INPUTS:
    in1         (no default):       The array on which the FFT is to be performed.
    padded      (default=True):     Boolean specifier for whether or not input must be padded.
    load_gpu    (default=False):    Boolean specifier for whether the result is to be left on the gpu or not.

    OUTPUTS:
    gpu_out1        (no default):   The gpu array containing the result.
        OR
    gpu_out1.get()  (no default):   The result from the gpu array.
    """

    if padded:
        padded_size = 2*np.array(in1.shape)

        output_size = 2*np.array(in1.shape)
        output_size[1] = 0.5*output_size[1] + 1

        gpu_in1 = np.zeros([padded_size[0],padded_size[1]])
        gpu_in1[0:padded_size[0]/2,0:padded_size[1]/2] = in1
        gpu_in1 = gpuarray.to_gpu_async(gpu_in1.astype(np.float32))
    else:
        output_size = np.array(in1.shape)
        output_size[1] = 0.5*output_size[1] + 1

        gpu_in1 = gpuarray.to_gpu_async(in1.astype(np.float32))

    gpu_out1 = gpuarray.empty([output_size[0],output_size[1]], np.complex64)
    gpu_plan = Plan(gpu_in1.shape, np.float32, np.complex64)
    fft(gpu_in1, gpu_out1, gpu_plan)

    if load_gpu:
        return gpu_out1
    else:
        return gpu_out1.get()

def gpu_c2r_ifft(in1, is_gpuarray=True, is_padded=True):
    """
    This function makes use of the scikits implementation of the FFT for GPUs to take the complex to real IFFT.

    INPUTS:
    in1         (no default):       The array on which the IFFT is to be performed.
    is_gpuarray (default=True):     Boolean specifier for whether or not input is on the gpu.
    is_padded   (default=True):     Boolean specifier for whether or not input is padded.

    OUTPUTS:
    gpu_out1.get()[out1]            The data of the IFFT, sliced according to is_padded.
    """

    if is_gpuarray:
        gpu_in1 = in1
    else:
        gpu_in1 = gpuarray.to_gpu_async(in1.astype(np.float32))

    output_size = np.array(in1.shape)
    output_size[1] = 2*(output_size[1]-1)

    if is_padded:
        out1_slice = tuple(slice(0.5*sz,1.5*sz) for sz in 0.5*output_size)
    else:
        out1_slice = tuple(slice(0,sz) for sz in output_size)

    gpu_out1 = gpuarray.empty([output_size[0],output_size[1]], np.float32)
    gpu_plan = Plan(output_size, np.complex64, np.float32)
    ifft(gpu_in1, gpu_out1, gpu_plan, True)

    return gpu_out1.get()[out1_slice]

if __name__ == "__main__":
    for i in range(1):
        delta = np.empty([512,512])
        delta[256,256] = 1
        fftdelta = gpu_r2c_fft(delta, load_gpu=True)

        a = np.random.randn(512,512)
        b = gpu_r2c_fft(a, padded=True, load_gpu=True)
        c = gpu_c2r_ifft(b, is_padded=True)

        d = fft_convolve(a, fftdelta, use_gpu=True, conv_mode='circular')
        e = fft_convolve(a, delta, use_gpu=False, conv_mode='circular')

        # pb.figure(1)
        # pb.subplot(211)
        # pb.imshow(d)
        #
        # pb.subplot(212)
        # pb.imshow(a)
        # pb.show()

        print d, e, a


# def threshold_array(in1, max_scale, initial_run=False):
#     """
#     This function performs the thresholding of the values in in1 at various sigma levels. When
#     initialrun is True, thresholding will be performed at 5 sigma uniformly. When it is False, thresholding is
#     performed at 3 sigma for scales less than maxscale. An additional 3 sigma threshold is also returned for maxscale.
#     Accepts the following paramters:
#
#     in1                     (no default):   The array to which the threshold is to be applied.
#     max_scale               (no default):   The maximum scale of of the decomposition.
#     initialrun              (default=False):A boolean which determines whether thresholding is at 3 or 5 sigma.
#     """
#
#     # The following establishes which thresholding level is of interest.
#
#     if initial_run:
#         sigma_level = 5
#     else:
#         sigma_level = 3
#
#     # The following loop iterates up to maxscale, and calculates the thresholded components using the functionality
#     # of np.where to create masks at each scale. Components of interest are determined by whether they are within
#     # some sigma of the threshold level, which is defined to be the median of the absolute values of the current
#     # scale divided by some factor, 0.6754.
#
#     for i in range(max_scale):
#         threshold_level = (np.median(np.abs(in1[i,:,:]))/0.6754)
#
#         if (i==(max_scale-1))&~initial_run:
#             mask = np.where((np.abs(in1[i,:,:])<(sigma_level*threshold_level)),0,1)
#             thresh3sigma = (mask*in1[i,:,:] + np.abs(mask*in1[i,:,:]))/2
#             sigma_level = 5
#
#         mask = np.where((np.abs(in1[i,:,:])<(sigma_level*threshold_level)),0,1)
#         in1[i,:,:] = (mask*in1[i,:,:] + np.abs(mask*in1[i,:,:]))/2
#
#     # The following simply determines which values to return.
#
#     if initial_run:
#         return in1
#     else:
#         return in1, thresh3sigma