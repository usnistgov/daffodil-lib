import matplotlib.pyplot as plt
import numpy as np
import time
"""
These functions import the board and supportive functions.

The key thing improted, is the controller and it's dependencies. What this allows is for you to implement programs.

Using the dependent models of the parts, all communication should occur exactly as it would be either the real
Daffodil Board or with the model API.

If the imported library for the real board doesn't include certain libraries, such as the functions mapping
ADC/DAC values to physical quantities. Those would need to be externally created.

For this Daffodil API, we assume that the unit of voltage is volts and current is uA. 
"""

"""
The read_array.py program is designed to do the most basic readout and matrix operations the board.

it includes
1) reading a kernel
2) reading all the kernels
3) doing forward/backward vector matrix multiplication on a kernel

"""

def read_kernel(board, kernel, vread, vgate, vref, weight_shape=[25, 25], xoffset=0, yoffset=0, configure=True):
    """
    This operation is designed, in the forward pass configuration, to give you all the device conductances.
    Forward pass means applying voltage on the columns and reading out currents on the rows. 
    After specifying a kernel, a read voltage, and a gate voltage, you will get back the device conductances.
    """



    dac_code_read = board.dac_invertvout(vread+vref) #this converts read voltage to dac bit code
    dac_gate_code = board.dac_invertvout(abs(vgate)) #this converts gate voltage to dac bit code
    ref_code = board.dac_invertvout(abs(vref))

    vreadinvert = board.dac_calcvout(dac_code_read)-board.dac_calcvout(ref_code) #this checks that you actually are applying bias. if you use a very small value it might be rounded to zero

    if vreadinvert == 0: #don't have zero read voltage!
        raise ValueError ("Cannot have zero read voltage!")

    board.set_kernel(kernel) #this selects the kernel
    if configure: # if you are doing a lot of reads, you might not want to configure every time
        board.setrefopamp(ref_code) #this sets the reference for the amplifiers to ref_code
        board.config_forward_pass() #this activates all the rows and columns available
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=1
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=1

    #this instantiates our bias lists
    gatebiases=[]
    rowbiases=[]
    colbiases=[]
    
    for i in range(board.xdim): #we start with zeros
        gatebiases.append(board.dac_invertvout(abs(board.vground)))
        colbiases.append(ref_code)
    for i in range(board.ydim):
        rowbiases.append(ref_code)


    #everything is now set to vref
    board.setgatedacs(gatebiases)
    board.setcoldacs(colbiases)
    board.setrowdacs(rowbiases)

    #this is where we store our conductances
    conductances=[]

    disable_unused = True
    if (disable_unused): 
        row_first = yoffset
        row_last = yoffset + weight_shape[1]
        col_first = xoffset
        col_last = xoffset + weight_shape[0]

        for i in range(board.xdim):
            board.COL_EN_tobe[i]=0
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=0

        # Disable unused rows/cols from the Kernel
        for i in range(col_first, col_last):
            board.COL_EN_tobe[i]=1
        for i in range(row_first, row_last):
            board.ROW_EN_tobe[i]=1
    else:
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=1
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=1


    #now we measure column by column and readout on the rows
    #only ONE column is allowed to have it's gates biased
    #for safety, we also keep unaccessed columns at zero asserted bias
    for i in range(board.xdim):
        gatebiases[i] = dac_gate_code #specify the gate bias
        colbiases[i] = dac_code_read #specify the column bias
        board.setgatedacs(gatebiases) #set the gate biases
        board.setcoldacs(colbiases) #set the column biases
        board.event() #assert an event
        conductances.append(board.retrievecurrents()) #add currents to the list. They are still ADC numbers
        for p in range(board.ydim):# since we have the current ADC code numbers we need to use the voltage and the potentiometer value to make them conductances
            conductances[i][p]=(board.adc_predict_voltage(conductances[i][p])-board.dac_calcvout(ref_code))/board.pots[p]/vreadinvert #we extract the predicted voltage, and use transimpedance+applied bias to get conductance

        gatebiases[i] = board.dac_invertvout(abs(board.vground)) #we specify these again as zero bias
        colbiases[i] = ref_code
    #when we leave the loop, we want to be sure to turn everything back off to zero. 
    board.setgatedacs(gatebiases) #set the gate biases
    board.setcoldacs(colbiases)

    #we return conductances
    return conductances

