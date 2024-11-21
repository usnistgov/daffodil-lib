"""
October 2020
Digital to Analog Converter class for the Daffodil Board
AD5391BSTZ-5
Device documentation available: https://www.analog.com/media/en/technical-documentation/data-sheets/AD5390_5391_5392.pdf
"""

from daffodillib.utils import find_device_iio as find_device
import ctypes

class AD5391BSTZ5_Base:
    def __init__(self, n):
        self.n = n
        self.all_channels=[] #this is the most basic element, a channel. description below
        for i in range(16):
            self.all_channels.append(self.Channel(i)) #this creates all 16 channels
            self.all_channels[-1].vmax = 3.3
            self.all_channels[-1].vmax = 5

    def setchannels_x1(self, values): # this sets a a list of channels x1 values
        if len(values) > 16:
            raise ValueError()
        for i in range (len(values)):
            self.all_channels[i].update_x1(values[i])

    def setchannels_m(self, values): #this sets a list of channels m values
        if len(values) > 16:
            raise ValueError()
        for i in range(len(values)):
            self.all_channels[i].update_m(values[i])

    def setchannels_c(self, values): #this sets a list of channel c values
        if len(values) > 16:
            raise ValueError()
        for i in range(len (values)):
            self.all_channels[i].update_c(values[i])

    def update_voltage(self): #this updates the voltage on the channels
        for obj in self.all_channels:
            obj.update_vout()

    def calcvout(self, x1, m, c): #this calculates vout for a particular m and c
        return self.all_channels[0].predictcalcvout(x1,m,c)

    def invertvout(self,v,m,c): #this calculates register value for a particular m and c from a voltage 
        return self.all_channels[0].invertvout(v,m,c)

    def get_bit_string(self, CS_line, channel, value):
        if value<0 or value>4095:
            raise Exception("Illegal value for x1")
        if channel<0 or channel>15:
            raise Exception("Nonexistent channel specified")
        if CS_line<0 or CS_line>255:
            raise Exception("CS line must be between 0 and 255")
        return CS_line << 24 | 0b0000 << 20 | channel << 16 | 0b11 << 14 | value


class Channel_Base:
    def __init__(self, i):
        self.i = i
        self.vref=2.5 #this is the reference bias. it is set by the board
        self.n=12 # this is the bit precision
        self.max_prec = 2**(self.n) # this is the max precision
        self.dac_offset = 2047
        self.curr_limit = 40000 # this is the channel current limit. 40mA

        self.x1=0 #this is the register value
        self.m=4094 #this is the default gain value
        self.c=0 #2048 #this is the default offset
        self.x2=((self.m+2)/2**self.n)*self.x1+(self.c) #this is the current x2 value

        self.set_x1 = 0 # The value that x1 will be set to when a hardware set pulse happens
        self.reset_x1 = 0 # The value for a hardware reset pulse
    def predictcalcvout(self, x1,m,c): #this function lets you do the voltage calculation without actually updating vout. 
        if x1 < 0 or x1 > self.max_prec:
            raise ValueError("x1 can only be from 0 to 4095, but was {}!".format(x1))
        x2 = ((m+2)/2**self.n)*x1+(c)
        return 2 * self.vref * x2/self.max_prec

    def invertvout(self, v,m,c): #this converts voltage to register value. you need this to write to the register to get your desired vout.
        #when writing RTL code, you may not need this function, but need to really understand the DAC configuration and device properties. 
        reg = round(2**(self.n-1)*((2**self.n)*(v)-2*c*self.vref)/(2+m)/self.vref)
        if (reg < 0): reg = 0
        elif (reg > 4095): reg = 4095
        return reg

    def update_m(self, value): #call this function to update m
        if value < 0 or value >= self.max_prec-2:
            raise ValueError("m can only be from 0 to 4093!")
        self.m = value

    def update_c(self, value): #call this funciton to update c
        if value < -(self.dac_offset+1) or value >= self.dac_offset:
            raise ValueError("c can only be from 0 to 2048!")
        self.c = value

    def update_x1(self, value): #call this function to write a new x1 value. used often during operation
        if value < 0 or value >= self.max_prec:
            raise ValueError("x1 can only be from 0 to 4095, but was {}!".format(value))
        self.x1 = value

    def update_set_x1(self, value):
        if value < 0 or value >= self.max_prec:
            raise ValueError("set_x1 can only be from 0 to 4096, but was {}!".format(value))
        self.set_x1 = value

    def update_reset_x1(self, value):
        if value < 0 or value >= self.max_prec:
            raise ValueError("reset_x1 can only be from 0 to 4096, but was {}!".format(value))
        self.reset_x1 = value



class AD5391BSTZ5_Sim(AD5391BSTZ5_Base):
    """
    This class defines the mathematical characteristics of a AD5391BSTZ-5 DAC. The important behaviors it approximates are:
            1) the mathematical relationship between the 12-bit input register values and the output voltage
            2) the limiting current and voltage values for when emulating the behavior of the device.
            3) the state relationship of the channels since each channel has it's own registers that specify different gain modes and offsets. 
    This class is designed to operate with a model ReRAM API.
    In addition to being able to specify these mathematical operations, it can also invert them. So, in high level code, you can also call the functions that map the ADC 12-bit values into real voltages.

    For neural network applications, this behavior is useful since it allows us to simulate the impact of bit quantization on network operation. 
    """
