form_inc = 40
sweep_inc = 6
#set_step_inc = 
#reset_step_inc =
write_pulse_len = 2 * 200 * 25 * 4*10*10*2 #375ms
read_pulse_len = 6 * 200 * 25 * 4*10*10*2 #375ms
max_iterations = 3
target_current = 69#120#uA
on_margin = 6#20#uA
off_margin = 5#20#uA

max_target_current = 70

form_max_cur = 350
sweep_max_cur = 260

#Voltage parameters
vground = 1.7#V
vref = 1.7#V
vstart = vref
vread = vstart + 0.3#V
vgate = vstart + 3.1#3.3v not possible as max out from DAC is only 4.9v

set_vcol = vstart 
set_vrow = vstart + 2.0 #V
set_vgate = vgate 
reset_vcol = vstart + 2.0 #V
reset_vrow = vstart 
reset_vgate = vstart + 3.3
switching_voltage = 0.85

#max current
set_max_current = 250#uA
form_max_current = 500#uA


#dac/adc parameters
dpot_r = 1.5*10**3
dac_gain = 4093

#misc
on = True #True - Turns the device on, False - Turns the device off
debug = True #not used
use_margin = True
configure = True
alg_option = 1 #1 - sets target with upper and lower range limit, 2-sets target with lower limit only for ON and upper limit only for OFF.
#fast mode parameters
fast_mode = False #Truen - Turns fast mode ON,  False - Turns fast mode OFF


#timing parameters
#prog_stime =
#read_stime = 
#sweep_stime = 
#wait_time = 



