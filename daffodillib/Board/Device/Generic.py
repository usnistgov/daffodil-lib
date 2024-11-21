"""
July 2023
Osama Yousuf
MTJ API for Daffodil Board 
"""

def gatecurrent(vg, vt): #Gate Voltage, Threshold voltage
    #This is a toy cutoff function to simulate the behavior of a transistor in this MTJ Arry
    if (vg > 3.3 + 1.7): # Defined by the manufacturer. You cannot apply more than 3.3Volts
        raise ValueError()
    if vg <= vt: # If you are below threshold you don't get any current
        return 0
    else:
        return 4000*(vg-vt)**2/(3-vt)**2 # above the threshold you get current. the maximum is about 4 mA

def voltageevent(vg,vt,vwrite,vcol,vrow,gdevice,goff,gon,activ,D): #this function calculates the current through a 1T-1R model device 
    if activ == 0: # this checks if the device is selcted
        return gdevice,0
    icurrent=(vcol-vrow)*gdevice # this uses the voltage to guess what the device is based on the conductance
    if icurrent == 0 or vg-min(vcol,vrow) < vt: # if there's no current just go home
        return gdevice, 0
    
    # current limit

    # print('voltageevent', icurrent, vcol, vrow, gdevice)
    currentlimit=gatecurrent(vg-min(vcol,vrow), vt) #we use the gatecurrent function to check what the max current allowed is from the transistor
    # vref=1.7
    # # compliance mode, set saturation current correctly
    # if (vcol - vref > 0): # Vref is sourcing current, TIA has to rise, max. vg V (5 V ideally)
    #     currentlimit = vref / D 
    # else: # sinking, TIA has to fall, min. 0 V
    #     currentlimit = abs(5 - vref) / D
    # # go from A to mA for compatibility since Gs are set in uA
    # currentlimit = currentlimit * 10**6
    # The current had to be inverted in order to match how the physical chip devices were switching
    if abs(icurrent) > currentlimit: #if we're above the limit we just use the limit current
        icurrent = currentlimit*icurrent/abs(icurrent) # we make sure to copy the sign
    if icurrent/gdevice >= vwrite and gdevice == gon: #here we measure the voltage across the device
        return goff, icurrent # RESET the device into OFF (low G) state
    elif icurrent/gdevice <= -vwrite and gdevice < gon: # SET the device into ON (high G) state
        return gon, icurrent
    else:
        return gdevice, icurrent  # we can also just return the current and leave conductance the same