#    def __init__(self):
#            super().__init__()

    class Channel(Channel_Base):
        """
        The channel is the most important part of the DAC. Each DAC has 16 channels which use register values, 'm' (GAIN) and 'c' (OFFSET) to calculate what the output voltage is.

        The gain setting has actually very little impact on the performance. It could be used to set a hard limit on the DAC output, e.g., by specifying the max x1 value to map to 3.3V,
        but otherwise the output is controlled by the x2 transfer value, which is still 12 bit.

        Precision can be increased by using the 14bit model of the device as well as reducing the reference bias from 2.5V to 1 v. This would lead to 3 additional bits of precision, about 15 bits on low bias. 

        """
        def __init__(self, i):
            super().__init__(i)

            self.vout = 2 * self.vref * self.x2/2**self.n #this is the current output bias

            self.set_x2 = 0
            self.reset_x2 = 0

        def update_vout(self): # this updates the output bias
            self.x2=((self.m+2)/2**self.n)*self.x1+(self.c) #this is the internal register value for the output
            self.vout = 2 * self.vref * self.x2/self.max_prec #this produces a new vout

            self.set_x2=((self.m+2)/2**self.n)*self.set_x1+(self.c) #A ficticious register for use by hardware set commands
            self.reset_x2=((self.m+2)/2**self.n)*self.reset_x1+(self.c) #Same but for reset

        def hardware_set(self):
            self.vout = 2 * self.vref * self.set_x2/self.max_prec #this produces a new vout

        def hardware_reset(self):
            self.vout = 2 * self.vref * self.reset_x2/self.max_prec #this produces a new vout


class AD5391BSTZ5_Phys(AD5391BSTZ5_Base):
    def __init__(self, n):
        self.device_dir = find_device(n)
        super().__init__(n)
        for chan in self.all_channels:
            chan.device_dir = self.device_dir
    class Channel(Channel_Base):
        def __init__(self, i):
            super().__init__(i)
            self.accel_iio_c = 0
        def init_static_files(self):
            if self.accel_iio_c == 2:
                self.bias_file_num = self.PGPIO.open_write_file(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibbias".format(self.i), 'utf-8')))
                self.scale_file_num = self.PGPIO.open_write_file(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibscale".format(self.i), 'utf-8')))
                self.raw_file_num = self.PGPIO.open_write_file(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_raw".format(self.i), 'utf-8')))
        def update_vout(self): #This is NOT an atomic operation, use the pulsed GPIO interface to send precisely timed signals
            if self.predictcalcvout(self.x1, self.m, self.c) > self.vmax:
                raise Exception("Voltage should not be set that high")
                return

            if self.predictcalcvout(self.set_x1, self.m, self.c) > self.vmax:
                raise Exception("Hardware set voltage should not be set that high")
                return

            if self.predictcalcvout(self.reset_x1, self.m, self.c) > self.vmax:
                raise Exception("Hardware reset voltage should not be set that high")
                return

            if self.accel_iio_c == 0:
                with open(self.device_dir + "/out_voltage{}_calibbias".format(self.i), 'w') as f:
                    f.write(str(self.c))
                with open(self.device_dir + "/out_voltage{}_calibscale".format(self.i), 'w') as f:
                    f.write(str(self.m))
                with open(self.device_dir + "/out_voltage{}_raw".format(self.i), 'w') as f:
                    f.write(str(self.x1))
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #with open(self.device_dir + "/out_voltage{}_calibbias".format(self.i), 'w') as f:
                    #f.write(str(self.c))
                #with open(self.device_dir + "/out_voltage{}_calibscale".format(self.i), 'w') as f:
                    #f.write(str(self.m))
                #with open(self.device_dir + "/out_voltage{}_raw".format(self.i), 'w') as f:
                    #f.write(str(self.x1))
            elif self.accel_iio_c == 1:
                self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibbias".format(self.i), 'utf-8')), self.c)
                self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibscale".format(self.i), 'utf-8')), self.m)
                self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_raw".format(self.i), 'utf-8')), self.x1)
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibbias".format(self.i), 'utf-8')), self.c)
                #self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_calibscale".format(self.i), 'utf-8')), self.m)
                #self.PGPIO.write_int(ctypes.c_char_p(bytes(self.device_dir + "/out_voltage{}_raw".format(self.i), 'utf-8')), self.x1)
            elif self.accel_iio_c == 2:
                self.PGPIO.write_static_file(self.bias_file_num, self.c)
                self.PGPIO.write_static_file(self.scale_file_num, self.m)
                self.PGPIO.write_static_file(self.raw_file_num, self.x1)
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #self.PGPIO.write_bit(0x1000, 39, 1)
                #self.PGPIO.write_static_file(self.bias_file_num, self.c)
                #self.PGPIO.write_static_file(self.scale_file_num, self.m)
                #self.PGPIO.write_static_file(self.raw_file_num, self.x1)

            #PGPIO.raw_write(PGPIO.set_command_offset + self.global_id * 4, get_bit_string(self.CS_line, self.i, self.set_x1))
            #PGPIO.raw_write(PGPIO.reset_command_offset + self.global_id * 4, get_bit_string(self.CS_line, self.i, self.reset_x1))

        def hardware_set(self):
            pass #Nothing needs to happen here because the hardware does this

        def hardware_reset(self):
            pass