def read_all_kernels(board,vread,vgate,vref=1.7):
    #for this, we use the read kernel operation to get ALL the kernel conductances. 
    originalkernel=board.selected_kernel #let's remember the original kernel
    kernels=[] #this is our list of kernel values

    configure=True #let's configure the first time
    for i in range(board.kernels):
        #let's read out all the kernels
        kernels.append(read_kernel(board,i,vread,vgate,vref,configure))
        configure = False # we don't need to configure again

    board.set_kernel(originalkernel)#let's go back to our original kernel 
    return kernels

def plot_kernel(kernel, fname='kernel.png'):
    #plot a single kernel! 
    fig = plt.figure()
    imgplot = plt.imshow(kernel)
    plt.axis('off')
    fig.tight_layout()
    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(imgplot, cax=cbar_ax)
    # plt.show()
    plt.savefig(fname)

def read_and_plot_kernels(board,vread,vgate,vref=1.7, fname='kernels.png'):
    #this does the same thing as just read kernels, but instead of reading kernels it plots them! 
    kernels = read_all_kernels(board,vread,vgate,vref)
    fig = plt.figure()
    for p in range(len(kernels)):
        ax = fig.add_subplot(4,8,p+1)
        # imgplot = plt.imshow(kernels[p], vmin=0, vmax=100*10**-6)
        imgplot = plt.imshow(kernels[p])
        plt.axis('off')
        fig.tight_layout()
    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(imgplot, cax=cbar_ax)
    plt.savefig(fname)

def vmm_kernel_forward(board, kernel, readvoltages, vgate, vref, weight_shape, xoffset, yoffset, configure=True, log=False):
    #This is used to perform vector matrix multiplication in the forward configuraiton. That means we assert bias on ALL the columns and read out from the rows.
    #if you submit a less than full kernel size length of readvoltages, then the remainders are set to zero. 

    disable_unused = True

    board.set_kernel(kernel) #let's pick our kernel
    if configure: #do we need to update our gate and column biases? if so, let's do it
        gatebiases=[] #these instantiate our lists 
        colbiases=[]

        for i in range(board.xdim): #this sets all gate biases to the specified gate bias while also padding the colbiases layer
            gatebiases.append(board.dac_invertvout(abs(vgate)))
            colbiases.append(0) #TODO: re-check
        
        for p in range(len(readvoltages)): #since the colbiases layer is padded, we can send this function lists of readvoltages which are smaller than full size 
           colbiases[p]=board.dac_invertvout(abs(readvoltages[p]))

        #you can specify a vref in the VMM function. This allows negative numbers to be multiplied into the array.
        #readvoltage values equal to vref will produce zero current and the ADC will readout a voltage of vref. 
        ref_code = board.dac_invertvout(abs(vref))
        board.setrefopamp(ref_code)
        #configures the forward pass and enables all rows/columns
        board.config_forward_pass()

        if (disable_unused): 
            row_first = yoffset
            row_last = yoffset + weight_shape[1]
            col_first = xoffset
            col_last = xoffset + weight_shape[0]

            for i in range(board.xdim):
                board.COL_EN_tobe[i]=0
                gatebiases[i]=board.dac_invertvout(abs(board.vground))
            for i in range(board.ydim):
                board.ROW_EN_tobe[i]=0

            # Disable unused rows/cols from the Kernel
            for i in range(col_first, col_last):
                board.COL_EN_tobe[i]=1
                gatebiases[i]=board.dac_invertvout(vgate)
            for i in range(row_first, row_last):
                board.ROW_EN_tobe[i]=1
        else:
            for i in range(board.xdim):
                board.COL_EN_tobe[i]=1
            for i in range(board.ydim):
                board.ROW_EN_tobe[i]=1

        #sets all the dacs
        board.setgatedacs(gatebiases)
        board.setcoldacs(colbiases)

    # Temp
    if (log):
        print('vref', vref)
        print('readvoltages', readvoltages, len(readvoltages))
        voltagelist = []
        for i in colbiases:
            voltagelist.append(board.dac_calcvout(i)-board.dac_calcvout(ref_code))
        print('colbiases', colbiases, len(colbiases))
        print('voltagelist (actual applied voltage across device)', voltagelist, len(voltagelist))

        print('COL_EN', board.COL_EN_tobe)
        print('ROW_EN', board.ROW_EN_tobe)

        exit()

    board.event() #we have an event

    currents=board.retrievecurrents() #we retrieve the currents 

    #as mentioned above, to get the correct current, you have to extract the reference bias and then use the transimpedance to get the current
    for y in range(len(currents)):
        currents[y]=(board.adc_predict_voltage(currents[y])-board.adc_predict_voltage(board.dac_invertvout(abs(vref))))/board.pots[y]

    if (board.sim_device and board.sim_device.name == 'MTJ'):
        # inject noise
        std = 0
        currents = np.random.normal(currents, std).tolist()

    # print(board.COL_EN_tobe)
    # print(board.ROW_EN_tobe)
    # print(readvoltages)
    # exit()
    #we return the currents 
    return currents