class Generic:
    """
        This is the Generic Device Class. It's most important characteristic is that you can select a kernel and specify voltages on the rows and the columns.
        When you apply an event to the Generic system, it will respond to the those voltages. It will respond by a) changing the device state and b) producing currents.

        For easier debug, you can pass smaller lists of voltages. It will default to the first few rows/columns. Others will automatically be zero. 

        The event definition can be augmented more. Probably the most important thing to add is TIME, or pulse width, to specify how long voltages are applied.

        This class is currently modeled in a pseudo-physical way. It assumes certain properties of the 1T-1R array, namely it is possible to select one device and you never have complete leakage paths.

        This would not work with a passive array or a different transistor array. For these, you would need a spice model. If your spice model class however specifies input voltages and output currents, it could comply with the Generic model class definition. 
    """
    
    def __init__(self, numkernel=32, xdim=25, ydim=25, vt=0.5):
        self.vt=vt # this is the threshold of the transistors 
        
        self.numkernel=numkernel #number of kernels in the array
        self.kernelxdim=xdim #column dimension of a kernel
        self.kernelydim=ydim #row dimension of a current
        
        self.rowcurrents=[] #initialize lists of row currents
        self.columncurrents=[] # initialize lists of column currents
        
        self.rowvoltages=[] #initlaize lists of row voltages
        self.columnvoltages=[] # initialize lists of column voltages
        self.gatevoltages=[] # initialize lists of gate voltages
        
        self.selectedkernel=0 #the default kernel is 0

        self.currentscale = 10**6 # to compensate for DPOT resistance compatibility with this model
        self.vwrite = 0.75

        vread = 0.3 # Todo: Pass this from outside
        self.resetG = 40 // vread # initial (off state) conductance state
        self.setG = 70 // vread
        
        for i in range(xdim): # inititialze with zero bias
            self.columncurrents.append(0)
            self.columnvoltages.append(0) 
            self.gatevoltages.append(0)
        for i in range(ydim):
            self.rowcurrents.append(0)
            self.rowvoltages.append(0)
        
        self.all_kernels=[] #initialize the kernen list

        for i in range(self.numkernel): #initialize the kernel class. we have now created the actual memory array. 
            self.all_kernels.append(self.kernel(self.kernelxdim,self.kernelydim,self.vt,self.vwrite,self.resetG,self.setG))
        
        self.name = 'Generic'

    def selectkernel(self, value):
        #this function lets you select a kernel. They are ordered from 1 to N
        #0-32 CA1, MSB, LSB, CA0, RA1, R0 The kernel can also be represented as a bit string based on the TTL command that asserts the kernel from the FPGA. 
        if value not in range(self.numkernel):
            raise ValueError()
        self.selectedkernel=value

    def retrievekernel(self, value):
        #you can ask what kernel you're using
        return self.all_kernels[self.selectedkernel].kern
            
    def event(self,colactiv,rowactiv):
        #This function has all the action. It uses the applied biases to decide the change in states and the generated currents.
        #Note, the current returned is the current of the PREVIOUS state, not the END state of the event. 
        self.columncurrents, self.rowcurrents = self.all_kernels[self.selectedkernel].biasupdate(self.gatevoltages,self.columnvoltages,self.rowvoltages, colactiv, rowactiv, self.dpot_r)
        
    class kernel:
        """
            The kernel class contains the actual device physics, along with the above definition functions in the Generic file. When you pass the voltages to the individual devices, you get current generation and conductance changes.
            If you want to model a different device start here. You could use, for example, jump tables or other physics based models.
            This model implicitly assumes conductanes are represented in microsiemens and currents therefore in microamps.
        """
        def __init__(self, xdim=25, ydim=25, vt=0.7, vwrite=0.7, resetG=50, setG=100):
            self.kern=[] # initialize the list of weights
            self.xdim=xdim # column dimension
            self.ydim=ydim # row dimension
            self.vt=vt #threshold bias of transistors 
            self.vwrite=vwrite
            self.G=resetG
            self.setG=[]
            self.resetG=[]
            for i in range(xdim):
                self.kern.append([])
                self.setG.append([])
                self.resetG.append([])
                for j in range (ydim):
                    self.kern[i].append(resetG) # this initliazes the kernel to 50 microsiemens, which is assumed to be the low conductance state for our Generic model. 
                    self.setG[i].append(setG)
                    self.resetG[i].append(resetG)

        def biasupdate(self, gatevoltages, columnvoltages, rowvoltages, colactiv, rowactiv, D):
            rowcurrents=[] # initliaze lists of values for row and column currents
            columncurrents=[]
            update=0 #initialize placeholder variable for whether or not to change a device conductance 
            current=0 #a variable for integrating currents in a row or column. 
            
            for i in range(self.xdim): # we initliaze everything to have zero current
                columncurrents.append(0) 
            for i in range(self.ydim):
                rowcurrents.append(0)
                
            for i in range(len(gatevoltages)): # we now do a loop over all devices
                for j in range(len(rowvoltages)):
                    
                    update, current = voltageevent(gatevoltages[i],self.vt,self.vwrite,columnvoltages[i],rowvoltages[j],self.kern[i][j],self.resetG[i][j],self.setG[i][j],colactiv[i]*rowactiv[j], D)
                    self.kern[i][j] = update # if there is enough voltage across the device, it will update. 

                    # this next code block helps deal with the zero edge case. 0 conductance is impossible and can lead to division by zero issues. We set the abosolute minimum as 0.1 microsiemens
                    # since we limit all steps sizes to be +/- 1 microsiemen, we also dealwith the 1.1 microsiemen edge case. 
                    if self.kern[i][j] < 1:
                        self.kern[i][j] = 0.1
                    if self.kern[i][j]==1.1:
                        self.kern[i][j]=1
                    
                    columncurrents[i]+=current # here we integrate the currents. 
                    rowcurrents[j]+=current

            return columncurrents, rowcurrents # we return the currents      
