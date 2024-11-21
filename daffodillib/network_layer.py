import matplotlib.pyplot as plt
import daffodillib.IVcurve as IVcurve
import daffodillib.read_array as read_array
import daffodillib.outerproduct as outerproduct
import numpy as np
import time
import daffodillib.parameters as prm

"""
These functions import the board and supportive functions.

The key thing imported, is the controller and it's dependencies. What this allows is for you to implement programs.

Using the dependent models of the parts, all communication should occur exactly as it would be either the real
Daffodil Board or with the model API.

If the imported library for the real board doesn't include certain libraries, such as the functions mapping
ADC/DAC values to physical quantities. Those would need to be externally created.

For this Daffodil API, we assume that the unit of voltage is volts and current is uA. 
"""

class Linear:
    """
    Class for realizing a fully-connected neural network linear layer.
    """
    def __init__(self, board, shape=[2,2], weight_shape=[25*2, 25*2], vread=0.3, vset=0.8, vreset=0.8, vref=1.7, vgate=5, encoding='forward', mode='block', offsets=[(0, 0, 0)]):
        
        """Initialize a linear neural network layer.

        Parameters
        ----------
        board : Board.controller.Daffodil_Base
            Daffodil board object (can be physical or simulated).
        shape : list[int, int]
            Dimensions of the layer in terms of kernels. A layer with 50 rows and 50 columns can be realized by passing [2, 2].
        weight_shape : list[int, int]
            Dimensions of the layer in terms of individual devices.
        vread : float
            The read voltage.
        vset : float
            The voltage used for SET pulses.
        vreset : float
            The voltage used for RESET pulses.
        vref : float
            The reference voltage for the ADCs.
        vgate : float
            The voltage for the gates.
        encoding : str
            Whether or not the layer should be mapped for Daffodil's forward configuration or backward.
        mode : str
            How a layer should be mapped to a kernel. The provided implementation supports `block` mode of operation, where a layer is mapped to contiguous blocks of devices within a kernel.
        offsets : list[tuples]
            A list of parameters compatible with the provided `mode`. For `block` mode, this is simply [(k, x, y)] where (x, y) indicate the (column, row) within kernel k to which the layer is mapped. 
        """
        
        self.board=board
        self.kernels=[i[0] for i in offsets]
        self.kernels = list(set(self.kernels))

        if len(shape) == 2:
            self.shape=shape
        else:
            raise ValueError("shape is not list of two values")

        self.xdim=shape[0]*self.board.xdim
        self.ydim=shape[1]*self.board.ydim

        self.array=[]

        for i in range(self.shape[0]):
            holdlist=[]
            for j in range(self.shape[1]):
                holdlist.append(self.kernels[j+self.shape[1]*i])
            self.array.append(holdlist)
            
        self.vread=vread
        self.vset=vset
        self.vreset=vreset
        self.vgate=vgate
        self.vref = vref

        self.encoding = encoding
        self.mode = mode
        self.weight_shape=weight_shape
        if (self.mode == 'block'): 
            # Block mode encoding: the layer is mapped to a contiguous block starting from (kernel, column, row)/(k, x, y)
            assert len(offsets) == 1 and len(offsets[0]) == 3
            self.xoffset = offsets[0][1]
            self.yoffset = offsets[0][2]
            # safety/sanity checks
            assert self.xoffset < self.board.xdim
            assert self.yoffset < self.board.ydim
        else:
            # Other modes can be implemented here
            raise ValueError(f"Layer mode {self.mode} not implemented")
            
    def read_array(self, vread, vref, slice=False):
        """Read states of kernels mapping the given neural network layer.

        Parameters
        ----------
        vread : float
            The read voltage.
        vref : float
            The reference voltage for the ADCs.
        slice : bool
            If True, the sliced subkernel to which the layer is mapped is returned. If False, entire Kernels are returned.
        Returns
        -------
        readarray : list[list[list[float]]]
            Three-dimensional array representing read-back device states over all kernels involved in layer mapping.
        """
        configure=True
        readarray = []
        if (self.mode == 'block'):
            for kernel in self.kernels:
                reads=read_array.read_kernel(self.board, kernel, vread, self.vgate, vref, weight_shape=[25, 25], xoffset=0, yoffset=0, configure=configure)
                if (self.encoding == 'forward'):
                    x_slice = self.weight_shape[0]
                    y_slice = self.weight_shape[1]
                else: 
                    x_slice = self.weight_shape[1]
                    y_slice = self.weight_shape[0]
                reads = np.array(reads)
                if (slice): reads = reads[self.xoffset:self.xoffset+x_slice, self.yoffset:self.yoffset+y_slice]
                readarray.append(reads)
        # reading for other modes can be implemented here
        return readarray

    def forward_pass(self, inputvector):
        """Perform a vector-matrix multiplication operation on the kernel mapping the given neural network layer using forward configuration.
        Input voltages are applied on columns and output currents are read from rows of the crossbar.

        Parameters
        ----------
        inputvector : list[floats]
            A list of voltages to be applied on input columns of the kernel mapping the given network layer.
        Returns
        -------
        currents : list[float]
            An array representing accumulated currents on rows corresponding to the mapped network layer.
        """
        inputvector = inputvector.copy()
        if self.vref == 0 and min(inputvector) < 0:
            raise ValueError("Layer is currently set to be strictly positive! Enable vref!")
        if max(list(map(abs,inputvector))) > 1:
            raise ValueError("Largest input can only be 1!")
        if len(inputvector) > self.xdim:
            raise ValueError("Too big input dimension!")
    
        if (self.mode == 'block'):
            currentstemp=[]
            vector=inputvector
            currents=[]
            for p in range(self.ydim):
                currents.append(0)
            # Padding if there's x offset
            # Forward pass = apply on columns (x), measure on rows (y)
            for p in range(self.xoffset):
                vector.insert(0, 0)
            for p in range(self.xdim-len(inputvector)):
                vector.append(0)
            for p in range(self.xdim):
                vector[p] = vector[p]+self.vref

            for i in range(self.shape[0]):
                configure = True
                for j in range(self.shape[1]):
                    currentstemp=currentstemp + read_array.vmm_kernel_forward(self.board,self.array[i][j],vector[(self.board.xdim)*i:self.board.xdim*(i+1)],self.vgate,self.vref,self.weight_shape,self.xoffset,self.yoffset,configure)
                    if j == 0:
                        configure = False
                for p in range(self.ydim):
                    currents[p]+=currentstemp[p]
                currentstemp=[]

            return currents[self.yoffset:self.yoffset+self.weight_shape[1]]

        # other modes can be implemented here

    def out_prod_update(self, yvector, xvector, vgate):

        """Update device states using the outerproduct configuration

        Parameters
        ----------
        yvector : list[float]
            A list of voltages to be applied on input rows of the kernel mapping the given network layer.
        xvector : list[float]
            A list of voltages to be applied on input columns of the kernel mapping the given network layer.
        vgate : float
            The voltage for the gates.
        Returns
        -------
        readarray : list[list[list[float]]]
            Three-dimensional array representing read-back device states over all kernels involved in layer mapping.
        """

        if len(yvector) > self.ydim:
            raise ValueError("Too big x input dimension!")    
        if len(xvector) > self.xdim:
            raise ValueError("Too big y input dimension!")

        # Handling for x, y offsets + modes
        if (self.mode == 'block'):
            for i in range(self.xoffset):
                xvector.insert(0, 0)

            for i in range(self.yoffset):
                yvector.insert(0, 0)

            for p in range(self.xdim-len(xvector)):
                xvector.append(0)
            for p in range(self.ydim-len(yvector)):
                yvector.append(0)

            assert len(xvector) == self.board.xdim and len(yvector) == self.board.ydim

            for i in range(self.shape[0]):
                for j in range(self.shape[1]):
                    self.board.set_kernel(self.array[i][j])
                    outerproduct.outer_product(self.board,self.vset,self.vreset,vgate,yvector[(self.board.xdim)*i:self.board.xdim*(i+1)],xvector[self.board.ydim*j:self.board.ydim*(j+1)])

        # Other encoding modes can be added here

    def load_weights_outerproduct_parallel(self, weights, vgate):
        num_pulses = 1
        for x in range(weights.shape[0]):
            weight_vector = weights[x].astype(np.int32).tolist()
            xvector = np.zeros(weights.shape[0], dtype=np.int32)
            yvector = np.zeros((len(weight_vector)), dtype=np.int32)
            xvector[x] = -num_pulses
            yvector[:len(weight_vector)] = weight_vector
            yvector[yvector == 1] = num_pulses # SET
            yvector[yvector == 0] = -num_pulses # RESET
            self.out_prod_update(yvector.tolist(), xvector.tolist(), vgate)

    def plot_weights(self, vread, vref, slice=False):
        """Read the kernel using `read_array` and generate a simple conductance map plot.

        Parameters
        ----------
        vread : float
            The read voltage.
        vref : float
            The reference voltage for the ADCs.
        slice : bool
            If True, the sliced subkernel to which the layer is mapped is returned. If False, entire Kernels are returned.
        Returns
        -------
        readarray : list[list[list[float]]]
            Three-dimensional array representing read-back device states over all kernels involved in layer mapping.
        """
        arrs = self.read_array(vread, vref, slice)
        for idx, arr in enumerate(arrs):
            fig = plt.figure()
            arr = arr * 10**6
            imgplot = plt.imshow(arr.T, origin='lower', vmin=0, vmax=300)
            plt.xlabel('Column (#)')
            plt.ylabel('Row (#)')
            plt.title(f'Kernel {self.kernels[idx]}')
            cbar = fig.colorbar(imgplot)
            cbar.set_label('Conductance (µS)')
        return arrs