"""
This class imports functions from various modelled parts of the Daffodil board. They can be indepently specified.

In the API framework, properties of the Daffodil board can in principle be passed to the parts and vis-a-versa to control the operation.

Daffodil-lib does not have a class model for all the parts. For example, the transimpedance amplifiers are modeled as ideal resistors with zero input resistance. 
"""

from .Components.AD5391BSTZ5 import AD5391BSTZ5_Sim as DAC_sim
from .Components.ADS7950SBDBT import ADS7950SBDBT_Sim as ADC_sim
from .Components.AD5391BSTZ5 import AD5391BSTZ5_Phys as DAC_phys
from .Components.ADS7950SBDBT import ADS7950SBDBT_Phys as ADC_phys
from .Components.AD8403 import AD8403_Sim as DPOT_sim
from .Components.AD8403 import AD8403_Phys as DPOT_phys
from .Device.Generic import Generic

import numpy as np
import ctypes
import ctypes.util
import time as t
import os

class Daffodil_Base:
    """
    Pure virtual class for Daffodil board. Provides common functionalities for downstream classes for board interaction.
    """
    def __init__(self, ADC, DAC, DPOT):
        """Initialize a Board object.

        Parameters
        ----------
        ADC : Board.Components.ADS7950SBDBT
            Part class for the analog-to-digital converters (ADCs).
        DAC : Board.Components.ADS7950SBDBT
            Part class for the digital-to-analog converters (DACs).
        DPOT : Board.Components.AD8403
            Part class for the digital potentiometers (DPOTs).
        """

        self.vground=1.7 #In Daffodil 2, the chip is floating at 1.7 V.
        self.vmax=3.3+self.vground #This board is designed to work with 3.3V CMOS. This is the digital logic supply voltage
        self.refvoltages=2.5 #This is the reference voltage given to the ADC. See part TI-REF5025
        self.highbias=5 #This is the absolute highest bias on the board passed to the DAC
    
        self.kernels=32 #This is the number of kernels that the board can support. 
        self.xdim=25 #This is the number of columns the board can support
        self.ydim=25 #This is the number of rows the board can support
        self.channels=16
        self.dac_num=5

        self.curr_vref = None # This is the on-board vref for the opamp (DAC2 Channel 9). It is set inside the setrefopamp() function.
        self.curr_mode = None

        self.dpots=[] # this initializes the potentiometers, which define the transimpedance for current measurement
        for i in range(7):
            self.dpots.append(DPOT(i)) # The pots can be tuned from 1 to 10 kohm. The actual expressed unit, however, is V/uA
            # the amplifiers for these are ADA4891-4WARUZ-R7

        self.dacs=[] # initiliaze the DAC list
        self.adcs=[] # initiliaze the ADC list
        
        for i in range(7): #7 ADCs are on the board
            self.adcs.append(ADC(self.refvoltages, i))
        for i in range(5): #5 DACs are on the board
            self.dacs.append(DAC(i + 8))

        self.adc_gain_mode = self.adcs[0].gain #we call the gain mode from one of the adcs
        self.dac_gain_mode = self.dacs[0].all_channels[0].m #we call the gain from from one of the dacs
        self.dac_offset = self.dacs[0].all_channels[0].c #we call the offset from one of the dacs
        self.dac_curr_limit = self.dacs[0].all_channels[0].curr_limit #we call the current limit so we can know if we are out of bounds

        #the below is a bit string that configures all the switches to select a kernel. 
        self.RA0=0
        self.RA1=0
        self.CA0=0
        self.LSB=0
        self.MSB=0
        self.CA1=0

        self.selected_kernel = 0
        
        self.swfix_en = False
                
        #these are all the row and col EN strings. the "tobe" is used because they are not asserted all the time, usually only during an event
        self.COL_EN_tobe=[]
        self.ROW_EN_tobe=[]

        #the default is to use all rows and columns. 1 is used, 0 is unused. 
        for i in range(self.xdim):
            self.COL_EN_tobe.append(1)
        for i in range(self.ydim):
            self.ROW_EN_tobe.append(1)

        #this configures the muxes

        self.config_muxes()

        # self.read_pulse_len = 128 * 200 * 25 * 4*10*10*2 
        # self.read_pulse_len = 128
        #spi clocks are 4 times slower than clk, each transfer takes as many as 200 spi clocks, there are 25 ADC channels to read at once, 4x because python is slow
        self.read_pulse_len = 128 * 200 * 25 * 4*10*10*2
        self.write_pulse_len = 5  # idk how long this should be
        # 80 DAC channels, 4 times slower SPI clock relative to CPU clock, 24 clocks per transaction

    def invert_dpot_rout(self, rout):
        """Invert the provided resistance value to corresponding digital code for the DPOT.

        Parameters
        ----------
        rout : float
            The resistance to be inverted.
        Returns
        -------
        Ds : list[floats]
            A list of digital codes corresponding to inverted resistances over each DPOT on the Board.
        """
        Ds=[]
        for dpot in self.dpots:
            ds = dpot.invertchannels_rout(rout)
            Ds.append(ds)
        return Ds  

    def set_dpot_D(self, D):
        """Configure all DPOTs based on the provided digital code D. 

        Parameters
        ----------
        D : float or list[float]
            The digital code or a list of digital codes to which DPOT channels on the Board should be configured.
        """
        # Configure dpots based on the provided digital code D. 
        # Calibration must have been done prior to calling this function.
        self.pots=[]  # list of actual resistances
        for i in range(len(self.dpots)):
            if type(D) == int: self.dpots[i].setchannels_D([D, D, D, D]) # put the same D on all dpots
            elif type(D) == list and len(D[i]) == 4: self.dpots[i].setchannels_D(D[i])
            else: raise ValueError()
            rs = self.dpots[i].calcrout()
            for r in rs: 
                self.pots.append(-1*r) # when positive voltage is applied (vappled-vref), the output of the amplifier to the ADC falls. That means, the votlage change is negative! However, in the vector matrix multiply, we expect the current output to be positive and the mathematical operation to be positive. For this reason, we add the negative sign.
                if (len(self.pots) == max(self.xdim, self.ydim)): break

    @staticmethod
    def log_interp1d(xx, yy, kind='linear'):
        import scipy as sp
        import scipy.interpolate
        logx = np.log10(xx)
        logy = np.log10(yy)
        lin_interp = sp.interpolate.interp1d(logx, logy, kind=kind, bounds_error=False)
        log_interp = lambda zz: np.power(10.0, lin_interp(np.log10(zz)))
        return log_interp

    @staticmethod
    def isat_to_vgate(isat):
        cmos_data = np.loadtxt('misc/CMOS_IV.csv', delimiter=',')
        v, i = cmos_data[:, 0], cmos_data[:, 1]
        vgate = Daffodil_Base.log_interp1d(i, v)
        return vgate(isat)

    @staticmethod
    def vgate_to_isat(vgate):
        cmos_data = np.loadtxt('misc/CMOS_IV.csv', delimiter=',')
        v, i = cmos_data[:, 0], cmos_data[:, 1]
        isat = Daffodil_Base.log_interp1d(v, i)
        return isat(vgate)

    def config_muxes(self):
        """
            Initialize configuration modes for gates, columns, and rows

            Configuration modes can be determined in this way:
            Refer schematic and part spec: ADG804YRMZ-REEL7

            **For Rows and Columns**

            Access DAC
                * write_mode=0
                * ext_mode=0
            Access ADC
                * write_mode=1
                * ext_mode=0
            Access GND
                * write_mode=0
                * ext_mode=1
            External SRC
                * write_mode=1
                * ext_mode=1

            **For Gates**

            Access ADC
                * write_mode=0
                * ext_mode=0
            Access AVDD (3.3V)
                * write_mode=1
                * ext_mode=0
            Access GND
                * write_mode=0
                * ext_mode=1
            Access External SRC
                * write_mode=1
                * ext_mode=1

            EN_IO switches are used to activate entire access systems. With a single assertion,  you can activate simultanouesly either rows, columns, or gates. In the event mode, this can be useful. For example, you can configure rows/columns and then assert all gates. You can also configure all gates and then assert rows/columns simultaneously
        """
        self.write_mode_G=0
        self.ext_mode_G=0
        self.EN_IO_G=1
        
        self.write_mode_C=0
        self.ext_mode_C=0
        self.EN_IO_C=1

        self.write_mode_R=0
        self.ext_mode_R=0
        self.EN_IO_R=1
        
        self.EXT_ROW=0
        self.EXT_GATE=0
        self.EXT_COL=0
      
    def setcoldacs(self, colvoltages):
        """This function accepts a list of voltages and programs all column DACS (all 25 channels). It will accept a smaller list.

        Parameters
        ----------
        colvoltages : list[float]
            A list of voltages to be applied on column DACs.

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a device, or if voltages lower than 1.7 V are applied on a column.
        """
        for i in range(len(colvoltages)):
            voltage_applied = self.dac_calcvout(colvoltages[i])
            voltage_drop =  voltage_applied - self.curr_vref
            # do not apply voltages across the device exceeding 3.3 V
            # do not apply anything lower than 1.7V (a 0 voltage_applied means the column/row/gate isn't active) 
            if (self.curr_mode == 'forward'):
                if (abs(voltage_drop) > (self.vmax - self.vground)):
                    raise ValueError('Applied voltage across the chip cannot be greater than 3.3V.')
                # This is potentially incorrect - rows can also be grounded as long as they're disabled (?)
                if (voltage_applied != 0 and (voltage_applied < self.vground or voltage_applied > self.vmax)): 
                    raise ValueError('Column Bias cannot be lower than 1.7V.')
            if i < 16: #this programs all 16 channels on DAC2
                self.dacs[2].all_channels[i].update_x1(colvoltages[i])
                self.dacs[2].all_channels[i].update_vout()
                self.load_dacs([1,1,0,1,1])
            elif i >= 16: #this programs 9 channels on DAC3
                if(i-16 < 10):
                     self.dacs[3].all_channels[i-16].update_x1(colvoltages[i])
                     self.dacs[3].all_channels[i-16].update_vout()
                     self.load_dacs([1,0,1,1,1])

    def setcoldac_channel(self, colvoltage, i):
        """This function accepts a voltage and programs a single column DAC channel. It will accept a smaller list.

        Parameters
        ----------
        colvoltage : list[float]
            The voltages to be applied on column DACs.
        i : int
            Channel number from the range [0-24] corresponding to available column DACs. 

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a device, or if voltages lower than 1.7 V are applied on a column.
        """
        #This function accepts a lists and programs all the column ADCS. It will accept a smaller list
        
        voltage_applied = self.dac_calcvout(colvoltage)
        voltage_drop =  voltage_applied - self.curr_vref
        # do not apply voltages across the device exceeding 3.3 V
        # do not apply anything lower than 1.7V (a 0 voltage_applied means the column/row/gate isn't active) 
        if (self.curr_mode == 'forward'):
            if (abs(voltage_drop) > (self.vmax - self.vground)):
                raise ValueError('Applied voltage across the chip cannot be greater than 3.3V.')
            # This is potentially incorrect - rows can also be grounded as long as they're disabled (?)
            if (voltage_applied != 0 and (voltage_applied < self.vground or voltage_applied > self.vmax)): 
                raise ValueError('Column Bias cannot be lower than 1.7V.')
        if i < 16: #this programs all 16 channels on DAC2
            self.dacs[2].all_channels[i].update_x1(colvoltage)
            self.dacs[2].all_channels[i].update_vout()
            self.load_dacs([1,1,0,1,1])
        elif i >= 16: #this programs 9 channels on DAC3
            if(i-16 < 10):
                 self.dacs[3].all_channels[i-16].update_x1(colvoltage)
                 self.dacs[3].all_channels[i-16].update_vout()
                 self.load_dacs([1,0,1,1,1])
        
    def setrowdacs(self, rowvoltages):
        """This function accepts a list of voltages and programs all row DACS (all 25 channels). It will accept a smaller list.

        Parameters
        ----------
        rowvoltages : list[float]
            A list of voltages to be applied on row DACs.

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a device, or if voltages lower than 1.7 V are applied on a row.
        """
        for i in range(len(rowvoltages)):
            voltage_applied = self.dac_calcvout(rowvoltages[i])
            voltage_drop =  voltage_applied - self.curr_vref
            # do not apply voltages across the device exceeding 3.3 V
            # do not apply anything lower than 1.7V (a 0 voltage_applied means the column/row/gate isn't active) 
            if (self.curr_mode == 'backward'):
                if (abs(voltage_drop) > (self.vmax - self.vground)): 
                    raise ValueError('Applied voltage across the chip cannot be greater than 3.3V.')
                # This is potentially incorrect - rows can also be grounded as long as they're disabled (?)
                if (voltage_applied != 0 and (voltage_applied < self.vground or voltage_applied > self.vmax)): 
                    raise ValueError('Row Bias cannot be lower than 1.7V.')
            if i < 16: #This programs all 16 channels on DAC0
                self.dacs[0].all_channels[i].update_x1(rowvoltages[i])
                self.dacs[0].all_channels[i].update_vout()
                self.load_dacs([1,1,1,1,0])
            elif i >= 16: #This programs 9 more channels on DAC1
                if(i-16 < 10):
                    self.dacs[1].all_channels[i-16].update_x1(rowvoltages[i])
                    self.dacs[1].all_channels[i-16].update_vout()
                    self.load_dacs([1,1,1,0,1])

    def setrowdac_channel(self, rowvoltage, i):
        """This function accepts a voltage and programs a single row DAC channel. It will accept a smaller list.

        Parameters
        ----------
        rowvoltage : list[float]
            The voltage to be applied on the row DAC channel i.
        i : int
            Channel number from the range [0-24] corresponding to available row DACs. 

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a device, or if voltages lower than 1.7 V are applied on a row.
        """
        voltage_applied = self.dac_calcvout(rowvoltage)
        voltage_drop =  voltage_applied - self.curr_vref
        if (self.curr_mode == 'backward'):
            if (abs(voltage_drop) > (self.vmax - self.vground)): 
                raise ValueError('Applied voltage across the chip cannot be greater than 3.3V.')
            # This is potentially incorrect - rows can also be grounded as long as they're disabled (?)
            if (voltage_applied != 0 and (voltage_applied < self.vground or voltage_applied > self.vmax)): 
                raise ValueError('Row Bias cannot be lower than 1.7V.')
        if i < 16: #this programs all 16 channels on DAC2
            self.dacs[0].all_channels[i].update_x1(rowvoltage)
            self.dacs[0].all_channels[i].update_vout()
            self.load_dacs([1,1,1,1,0])
        elif i >= 16: #this programs 9 channels on DAC3
            if(i-16 < 10):
                self.dacs[1].all_channels[i-16].update_x1(rowvoltage)
                self.dacs[1].all_channels[i-16].update_vout()
                self.load_dacs([1,1,1,0,1])
    
    def setgatedacs(self, gatevoltages):
        """This function accepts a list of voltages and programs all gate DACS (all 25 channels). It will accept a smaller list. The actual voltage applied to the gate is with reference to ground, which is always 1.7V. This means that a gate voltage of 1.7V means 0V across the gate, and 5V means 3.3V across the gate.
        
        Parameters
        ----------
        gatevoltages : list[float]
            A list of voltages to be applied on gate DACs.

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a gate, or if voltages lower than 1.7 V are applied on a gate.
        """
        for i in range(len(gatevoltages)):
            voltage_applied = self.dac_calcvout(gatevoltages[i])
            voltage_drop =  voltage_applied - self.curr_vref
            # do not apply voltages across the device exceeding 3.3 V
            # do not apply anything lower than 1.7V (a 0 voltage_applied means the column/row/gate isn't active) 
            if (abs(voltage_drop) > (self.vmax - self.vground)): 
                raise ValueError('Applied voltage across the gate cannot be greater than 3.3V.')
            if (voltage_applied != 0 and (voltage_applied < 1.68 or voltage_applied > 5)):
                raise ValueError('Gate Bias cannot be lower than 1.7V.')
            if i < 16: #this programs all 16 channels on DAC4 
                if(i == 13 and self.swfix_en):
                    self.dacs[4].all_channels[14].update_x1(gatevoltages[13])
                    self.dacs[4].all_channels[14].update_vout()
                    self.load_dacs([0,1,1,1,1])
                elif(i == 14 and self.swfix_en):
                    self.dacs[4].all_channels[13].update_x1(gatevoltages[14])
                    self.dacs[4].all_channels[13].update_vout()
                    self.load_dacs([0,1,1,1,1])
                else:
                    self.dacs[4].all_channels[i].update_x1(gatevoltages[i])
                    self.dacs[4].all_channels[i].update_vout()
                    self.load_dacs([0,1,1,1,1])
            elif 22> i >= 16: #we take 6 channels from DAC1
                self.dacs[1].all_channels[i-16+10].update_x1(gatevoltages[i])
                self.dacs[1].all_channels[i-16+10].update_vout()
                self.load_dacs([1,1,1,0,1])
            elif i >= 22: #The last 3 channels we take from DAC3 
                self.dacs[3].all_channels[i-22+9].update_x1(gatevoltages[i])
                self.dacs[3].all_channels[i-22+9].update_vout() 
                self.load_dacs([1,0,1,1,1])
                
    def setgatedac_channel(self, gatevoltage, i):
        """This function accepts a voltage and programs a single gate DAC channel. It will accept a smaller list. The actual voltage applied to the gate is with reference to ground, which is always 1.7V. This means that a gate voltage of 1.7V means 0V across the gate, and 5V means 3.3V across the gate.

        Parameters
        ----------
        gatevoltage : list[float]
            The voltages to be applied on gate DACs.
        i : int
            Channel number from the range [0-24] corresponding to available gate DACs. 

        Raises
        ------
        ValueError
            If voltages exceeding 3.3 V are applied across a gate, or if voltages lower than 1.7 V are applied on a gate.
        """
    
        voltage_applied = self.dac_calcvout(gatevoltage)
        voltage_drop =  voltage_applied - self.curr_vref
        # do not apply voltages across the device exceeding 3.3 V
        # do not apply anything lower than 1.7V (a 0 voltage_applied means the column/row/gate isn't active) 
        if (abs(voltage_drop) > (self.vmax - self.vground)): 
            raise ValueError('Applied voltage across the gate cannot be greater than 3.3V.')
        if (voltage_applied != 0 and (voltage_applied < 1.68 or voltage_applied > 5)):
            raise ValueError('Gate Bias cannot be lower than 1.7V.')
        if i < 16: #this programs all 16 channels on DAC4 
            if(i == 13 and self.swfix_en):
                self.dacs[4].all_channels[14].update_x1(gatevoltage)
                self.dacs[4].all_channels[14].update_vout()
                self.load_dacs([0,1,1,1,1])
            elif(i == 14 and self.swfix_en):
                self.dacs[4].all_channels[13].update_x1(gatevoltage)
                self.dacs[4].all_channels[13].update_vout()
                self.load_dacs([0,1,1,1,1])
            else:
                self.dacs[4].all_channels[i].update_x1(gatevoltage)
                self.dacs[4].all_channels[i].update_vout()
                self.load_dacs([0,1,1,1,1])
        elif 22> i >= 16: #we take 6 channels from DAC1
            self.dacs[1].all_channels[i-16+10].update_x1(gatevoltage)
            self.dacs[1].all_channels[i-16+10].update_vout()
            self.load_dacs([1,1,1,0,1])
        elif i >= 22: #The last 3 channels we take from DAC3 
            self.dacs[3].all_channels[i-22+9].update_x1(gatevoltage)
            self.dacs[3].all_channels[i-22+9].update_vout()
            self.load_dacs([1,0,1,1,1])            
        
    def set_kernel(self, kernel): # This selects the kernel
        """Select the physical kernel on the chip. This is an abstract method that must be re-defined by inheriting classes.

        Parameters
        ----------
        kernel : int
            The kernel number from the range [0-31] corresponding to available physical kernels. 
        """
        raise Exception("This is an abstract method and must be implemented")

    def setrefopamp(self, refbias):
        """Set the reference bias for the ADCs to provided `refbias.`

        Parameters
        ----------
        refbias : float
            The reference voltage for the ADCs.
        """
        #transimpedance amplifiers operate with a virtual ground. This sets that value.
        #for example, we can pass 0.1 volts and measure current by applying the DACs to the columns at 0.1V and reading the current on the rows
        #we can also set the DACs to zero on the column and apply 0.1 volts to the reference bias. That will apply "negative" 0.1V to the device
        #current will flow the opposite direction. However, this also means that 0.1V is the zero current bias condition. This must be corrected post ADC in algorithm
        v = self.dac_calcvout(refbias)
        if (abs(v) < 1.687 or abs(v) > 2.5): raise ValueError('vref is best set within [1.7, 2.5] V. Verify that applied voltages are safe before suppressing this error.')
        self.curr_vref = v # saving for calculating applied voltages for later
        self.dacs[1].all_channels[9].update_x1(refbias)
        self.dacs[1].all_channels[9].update_vout()
        self.load_dacs([1,1,1,0,1])

    def event(self):
        """Assert an event. This is an abstract method that must be re-defined by inheriting classes.

        The event is the most important operation in the Daffodil board.

        Based on the configured mode, the event will update and read a specified kernel. Primarily, the inputs are voltages and, if the ADCs are connected, the outputs are currents.

        However, the read event does not produce the outputs. It simply tells the different parts to update their registers.

        Depending on the configuration, you will read from either the rows or columns or neither. 

        Explicitly included in the event operation is that the COL_EN_tobe and the ROW_EN_tobe variables are passed to the device model/physical chip.

        When an event is written on the board, for some period of clock cycles, all of the relevant enable assertions will be specified.

        Read and write operations have different clock cycle dependencies. For example, the read operation takes many cycles whereas a write only requires a few cycles. 
        """
        raise Exception("This is an abstract method and must be implemented")

    def retreivecolvoltages(self):
        """Retrieve the voltages written to the column DACs. These are 12 bit integers.

        Returns
        -------
        colvoltagelist : list[floats]
            A list of voltages corresponding to the available column DAC channels.
        """
        colvoltagelist=[]
        for i in range(self.xdim):
            if i < 16:
                 colvoltagelist.append(self.dacs[2].all_channels[i].x2)
            elif i >= 16:
                colvoltagelist.append(self.dacs[3].all_channels[i-16].x2)
        return colvoltagelist

    def retrieverowvoltages(self):
        """Retrieve the voltages written to the row DACs. These are 12 bit integers.

        Returns
        -------
        rowvoltagelist : list[floats]
            A list of voltages corresponding to the available row DAC channels.
        """
        rowvoltagelist=[]
        for i in range(self.ydim):
            if i < 16:
                rowvoltagelist.append(self.dacs[0].all_channels[i].x2)
            elif i >= 16:
                rowvoltagelist.append(self.dacs[1].all_channels[i-16].x2)
        return rowvoltagelist

    def retrievegatevoltages(self):
        """Retrieve the voltages written to the gate DACs. These are 12 bit integers.

        Returns
        -------
        gatevoltagelist : list[floats]
            A list of voltages corresponding to the available gate DAC channels.
        """
        gatevoltagelist=[]
        for i in range(self.xdim):
            if i < 16:
                gatevoltagelist.append(self.dacs[4].all_channels[i].x2)
            elif 22> i >= 16:
                gatevoltagelist.append(self.dacs[1].all_channels[i-16+10].x2)
            elif i >= 22:
                gatevoltagelist.append(self.dacs[3].all_channels[i-22+9].x2)
        return gatevoltagelist

    def retrievecurrents(self):
        """Retrieve output currents from all ADCs. These are 12 bit values. Their precise meaning in terms of current depends on the values of the potentiometers. 

        Returns
        -------
        currents : list[int]
            A list of currents on the crossbar outputs as 12-bit integers.
        """
        #this function 
        currents=[]
        for i in range(self.xdim):
            currents.append(self.adcs[i//4].registers[i%4])
        return currents
        
    def retrievecurrent_channel(self, channel_no):
        """Retrieve output currents from a specified ADC channel. This is a 12 bit value. The precise meaning in terms of current depends on the corresponding value of the potentiometers. 

        Parameters
        ----------
        channel_no : int
            Channel number from the range [0-24] corresponding to available ADCs. 

        Returns
        -------
        currents : floats
            Current on the crossbar output corresponding to specified channel as a 12-bit integer.
        """
        #this function reads out the 12 bit values from a specific ADC. Their precise meaning in terms of current depends on the values of the potentiometers. 
        current = self.adcs[channel_no//4].registers[channel_no%4]
        return current    

    def set_dac_gain_mode(self, mode):
        """Set the DAC gain mode.

        Parameters
        ----------
        mode : int
            DAC gain mode from the range [0-4094] for the default DAC part. 
        """
        for dac in self.dacs:
           dac.setchannels_m([mode]*16)

    def set_dac_offset(self, offset):
        """Set the DAC offset.

        Parameters
        ----------
        offset : int
            DAC offset from the range [0-2046] for the default DAC part. 
        """
        self.dac_offset=offset
        for dac in self.dacs:
            dac.setchannels_c([offset]*16)

    def dac_calcvout(self,x1):
        """Convert a provided 12-bit register value for a DAC to an output voltage.

        Parameters
        ----------
        x1 : int
            12-bit register value for a DAC. 

        Returns
        -------
        vout : float
            Output voltage corresponding to `x1`.
        """
        return self.dacs[0].calcvout(x1,self.dac_gain_mode,self.dac_offset)

    def dac_invertvout(self,v):
        """Convert a voltage to a 12-bit register value for a DAC.

        Parameters
        ----------
        vout : float
            Voltage to be converted.
        Returns
        -------
        x1 : int
            12-bit register value corresponding to `v`. 
        """
        return self.dacs[0].invertvout(v,self.dac_gain_mode,self.dac_offset)

    def adc_predict_voltage(self, registervalue):
        """Convert a readout ADC 12-bit register value to a voltage, which can then be converted to current using potentiometer values and knowledge of the reference bias.

        Parameters
        ----------
        registervalue : int
            12-bit register value measured from an ADC.
        Returns
        -------
        v : float
            Voltage corresponding to `registervalue`. 
        """
        #this asks what the voltage is from a partiuclar readout adc value.
        return self.adcs[0].predict_voltage(registervalue,self.adc_gain_mode)

    def adc_invert_voltage(self, voltage):
        """Convert a voltage to a 12-bit register value for the ADC.

        Parameters
        -------
        voltage : float
            Voltage to be converted.
        Returns
        ----------
        registervalue : int
            12-bit register value corresponding to `voltage`.
        """
        return self.adcs[0].invert_voltage(voltage,self.adc_gain_mode)

    def config_forward_pass(self):
        """Configure the board to be in forward configuration. The DACs are on the columns and the ADCs are on the rows.
        """
        #this configures a foward pass. The DACs are on the columns and the ADCs are on the rows.
        self.write_mode_C=0
        self.ext_mode_C=0

        self.write_mode_G=0
        self.ext_mode_G=0

        self.write_mode_R=1
        self.ext_mode_R=0

        self.curr_mode = 'forward'

    def config_backward_pass(self):
        """Configure the board to be in backward configuration. The DACs are on the rows and the ADCs are on the columns.
        """
        self.write_mode_C=1
        self.ext_mode_C=0

        self.write_mode_G=0
        self.ext_mode_G=0

        self.write_mode_R=0
        self.ext_mode_R=0

        self.curr_mode = 'backward'

    def config_outerproduct(self):
        """Configure the board to be in outerproduct configuration. The DACs are on the rows and columns and the ADCs are disconnected since no currents are measured.
        """
        self.write_mode_C=0
        self.ext_mode_C=0

        self.write_mode_G=0
        self.ext_mode_G=0

        self.write_mode_R=0
        self.ext_mode_R=0

        self.curr_mode = 'outerproduct'    

class Daffodil_Sim(Daffodil_Base):
    """
    Simulation class for Daffodil board. Inherits from `Daffodil_Base`.
    """
    def __init__(self, name):
        """Initialize a Board object with simulated devices of type `name`.

        Parameters
        ----------
        name : 'Generic'
            A generic device model. See Board.Device.Generic for further details on default implementation.
        """
        super().__init__(ADC_sim, DAC_sim, DPOT_sim)

        if name == 'Generic':
            self.sim_device = Generic(self.kernels, self.xdim, self.ydim)
        else:
            raise ValueError(f"{name} not implemented.")

    def load_dacs(self, value):
        # nothing to do if simulation model
        return

    def event(self):
        """
        Assert an `event` for the simulated Board. `event` physics are not perfectly resolved here. For example, there is no sense of timing. Certain realistic features are missing such as the
        scanning of the ADC to produce it's register values. This is a weakness of the model.
        """
        if self.write_mode_C == 0 and self.ext_mode_C == 0:
            #this is the forward pass configuraiton
            for i in range(self.xdim):
                if i < 16:
                    self.sim_device.columnvoltages[i]=self.dacs[2].all_channels[i].vout
                elif i >= 16:
                    self.sim_device.columnvoltages[i]=self.dacs[3].all_channels[i-16].vout
        elif self.write_mode_C == 1 and self.ext_mode_C ==0:
            #this is the backward pass configuration. The specified channel is the transimpedance amplifier reference voltage. 
            for i in range(self.xdim):
                self.sim_device.columnvoltages[i]=self.dacs[1].all_channels[9].vout

        if self.write_mode_R == 0 and self.ext_mode_R == 0:
            #this is the backward pass configuration
            for i in range(self.ydim):
                if i < 16:
                    self.sim_device.rowvoltages[i]=self.dacs[0].all_channels[i].vout
                elif i >= 16:
                    self.sim_device.rowvoltages[i]=self.dacs[1].all_channels[i-16].vout
        elif self.write_mode_R == 1 and self.ext_mode_R ==0:
            #this is the foward pass configuration. The specified channel is the transimpedance amplifier reference voltage
            for i in range(self.ydim):
                self.sim_device.rowvoltages[i]=self.dacs[1].all_channels[9].vout

        if self.write_mode_G == 0 and self.ext_mode_G == 0:
            #there is no forward or backward pass really for the gate. This allows the gates to be tunable
            for i in range(self.xdim):
                if i < 16:
                    self.sim_device.gatevoltages[i]=self.dacs[4].all_channels[i].vout*self.COL_EN_tobe[i]
                elif 22> i >= 16:
                    self.sim_device.gatevoltages[i]=self.dacs[1].all_channels[i-16+10].vout*self.COL_EN_tobe[i]
                elif i >= 22:
                    self.sim_device.gatevoltages[i]=self.dacs[3].all_channels[i-22+9].vout*self.COL_EN_tobe[i]
        elif self.write_mode_G == 1 and self.ext_mode_G == 0:
            #this sets all the gates to the max bias. Useful for inference.
            for i in range(self.xdim):
                self.sim_device.gatevoltages[i]=self.vmax
        elif self.write_mode_G == 0 and self.ext_mode_G == 1:
            #this sets all the gates to ground. Possibly useful for an event(). 
            for i in range(self.xdim):
                self.sim_device.gatevoltages[i] = 0

        for volt in self.sim_device.columnvoltages:
            #this checks for unrealistic voltages
            if volt > self.vmax:
                raise ValueError("Voltage too high: " + str(volt) + "Volts > " + str(self.vmax))
            #this checks for unrealistic voltages
        for volt in self.sim_device.rowvoltages:
            if volt > self.vmax:
                raise ValueError("Voltage too high: " + str(volt) + "Volts > " + str(self.vmax))
            #this checks for unrealistic voltages 
        for volt in self.sim_device.gatevoltages:
            if volt > self.vmax:
                raise ValueError("Voltage too high: " + str(volt) + "Volts > " + str(self.vmax))

        #this asserts a ReRAM/MTJ (whatever simulation device is selected) event. The devices and the currents are updated.
        self.sim_device.event(self.COL_EN_tobe,self.ROW_EN_tobe)

        if self.write_mode_C == 0 and self.ext_mode_C == 0:
            #if you are in the forward pass or the outer product update, this checks if the current exceeded the DAC limits
            for curr in self.sim_device.columncurrents:
                if abs(curr) > self.dac_curr_limit:
                    raise ValueError("Column Current too high: " + str(curr) + "Volts > " + str(self.dac_curr_limit))
            
        if self.write_mode_R == 0 and self.ext_mode_R == 0:
            #if you are in the backward pass or the outer product update, this checks if the current exceeded the DAC limits
            for curr in self.sim_device.rowcurrents:
                if abs(curr) > self.dac_curr_limit:
                    raise ValueError("Row Current too high: " + str(curr) + "Volts > " + str(self.dac_curr_limit))

        if self.write_mode_C == 1 and self.ext_mode_C == 0:
            #this converts the currents (in uA) to voltages values and updates the ADC registers. It assumes an ideal zero input impedance transimpedance.
            for i in range(self.xdim):
                transimpedance_output = self.sim_device.columnvoltages[i] - self.sim_device.columncurrents[i]*self.pots[i]/self.sim_device.currentscale
                if transimpedance_output > (self.vmax - self.vground): #The voltage cannot exceed the board limit. You can also clip this at 3.3
                    raise ValueError("input current to transimpedance amplifier at limit")
                if transimpedance_output < 0.0: #The voltage cannot go below the board limit. You can also clip this at 0
                    raise ValueError("the minimal voltage limit on the amplifier is reached " + str(transimpedance_output) + " is out of range")
                self.adcs[i//4].update_register(i%4,transimpedance_output)

        if self.write_mode_R == 1 and self.ext_mode_R == 0:
            #this converts the currents (in uA) to voltages values and updates the ADC registers. It assumes an ideal zero input impedance transimpedance.
            for i in range(self.ydim):
                transimpedance_output = self.sim_device.rowvoltages[i] + self.sim_device.rowcurrents[i]*self.pots[i]/self.sim_device.currentscale
                if transimpedance_output > (self.vmax - self.vground): #The voltage cannot exceed the board limit. You can also clip this at 3.3
                    transimpedance_output = (self.vmax - self.vground)
                    # raise ValueError("input current to transimpedance amplifier at limit")
                if transimpedance_output < 0.0: #The voltage cannot go below the board limit. You can also clip this at 0
                    transimpedance_output = 0.0
                    # raise ValueError("the minimal voltage limit on the amplifier is reached " + str(transimpedance_output) + " is out of range")
                self.adcs[i//4].update_register(i%4,transimpedance_output)

    def event_timevariant(self, pulse_len):
        self.event()

    def set_kernel(self, kernel, swfix_en=False): # This selects the kernel

        # To select the kernel on the chip, we have to specify some bit string which maps to TTL assertions on the the FPGA board.
        # That string is: CA0_MSB_LSB_CA1_RA1_RA0 where CA0 is always zero, MSB/LSB are the internal chip muxes, CA1 is the column mux access
        # and RA1 and RA0 are row access commands.
        # CA0 is always zero because we only use inputs 0 and 2 and never 1 and 3. This is because we have 50 columns and 100 rows.
        # When not selected, the columns are high impedance because floating gates are automatically grounded by the chip. The rows are floating. 

        binnum = format(kernel, '#010b') #this creates a bit string

        #these functinos map the number 0-31 into the FPGA assertions
        self.RA0=int(binnum[-1])
        self.RA1=int(binnum[-2])
        self.CA1=int(binnum[-3])
        self.LSB=int(binnum[-4])
        self.MSB=int(binnum[-5])

        #this tells the ReRAM what kernel is selected 
        self.sim_device.selectkernel(kernel)

        # nothing to do with swfix_en, it's simulation

    def set_compliance_control(self, bit): # This asserts/deasserts the compliance_control_lo signal
        # We have 3 digital signals for the chip - MSB, LSB, and compliance control
        # LSB & MSB are for the selection of the subarrays, used within set_kernel(), whereas compliance control is for a full-power mode.
        # When this compliance control is ON (set to 3.3V), the PMOS is OFF and all current is flowing through the NMOS channel
        # The chip gets put in digital mode essentially, where the only options for the gate is ON (3.3V) or OFF
        # There is circuitry on the chip that corrects to 3.3V at the input of the gates

        # When compliance = 0 (not full power), vgate dictates the saturation current. The compliance IV file has that mapping between the two, and the helper function (TBA) can be used to choose an appropriate vgate directly.
        # When compliance = 1 (full power), vgate does not dictate the saturation current. We always go for vgate 3.3V across i.e. 5V on the DACs in order to have the gates ON. The saturation current, in this case, is dictated directly by the DPOT resistance.

        if bit not in [0, 1]: raise ValueError("Setting compliance control incorrectly")
        self.compliance_control = bit

class Daffodil_Phys(Daffodil_Base):
    """
    Physical class for Daffodil board. Inherits from `Daffodil_Base`. Handles all physical interactions with the mixed-signal daughterboard.
    """
    def __init__(self):

        """Initialize the physical Board object. Similar to `Daffodil_Base.__init__` with additional binding to the physical memory space for communication with the mixed-signal daughterboard.
        """

        self.name_map = {}
        try:
            self.PGPIO = ctypes.CDLL(ctypes.util.find_library("pgpio")) #this will find and load libpgpio.so
        except:
            raise Exception("Failed to load C bindings for PGPIO")

        ret = self.PGPIO.open_mem()
        if ret != 0:
            raise Exception(os.strerror(ret))
        self.PGPIO.init()

        super().__init__(ADC_phys, DAC_phys, DPOT_phys)

        self.name_map = {
            "RA0": self.get_int("ra_base"),
            "RA1": self.get_int("ra_base") + 1,
            "CA1": self.get_int("ca_base") + 1,
            "compliance_control": self.get_int("compliance_control_lo_pin"),
            "LSB": self.get_int("array_control_lsb_lo_pin"),
            "MSB": self.get_int("array_control_msb_lo_pin"),
            "write_mode_R": self.get_int("write_mode_R_pin"),
            "ext_mode_R": self.get_int("ext_mode_R_pin"),
            "EN_IO_R": self.get_int("EN_IO_R_pin"),
            "write_mode_C": self.get_int("write_mode_C_pin"),
            "ext_mode_C": self.get_int("ext_mode_C_pin"),
            "EN_IO_C": self.get_int("EN_IO_C_pin"),
            "write_mode_G": self.get_int("write_mode_G_pin"),
            "ext_mode_G": self.get_int("ext_mode_G_pin"),
            "EN_IO_G": self.get_int("EN_IO_G_pin"),
        }

        self.config_muxes()

        for dac in self.dacs:
            dac.PGPIO = self.PGPIO
            for c in dac.all_channels:
                c.PGPIO = self.PGPIO
                c.init_static_files()
        for adc in self.adcs:
            adc.PGPIO = self.PGPIO
            adc.init_static_files()

    def __setattr__(self, name, value):
        if name == "name_map":
            object.__setattr__(self, name, value)
        if name in self.name_map.keys():
            self.PGPIO.write_bit(self.get_int("gpio_data_offset"), self.name_map[name], value)
            return
        object.__setattr__(self, name, value)

    def __getattribute__(self, name):
        if name == "name_map":
            return object.__getattribute__(self, name)
        if name in object.__getattribute__(self, "name_map").keys():
            return object.__getattribute__(self, "PGPIO").read_bit(object.__getattribute__(self, "get_int")("gpio_data_offset"), object.__getattribute__(self, "name_map")[name])
        return object.__getattribute__(self, name) #not sure this is nescessary

    def get_int(self, name):
        return ctypes.c_int.in_dll(self.PGPIO, name).value

    def load_dacs(self, value):
        self.PGPIO.write_bit(0x1000, 15, value[4])
        self.PGPIO.write_bit(0x1000, 16, value[3])
        self.PGPIO.write_bit(0x1000, 17, value[2])
        self.PGPIO.write_bit(0x1000, 18, value[1])
        self.PGPIO.write_bit(0x1000, 19, value[0])
        self.PGPIO.write_bit(0x1000, 15, 1)
        self.PGPIO.write_bit(0x1000, 16, 1)
        self.PGPIO.write_bit(0x1000, 17, 1)
        self.PGPIO.write_bit(0x1000, 18, 1)
        self.PGPIO.write_bit(0x1000, 19, 1)

    def set_kernel(self, kernel, swfix_en = False): # This selects the kernel
        # Behavior similar to description in Daffodil_Sim.set_kernel
        binnum = format(kernel, '#010b') #this creates a bit string
        #these functinos map the number 0-31 into the FPGA assertions
        self.RA0=int(binnum[-1])
        self.RA1=int(binnum[-2])
        self.CA1=int(binnum[-3])
        self.LSB=int(binnum[-4])
        self.MSB=int(binnum[-5])
        self.swfix_en = swfix_en

    def set_compliance_control(self, bit): # This asserts/deasserts the compliance_control_lo signal
        # Behavior similar to description in Daffodil_Sim.set_compliance_control
        if bit not in [0, 1]: raise ValueError("Setting compliance control incorrectly")
        self.compliance_control = bit

    def event(self):
        """
        Assert an `event` for the physical Board with preset pulse lengths for reading and writing.
        """
        data_offset = self.get_int("gpio_data_offset")
        col_cnt = self.get_int("col_en_cnt")
        col_base = self.get_int("col_en_base")
        row_cnt = self.get_int("row_en_cnt")
        row_base = self.get_int("row_en_base")

        # permanently disabled columns/rows - primarily for debugging
        rows_disabled = []
        cols_disabled = []
        for i in cols_disabled:
            self.COL_EN_tobe[i] = 0
        for i in rows_disabled:
            self.ROW_EN_tobe[i] = 0

        for i in range(col_cnt):
            self.PGPIO.write_bit(data_offset, col_base + i, self.COL_EN_tobe[i])
        for i in range(row_cnt):
            self.PGPIO.write_bit(data_offset, row_base + i, self.ROW_EN_tobe[i])
        if self.write_mode_C == 1 or self.write_mode_R == 1:
            self.PGPIO.raw_write(self.get_int("pulse_length_addr"), self.read_pulse_len)
            self.PGPIO.raw_write(self.get_int("event_addr"), 1)
            for i in range(self.xdim):
                self.adcs[i//4].update_register(i%4)
            #event will end after all adcs have been read
        else:
            self.PGPIO.raw_write(self.get_int("pulse_length_addr"), self.write_pulse_len)
            self.PGPIO.raw_write(self.get_int("event_addr"), 1)
            #event is over quickly

        # There should be more methods added to the base class to deal with changing the pulse length
        # Different pulse lengths will also impact the simulation, so the base class should take care of them
 
    def event_timevariant(self, pulse_len, write = False):
        """
        Assert a read or write `event` for the physical Board with specified pulse length `pulse_len`.

        Parameters
        ----------
            pulse_len: int
                Length of the event during which enable signals on the physical board will be asserted in terms of clock cycles.
            write: bool
                If False, the event is followed by ADC register updates, indicating a read operation.
        """
        data_offset = self.get_int("gpio_data_offset")
        col_cnt = self.get_int("col_en_cnt")
        col_base = self.get_int("col_en_base")
        #row_cnt = self.ydim
        row_cnt = self.get_int("row_en_cnt")
        row_base = self.get_int("row_en_base")

        rows_disabled = []
        cols_disabled = []
        for i in cols_disabled:
            self.COL_EN_tobe[i] = 0
        for i in rows_disabled:
            self.ROW_EN_tobe[i] = 0

        for i in range(col_cnt):
            self.PGPIO.write_bit(data_offset, col_base + i, self.COL_EN_tobe[i])
        for i in range(row_cnt):
            self.PGPIO.write_bit(data_offset, row_base + i, self.ROW_EN_tobe[i])
        if self.write_mode_C == 1 or self.write_mode_R == 1:
            self.PGPIO.raw_write(self.get_int("pulse_length_addr"), pulse_len)
            self.PGPIO.raw_write(self.get_int("event_addr"), 1)
            if(write == False):
                t.sleep(0.06)
            for i in range(self.xdim):
                self.adcs[i//4].update_register(i%4)
            #event will end after all adcs have been read
        else:
            self.PGPIO.raw_write(self.get_int("pulse_length_addr"), pulse_len)
            self.PGPIO.raw_write(self.get_int("event_addr"), 1)
            #print("pulse len", self.write_pulse_len)
            #event is over quickly

        # There should be more methods added to the base class to deal with changing the pulse length
        # Different pulse lengths will also impact the simulation, so the base class should take care of them    
