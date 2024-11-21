"""
May 2023
Osama Yousuf
Digital Potentiometer class for the Daffodil Board
AD8403
Device documentation available: https://www.analog.com/media/en/technical-documentation/data-sheets/AD8400_8402_8403.pdf
"""

from daffodillib.utils import find_device_spi
import ctypes
import numpy as np

class AD8403_Base:
    def __init__(self, n, R_AB=100000):
        self.num_channels = 4
        self.num_positions = 256
        self.R_W = 50
        self.R_AB = R_AB
        self.n = n
        self.all_channels=[] #this is the most basic element, a channel. description below
        for i in range(self.num_channels):
            # m, b = self.calc_m_b(self.Dmin, self.rmin, self.Dmax, self.rmax)
            self.all_channels.append(self.Channel(i)) #this creates all 16 channels
            self.all_channels[-1].R_W = self.R_W
            self.all_channels[-1].R_AB = self.R_AB
            self.all_channels[-1].num_positions = self.num_positions

    def setchannels_D(self, values): # this sets a list of channel D values
        if len(values) > len(self.all_channels):
            raise ValueError()
        for i in range (len(values)):
            self.all_channels[i].update_D(values[i])

    def invertchannels_rout(self, rout):
        Ds = []
        for i in range(self.num_channels):
            D = self.all_channels[i].invertrout(rout)
            Ds.append(D)
        return Ds

    def calcrout(self): #this calculates rout and returns a list of resistances for all channels
        return [self.all_channels[i].predictcalcrout() for i in range(self.num_channels)]

    @staticmethod
    def calc_m_c(x1, y1, x2, y2):
        x_coords = [x1, x2]
        y_coords = [y1, y2]
        A = np.vstack([x_coords, np.ones(len(x_coords))]).T
        m, c = np.linalg.lstsq(A, y_coords, rcond=None)[0]
        return m, c


class Channel_Base:
    def __init__(self, i):
        self.i = i
        self.D = -1 # uninitialized at start

    def predictcalcrout(self): #this function lets you do the resistance calculation without actually updating rout. 
        if (self.D not in range(self.num_positions)):
            raise ValueError()
        return self.D / self.num_positions * self.R_AB + self.R_W

    def update_D(self, D):
        raise ValueError("This is a virtual method, must be defined by inheriting class")

class AD8403_Sim(AD8403_Base):
    """
    This class defines the mathematical characteristics of an AD8403 Digital Potentiometer.

    The 25 ADC channels are connected to Transimpedance Amplifiers, each of which is then connected to an independent Digipot channel.
    """

    class Channel(Channel_Base):
        def update_D(self, D):
            if (D not in range(self.num_positions)):
                raise ValueError()
            self.D = D

        def invertrout(self, rout): #this function lets you invert resistance r to the nearest digital code (D) of the digipot.
            D = round((rout - self.R_W) / (self.R_AB / self.num_positions))
            if (D > 255):
                D = 255
            if (D < 0):
                D = 0
            return D

class AD8403_Phys(AD8403_Base):
    def __init__(self, n):
        self.device_dir = find_device_spi(n)

        # TODO: This can be separated - no need to load file for every dpot
        self.phys_calib = np.loadtxt('misc/dpots/1304917.txt')
        
        assert self.phys_calib.shape[0] == 7 * 4 + 1
        assert self.phys_calib.shape[1] >= 2 

        super().__init__(n)
        chan_num = 4*n + 1 # + 1 to skip header row
        for chan in self.all_channels:
            chan.device_dir = self.device_dir
            x1 = self.phys_calib[0, 0]
            x2 = self.phys_calib[0, 2]
            y1 = self.phys_calib[chan_num, 0]
            y2 = self.phys_calib[chan_num, 2]
            chan.m, chan.c = self.calc_m_c(x1, y1, x2, y2)
            chan_num += 1

    class Channel(Channel_Base):
        def __init__(self, i):
            super().__init__(i)
            # The following need to be calibrated based on physical tuning and measurements
            self.m = None
            self.c = None
        
        def predictcalcrout(self): #this function lets you do the resistance calculation without actually updating rout. 
            if (self.m == None or self.c == None):
                print("Digipots need to be calibrated")
                raise ValueError()
            if (self.D not in range(self.num_positions)):
                raise ValueError()
            return self.m * self.D + self.c 

        def invertrout(self, rout): #this function lets you invert resistance r to the nearest digital code (D) of the digipot.
            if (self.m == None or self.c == None):
                print("Digipots need to be calibrated")
                raise ValueError()
            if (self.m == 0 and self.c == 0): # unused digipot channels
                return 0
            D = round((rout - self.c) / self.m)
            if (D > 255):
                D = 255
            if (D < 0):
                D = 0
            return D   
        
        def update_D(self, D): #This is NOT an atomic operation, use the pulsed GPIO interface to send precisely timed signals
            if (D not in range(256)):
                raise ValueError()
            self.D = D
            with open(self.device_dir + "/rdac{}".format(self.i), 'w') as f:
                f.write(str(self.D))

