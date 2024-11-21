"""
October 2020
Analog to Digital Converter class for the Daffodil Board
ADS7950SBDBT
Device documentation available: https://www.ti.com/lit/ds/symlink/ads7950.pdf?HQS=TI-null-null-mousermode-df-pf-null-wwe&ts=1602784582545&ref_url=https%253A%252F%252Fwww.mouser.com%252F
"""

from daffodillib.utils import find_device_iio as find_device
import ctypes

class ADS7950SBDBT_Base:
    def predict_voltage(self, registervalue, gain): #this takes an ADC value and tells you how much voltage you should have gotten
        return (1+gain)*self.vref*registervalue/4096

    def invert_voltage(self, value, gain): #this takes a voltage and tells you the nearest ADC value that maps to it.
        return round(4096*value/(gain+1)/self.vref)

    def setgain(self, gain):
        raise Exception("This is an abstract method and must be implemented by a subclass")

    def update_register(self, i, value = 0):
        raise Exception("This is an abstract method and must be implemented by a subclass")

    def update_registers(self, values = [0]):
        raise Exception("This is an abstract method and must be implemented by a subclass")

class ADS7950SBDBT_Sim(ADS7950SBDBT_Base):
    """
    This class contains a simplified description of the ADS7950SBDBT ADC. It assumes a 2.5 volt reference against which the 12 bit ADC values are defined.
    This system is used in the Daffodil board to readout voltages from the transimpedance amplifier.
    In reality, the system has a single ADC internally muxed to 4 channels. The model assumes, implicitly, 4 independent ADCs. This would need to be resolved in the event definition of the ADC.

    The most important quantity is the gain mode, which can take on values of 0 and 1. This specifies a factor of 2 in the read out values of the ADC. The higher gain has more range but lower precision.

    This class includes an accurate model for mapping voltage to integer values and the inverse processes.
    """
    def __init__(self, vref, n):
        self.n = n
        self.gain = 1 # the gain, can be 0 or 1.
        self.registers=[0,0,0,0] # initialize 4 registers. This is where the 12bit output values are stored

        if vref < 2 or vref > 3:
            raise ValueError("vref is outside of the datashet bounds! Can only have values from 2 to 3")
        else:
            self.vref=vref #the reference bias

    def setgain(self, value): #sets the gain checks for range
        if value not in range(1):
            raise ValueError()
        self.gain = value

    def update_registers(self, values): # this updates all registers by taking a list of values
        if len(values) not in range(1,5):
            raise ValueError()
        for i in range(len(values)):
            self.update_register(i, values[i])

    def update_register(self, i, value): #based on the input voltages, this sets values in a register to a 12 bit integer
        if i not in range(4):
            raise ValueError()
        self.registers[i]= round(4096*value/(self.gain+1)/self.vref)
        if self.registers[i] > 4096: # this checks a physical reality. It's mathematically impossible to read more than 4096 values
            raise ValueError("Register overflow, unphysical current of {} from value {}".format(self.registers[i], value))

class ADS7950SBDBT_Phys(ADS7950SBDBT_Base):
    def __init__(self, vref, n):
        self.gain = 1
        self.registers = [0, 0, 0, 0]

        self.device_dir = find_device(n)
        with open(self.device_dir + "/in_voltage_scale") as f:
            self.voltage_scale = float(f.read())
        if vref < 2 or vref > 3:
            raise ValueError("vref is outside of the datashet bounds! Can only have values from 2 to 3")
        else:
            self.vref=vref #the reference bias

        self.accel_iio_c = 0

    def init_static_files(self):
        if self.accel_iio_c == 2:
            self.static_file_nums = [self.PGPIO.open_read_file(ctypes.c_char_p(bytes(self.device_dir + "/in_voltage{}_raw".format(i), 'utf-8'))) for i in range(4)]

    def setgain(self, value):
        raise Exception("Not yet implemented")

    def update_registers(self): # this updates all registers by taking a list of values
        for i in range(4):
            self.update_register(i)

    def update_register(self, i):
        if i not in range(4):
            raise ValueError()
        fname = self.device_dir + "/in_voltage{}_raw".format(i)
        if self.accel_iio_c == 0:
            with open(fname) as f:
                self.registers[i] = int(f.read())
        elif self.accel_iio_c == 1:
            self.registers[i] = self.PGPIO.read_int(ctypes.c_char_p(bytes(fname, 'utf-8')))
        elif self.accel_iio_c == 2:
            self.registers[i] = self.PGPIO.read_static_file(self.static_file_nums[i])