def vmm_kernel_backward(board, kernel, readvoltages, vgate=3.3, vref=1.7, configure=True, log=False):
    #This is used to perform vector matrix multiplication in the backwards configuraiton. That means we assert bias on ALL the rows and read out from the columns.
    #if you submit a less than full kernel size length of readvoltages, then the remainders are set to zero.
    board.set_kernel(kernel) #let's pick our kernel
    if configure: #do we need to update our gate and row biases? if so, let's do it
        gatebiases=[] #these instantiate our lists 
        rowbiases=[]
    
        for i in range(board.xdim): #this sets all gate biases to the specified gate bias while also padding the rowbiases layer
            gatebiases.append(board.dac_invertvout(abs(vgate)))
        for i in range(board.ydim):
            rowbiases.append(0)

        for p in range(len(readvoltages)): #since the rowbiases layer is padded, we can send this function lists of readvoltages which are smaller than full size 
           rowbiases[p]=board.dac_invertvout(abs(readvoltages[p]))

        #you can specify a vref in the VMM function. This allows negative numbers to be multiplied into the array.
        #readvoltage values equal to vref will produce zero current and the ADC will readout a voltage of vref. 
        ref_code = board.dac_invertvout(abs(vref))
        board.setrefopamp(ref_code)
        #configures the forward pass and enables all rows/columns
        board.config_backward_pass()
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=1
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=1

        #sets all the dacs
        board.setgatedacs(gatebiases)
        board.setrowdacs(rowbiases)

    # Temp
    if (log):
        print('vref', vref)
        print('readvoltages', readvoltages, len(readvoltages))
        voltagelist = []
        for i in rowbiases:
            voltagelist.append(-board.dac_calcvout(i)+board.dac_calcvout(ref_code))
        print('rowbiases', rowbiases, len(rowbiases))
        print('voltagelist (actual applied voltage across device)', voltagelist, len(voltagelist))

    board.event() #we have an event

    currents=board.retrievecurrents() #we retrieve the currents
    # as mentioned above, to get the correct current, you have to extract the reference bias and then use the transimpedance to get the current
    for y in range(len(currents)):
        currents[y]= -(board.adc_predict_voltage(currents[y])-board.adc_predict_voltage(board.dac_invertvout(abs(vref))))/board.pots[y]

    #we return the currents 
    return currents    