"""
These functions import the board and supportive functions.

The key feature is the controller and it's dependencies. What this allows is for you to implement programs.

Using the dependent models of the parts, all communication should occur exactly as it would be either the real
Daffodil Board or with the model API.

If the imported library for the real board doesn't include certain libraries, such as the functions mapping
ADC/DAC values to physical quantities, then those would need to be externally created.
"""
import numpy as np
import time as t



sleep_time = 1/1000
DEBUG = True

def IVsweep_parallel(board,kernel,x,vstart,vend,step_mult,vgate,vref,backwards=False,configure=True):
    """
    The IVsweep function is designed to select an arbitrary device and do an IV sweep. It lets you
    select a kernel a column (x) or row (y) value. It lets you set a starting and end voltage. It lets you select
    what multiple of the DAC precision you would like to step through these biases. It lets you select a gate bias to apply
    to the device. It does not sweep gate bias. It does not, as this time, let you specify a number of clock cycles
    with which to program the device.

    It only supports single quadrant applications. the voltage should either be positive to positive or negative to negative.
    single quadrant sweep is enforced because crossing quadrants is degenerate. You would need to specify a reference bias
    on the transimpance amplifiers. 
    """


    if vend*vstart<0: # this guarantueess single quadrant sweeps
        raise ValueError("No Negative numbers requires only single quadrant sweeps!")

    #this code converts the voltages into dac code. 
    dac_code_start = board.dac_invertvout(abs(vstart))
    dac_code_end = board.dac_invertvout(abs(vend))
    gate_code = board.dac_invertvout(abs(vgate))
    ref_code = board.dac_invertvout(abs(vref))
    ground_code = board.dac_invertvout(abs(board.vground))


    #if you haven't selected the device, it will assert that device.
    #it selects the kern and then disables all the other col/rows.
    if configure:
        for i in range(board.xdim): board.COL_EN_tobe[i]=0
        for i in range(board.ydim): board.ROW_EN_tobe[i]=0
        board.set_kernel(kernel) # one of the 32 kernels is selected
    #the column we want is selected
    if (backwards): board.ROW_EN_tobe[x]=1
    else: board.COL_EN_tobe[x]=1
    gatebiases=[]
    rowbiases=[]
    colbiases=[]
    
    #we start by giving everything zero
    for i in range(board.xdim):
        if (backwards): gatebiases.append(gate_code)
        else: gatebiases.append(ground_code)
        colbiases.append(ground_code)
    for i in range(board.ydim):
        rowbiases.append(ground_code)

    #for our selected device, we bias it's gate
    gatebiases[x] = gate_code

    #we now tell the DACs to ground everything and bias our gate.
    board.setrefopamp(ref_code)
    board.setgatedacs(gatebiases)
    board.setcoldacs(colbiases)
    board.setrowdacs(rowbiases)
        
    if(backwards):
    	for i in range(board.ydim): board.COL_EN_tobe[i]=1
    else:
    	for i in range(board.xdim): board.ROW_EN_tobe[i]=1
    #t.sleep(sleep_time)
    

    #these store the IV curve
    currentlist=[]
    voltagelist=[]
    
    #dac_code_start = ground_code 
    steps = (dac_code_end-dac_code_start)//step_mult #this is  how many steps we will take
    
    # if vend < 0 or vstart < 0 :
    if backwards:
        # TODO
        #if we are in the negative valued region, we do a backward pass.
        #we will apply to rows and measure currents on columns
        #for i in range(board.xdim): board.COL_EN_tobe[i]=0
        
        board.config_backward_pass()
        rowbiases[x]=dac_code_start
        for i in range(steps):
            board.setrowdacs(rowbiases)
            #we set our bias and assert an event
            board.event()
            #we attach our voltage to the voltage list by converting the register value to a voltage
            voltagelist.append(-board.dac_calcvout(rowbiases[x])+board.dac_calcvout(ref_code))
            #we readout the ADC value, convert it to a voltage, and finally a current using the potentiometer value
            for i in range(board.xdim): board.COL_EN_tobe[i]=1
            t.sleep(sleep_time)
            currentlist.append(-(board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)
            rowbiases[x]+=1*step_mult
            t.sleep(sleep_time)
        rowbiases[x]=dac_code_end
         
        for i in range(steps):
            #we repeat what we did above, except now we are counting down!
            board.setrowdacs(rowbiases)
            board.event()
            voltagelist.append(-board.dac_calcvout(rowbiases[x])+board.dac_calcvout(ref_code))
            for i in range(board.xdim): board.COL_EN_tobe[i]=1
            t.sleep(sleep_time)
            currentlist.append(-(board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)
            rowbiases[x]+=-1*step_mult
            t.sleep(sleep_time)

        if rowbiases[x] != dac_code_start:
            #if we don't end exactly at the start, we do a start voltage measurement. It will close a nice loop 
            rowbiases[x]=dac_code_start
            board.setrowdacs(rowbiases)
            board.event()
            voltagelist.append(-board.dac_calcvout(rowbiases[x])+board.dac_calcvout(ref_code))
            for i in range(board.xdim): board.COL_EN_tobe[i]=1
            t.sleep(sleep_time)
            currentlist.append(-(board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)

    else:
        board.config_forward_pass()
        #since we are in the positive quadrant, we can specify a forward pass
        #we will apply to columns and measure currents on rows
        colbiases[x]=dac_code_start
        for i in range(steps):
            board.setcoldacs(colbiases) #, ref_code, gatebiases, rowbiases)
            #we set or bias and assert an event
            board.event()
            #we attach our voltage to the voltage list by converting the register value to a voltage
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            #we readout the ADC value, convert it to a voltage, and finally a current using the potentiometer value
            for i in range(board.ydim): board.ROW_EN_tobe[i]=1        
            t.sleep(0.001)
            currentlist.append((board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)
            colbiases[x]+=1*step_mult
        colbiases[x]=dac_code_end

        #for i in range(board.ydim): board.ROW_EN_tobe[i]=0
        for i in range(steps):
            # now we go in the opposite direction!
            board.setcoldacs(colbiases)
            board.event()
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            for i in range(board.ydim): board.ROW_EN_tobe[i]=1        
            t.sleep(sleep_time)
            currentlist.append((board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)
            colbiases[x]+=-1*step_mult
        for i in range(board.ydim): board.ROW_EN_tobe[i]=0        

        if colbiases[x] != dac_code_start:
            #if we don't end where we started we'll measure here just to get a nice loop
            colbiases[x]=dac_code_start
            board.setcoldacs(colbiases)
            board.event()
         
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            for i in range(board.ydim): board.ROW_EN_tobe[i]=1        

            t.sleep(sleep_time)
            currentlist.append((board.adc_predict_voltage(np.array(board.retrievecurrents()))-board.dac_calcvout(ref_code))/board.pots)

    #we return these lists to plot
    return voltagelist, currentlist


def IVsweep(board,kernel,x,y,vstart,vend,step_mult,vgate,vref,backwards=False,configure=True):
    """
    The IVsweep function is designed to select an arbitrary device and do an IV sweep. It lets you
    select a kernel a column (x) or row (y) value. It lets you set a starting and end voltage. It lets you select
    what multiple of the DAC precision you would like to step through these biases. It lets you select a gate bias to apply
    to the device. It does not sweep gate bias. It does not, as this time, let you specify a number of clock cycles
    with which to program the device.

    It only supports single quadrant applications. the voltage should either be positive to positive or negative to negative.
    single quadrant sweep is enforced because crossing quadrants is degenerate. You would need to specify a reference bias
    on the transimpance amplifiers. 
    """


    if vend*vstart<0: # this guarantueess single quadrant sweeps
        raise ValueError("No Negative numbers requires only single quadrant sweeps!")

    #this code converts the voltages into dac code. 
    dac_code_start = board.dac_invertvout(abs(vstart))
    dac_code_end = board.dac_invertvout(abs(vend))
    gate_code = board.dac_invertvout(abs(vgate))
    ref_code = board.dac_invertvout(abs(vref))
    ground_code = board.dac_invertvout(abs(board.vground))

    #if you haven't selected the device, it will assert that device.
    #it selects the kern and then disables all the other col/rows.
    if configure:
        board.set_kernel(kernel) # one of the 32 kernels is selected
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=0 # the columns are disabled
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=0 # the rows are disabled

    #the row we want is selected
    board.COL_EN_tobe[x]=1
    board.ROW_EN_tobe[y]=1

    # we instantiate our lists 
    gatebiases=[]
    rowbiases=[]
    colbiases=[]
    
    #we start by giving everything zero
    for i in range(board.xdim):
        gatebiases.append(ground_code)
        colbiases.append(ground_code)
    for i in range(board.ydim):
        rowbiases.append(ground_code)

    #for our selected device, we bias it's gate
    gatebiases[x] = gate_code

    #we now tell the DACs to ground everything and bias our gate.
    board.setrefopamp(ref_code)
    board.setgatedacs(gatebiases)
    board.setcoldacs(colbiases)
    board.setrowdacs(rowbiases)

    #these store the IV curve
    currentlist=[]
    voltagelist=[]

    steps = (dac_code_end-dac_code_start)//step_mult #this is  how many steps we will take

    if backwards:
        #if we are in the negative valued region, we do a backward pass.
        #we will apply to rows and measure currents on columns
        board.config_backward_pass()
        rowbiases[y]=dac_code_start
        for i in range(steps):
            board.setrowdacs(rowbiases)
            #we set our bias and assert an event
            board.event()
            #we attach our voltage to the voltage list by converting the register value to a voltage
            voltagelist.append(-board.dac_calcvout(rowbiases[y])+board.dac_calcvout(ref_code))
            #we readout the ADC value, convert it to a voltage, and finally a current using the potentiometer value
            t.sleep(sleep_time)
            currentlist.append(-(board.adc_predict_voltage(board.retrievecurrents()[x])-board.dac_calcvout(ref_code))/board.pots[x])
            rowbiases[y]+=1*step_mult

        rowbiases[y]=dac_code_end
        for i in range(steps):
            #we repeat what we did above, except now we are counting down!
            board.setrowdacs(rowbiases)
            board.event()
            voltagelist.append(-board.dac_calcvout(rowbiases[y])+board.dac_calcvout(ref_code))
            currentlist.append(-(board.adc_predict_voltage(board.retrievecurrents()[x])-board.dac_calcvout(ref_code))/board.pots[x])
            rowbiases[y]+=-1*step_mult

        if rowbiases[y] != dac_code_start:
            #if we don't end exactly at the start, we do a start voltage measurement. It will close a nice loop 
            rowbiases[y]=dac_code_start
            board.setrowdacs(rowbiases)
            board.event()
            voltagelist.append(-board.dac_calcvout(rowbiases[y])+board.dac_calcvout(ref_code))
            currentlist.append(-(board.adc_predict_voltage(board.retrievecurrents()[x])-board.dac_calcvout(ref_code))/board.pots[x])

    else:
        board.config_forward_pass()
        #since we are in the positive quadrant, we can specify a forward pass
        #we will apply to columns and measure currents on rows
        colbiases[x]=dac_code_start
        for i in range(steps):
            board.setcoldacs(colbiases)
            #we set our bias and assert an event
            board.event()
            #we attach our voltage to the voltage list by converting the register value to a voltage
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            #we readout the ADC value, convert it to a voltage, and finally a current using the potentiometer value
            t.sleep(sleep_time)
            currentlist.append((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[y])
            colbiases[x]+=1*step_mult

        colbiases[x]=dac_code_end
        for i in range(steps):
            # now we go in the opposite direction!
            board.setcoldacs(colbiases)
            board.event()
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            currentlist.append((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[y])
            colbiases[x]+=-1*step_mult

        if colbiases[x] != dac_code_start:
            #if we don't end where we started we'll measure here just to get a nice loop
            colbiases[x]=dac_code_start
            board.setcoldacs(colbiases)
            board.event()
            voltagelist.append(board.dac_calcvout(colbiases[x])-board.dac_calcvout(ref_code))
            currentlist.append((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[y])
            
    #we return these lists to plot
    return voltagelist, currentlist
    
    
    



def init_dacs(ground_code,board,ref_code):
    #Sets all columns and rows to zero/ground state.
    rowbiases=[]
    gatebiases=[]
    colbiases=[]
    currentlist=[]
    voltagelist=[]
    for i in range(board.xdim):
        gatebiases.append(ground_code)
        colbiases.append(ground_code)
    for i in range(board.ydim):
        rowbiases.append(ground_code)
    board.setrefopamp(ref_code)
    board.setgatedacs(gatebiases)
    board.setcoldacs(colbiases)
    board.setrowdacs(rowbiases)
    
     
def read_device(col_code, row_code, gate_code, x ,y, pulselen, ground_code, board, ref_code):
    #Read is always performed on fwd configuration. Reads current on rows for a given  Vread 
    board.config_forward_pass()
    board.set_compliance_control(1)
    rowbiases=[]
    gatebiases=[]
    colbiases=[]
    write=False
    for i in range(board.xdim):
        gatebiases.append(ground_code)
        colbiases.append(ground_code)
    for i in range(board.ydim):
        rowbiases.append(ground_code)
    gatebiases[x] = gate_code
    rowbiases[y] = row_code
    colbiases[x] = col_code
    board.setgatedac_channel(gatebiases[x], x)
    board.setrowdac_channel(rowbiases[y], y )
    board.setcoldac_channel(colbiases[x], x)
    #t.sleep(0.05)
    board.event_timevariant(pulselen, write=False)
    #Sleep time should be adjusted. But may not be necessary when parallel DAC programming is implemented in FPGA.
   
    avg_current = 0
    #There is still plenty of noise while reading the ADC. We are currently averaging 4 reads to overcome noise.
    for i in range(1):
        #read_current = ((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[x])*1000000
        read_current = ((board.adc_predict_voltage(board.retrievecurrent_channel(y))-board.dac_calcvout(ref_code))/board.pots[x])*1000000
        avg_current = avg_current + read_current
    current = avg_current/1 
    t.sleep(0.01)
    
    return current


def program (col_code, row_code, gate_code, x ,y, pulselen, ground_code, board, ref_code):
    #Simple routine to program DACS. Incluces even pulse width programming.
    rowbiases=[]
    gatebiases=[]
    colbiases=[]
    write = True
    for i in range(board.xdim):
        gatebiases.append(ground_code)
        colbiases.append(ground_code)
    for i in range(board.ydim):
        rowbiases.append(ground_code)
    gatebiases[x] = gate_code
    rowbiases[y] = row_code
    colbiases[x] = col_code
    board.setgatedac_channel(gatebiases[x], x)
    board.setrowdac_channel(rowbiases[y], y)
    board.setcoldac_channel(colbiases[x], x)
    board.event_timevariant(pulselen, write=True)
    broken_device = 0
    t.sleep(0.005)
    
#def form_device (col_code, row_code, gate_code,  x ,y, ground_code, board, prm, ref_code, form_inc, vtolerant, form_max, on, fast_mode = True):
def form_device (col_code, row_code, gate_code, x ,y, ground_code, board, prm, ref_code, form_inc, vtolerant, form_max, on, fast_mode = True):
    #Device forming with non-variation method. This is the same as set operation. We will use this method until variation based forming works.
    #This method increments vgate gradually for a set Vrow and measure the current on columns. It searches for switch in the current by calculating slope between two point.
    #When the device is almost saturated (read constant or almost constant) current, sweep is stopped and reversed
    print("Form/Set begin") 
    currentlist=[]
    voltagelist=[]
    board.set_compliance_control(0)
    board.config_backward_pass()
    gate_sweep_code = ground_code
    status = 1
    vstart = prm.vstart
    row_code_start = board.dac_invertvout(abs(vstart))
    gate_code_end = board.dac_invertvout(abs(vstart + 3.2)) #4.8 DAC can only provide upto 4.85xx so limiting to 4.8
    vread = prm.vread
    col_read_code = board.dac_invertvout(abs(vread))


    switch, cnt, formed_voltage = 0, 0, 0
    read_pulse_len = prm.read_pulse_len #375ms
    write_pulse_len = prm.write_pulse_len #375ms
    max_current =  form_max #480 #490 for sweep #uA Max current in backward pass is 550uA. Dont want to go all the way to 550
    gate_code_1v = board.dac_invertvout(abs(1.2))
    fast_gate_sweep_code = gate_sweep_code + gate_code_1v
    break_next = 0
    fast_mode = False
    if(fast_mode):
        #Programs to 2.7v and then steps
        program(col_code, row_code, fast_gate_sweep_code, x, y, write_pulse_len, ground_code, board, ref_code)
        t.sleep(0.06)
        voltagelist.append(-board.dac_calcvout(fast_gate_sweep_code)+board.dac_calcvout(ref_code))
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)/1000000)
        currentlist.append(-(board.adc_predict_voltage(board.retrievecurrent_channel(x))-board.dac_calcvout(ref_code))/board.pots[x])
        gate_sweep_code = fast_gate_sweep_code
        form_steps = int((gate_code-fast_gate_sweep_code)//form_inc) #this is  how many steps we will take
    else:
        form_steps = int((gate_code-col_code)//form_inc) #this is  how many steps we will take
    

    for i in range(form_steps):
        program(col_code, row_code, gate_sweep_code, x, y, write_pulse_len, ground_code, board, ref_code)
        voltagelist.append(-board.dac_calcvout(gate_sweep_code)+board.dac_calcvout(ref_code))
        t.sleep(0.06)
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)/1000000)
        currentlist.append(-(board.adc_predict_voltage(board.retrievecurrent_channel(x))-board.dac_calcvout(ref_code))/board.pots[x])
        
        if(i >= 3):
            slope = ((currentlist[i] - currentlist[i-3])/(voltagelist[i] -  voltagelist[i-3])) * 1000
            if(slope > 0.4):
                switch = 1
                cnt = cnt + 1
            #if(cnt >= 3 and ((currentlist[i] - currentlist[i-1] in  r) and (currentlist[1-2] - currentlist[i-3] in r))):
            diff = (currentlist[i]*10**6 - currentlist[i-1]*10**6) 
            abs_current = abs(currentlist[i])*10**6
            
            if(DEBUG):  print("Current(uA)", currentlist[i]*10**6,"Vgate",voltagelist[i], "slope", slope)
            #if((abs_current > 400 and cnt >= 2 and diff < 5 and diff > -5) or abs_current > max_current or voltagelist[i] > 2.8): # or (abs_current > 480)): #If the current stays almost constant with =5/-5 uA difference, saturation reached. so end and reverse sweep to 0
            if((cnt >= 3 and diff < 5 and diff > -5) or (abs_current > max_current or voltagelist[i] < -2.8 )): # or (abs_current > 480)): #If the current stays almost constant with =5/-5 uA difference, saturation reached. so end and reverse sweep to 05
                if(DEBUG):  print("Form/Set end (with switch)")   
                formed_voltage = voltagelist[i]  
                switch = 1
                break                
            elif((gate_sweep_code > (gate_code)  and cnt >= 2)): # Max gate voltage is 4.9v. We dont want to sweep all the way to 4.9v and break the device if switching does not happen.
                if(DEBUG):  print("Form/Set end (without switch)")       
                formed_voltage = voltagelist[i]                

                break
            elif(slope > 1.0):
                break_next = 1
            elif(break_next == 1):
                    #if(DEBUG):  print("Sharp  drop")
                    switch = 1
                    #break
                
        gate_sweep_code = gate_sweep_code+1*form_inc
        t.sleep(0.01)
       
    #If fast mode enabled. Increase the step size in reverse sweep. This is mainly done to reduce sweep/form/set time.     
    if(fast_mode):
        form_inc = form_inc*8
    else:
        form_inc = form_inc
    if(switch == 1):
        gate_sweep_code = gate_sweep_code     
        form_steps = (gate_sweep_code-ground_code)//(form_inc) #this is  how many steps we will take
    else:
        gate_sweep_code = gate_code
        form_steps = (gate_code-ground_code)//(form_inc)
        
    for j in range(form_steps):
        program(col_code, row_code, gate_sweep_code, x, y, write_pulse_len, ground_code, board, ref_code)
        voltagelist.append(-board.dac_calcvout(gate_sweep_code)+board.dac_calcvout(ref_code))
        gate_sweep_code = gate_sweep_code-1*form_inc
        t.sleep(0.01)       
        currentlist.append(-(board.adc_predict_voltage(board.retrievecurrent_channel(x))-board.dac_calcvout(ref_code))/board.pots[x])
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, pulse_len, ground_code, board, ref_code)/1000000)

        if(DEBUG):  print("Current(uA)", currentlist[i+j]*10**6,"Vgate",voltagelist[i+j])
    
    if gate_sweep_code != ground_code:
        #if we don't end exactly at the start, we do a start voltage measurement. It will close a nice loop 
        gate_sweep_code = ground_code
        program(col_code, row_code, gate_sweep_code, x, y, write_pulse_len, ground_code, board, ref_code)
        voltagelist.append(-board.dac_calcvout(gate_sweep_code)+board.dac_calcvout(ref_code))
        currentlist.append(-(board.adc_predict_voltage(board.retrievecurrent_channel(x))-board.dac_calcvout(ref_code))/board.pots[x])    
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, pulse_len, ground_code, board, ref_code)/1000000)

        t.sleep(0.01)       

        if(DEBUG):  print("Current(uA)", currentlist[i+j+1]*10**6,"Vgate",voltagelist[i+j]+1)
    if(cnt < 1): status = 0    
    return voltagelist, currentlist, status
 
            

#def set_target (board,prm,kernel,x,y,vcol,vrow,vgate, form=True,set_current= True,on=True,swfix_en = False):
def set_target (board,prm,kernel,x,y,vcol,vrow,vgate, tc, form=True,set_current= True,swfix_en = False):
    
    
    fast_mode = False
    vstart = prm.vstart
    vref = prm.vref 
    vread = prm.vread
    #converts the voltages into dac code. 
    
    col_code_start = board.dac_invertvout(abs(vstart))
    col_code_start_new = board.dac_invertvout(abs(vstart+0.8))
    col_code_end = board.dac_invertvout(abs(vcol))
    col_read_code = board.dac_invertvout(abs(vread))
    row_code_start = board.dac_invertvout(abs(vstart))
    row_code_end = board.dac_invertvout(abs(vrow)) #3.4
    gate_code_start = board.dac_invertvout(abs(vstart))
    gate_code_start_new = board.dac_invertvout(abs(vstart+2.5))
    gate_code_end = board.dac_invertvout(abs(vstart + 3.3)) #4.8 DAC can only provide upto 4.85xx so limiting to 4.8
    gate_code_fwd = board.dac_invertvout(abs(vgate))
    gate_sweep_code = gate_code_start
    ref_code = board.dac_invertvout(abs(vref))
    ground_code = board.dac_invertvout(abs(board.vground))
    setcurrent = 0
    curr_diff = 0
    
    #Initial values that may require some tweaking
    on_current_margin, off_current_margin = prm.on_margin, prm.off_margin #(30uA)
    form_inc = prm.form_inc #(0.05v) Form steps can be larger 
    sweep_inc = prm.sweep_inc    
    max_current = 300 #300uA
    write_pulse_len = prm.write_pulse_len #375ms
    read_pulse_len = prm.read_pulse_len #375ms
    #target_current = prm.target_current
    target_current = tc
    
    #Initializations (no need to change)
    if(target_current <= prm.max_target_current and target_current > (prm.max_target_current-10)):
        on_target = target_current
        on = True
    elif(target_current <= (prm.max_target_current-10)):
        off_target = target_current
        on = False
    else:
        on = True
        
    if(on):
        print ("Turning on", "device in column:", x, "row:", y, "kernel:", kernel, "Target Current", target_current)
    else:
        print ("Turning off", "device in column:", x, "row:", y, "kernel:", kernel,  "Target Current", target_current)    
    target_reached, sweep_cnt  = 0, 0
    max_sweep_cnt = prm.max_iterations
    target_on_reached = False
    target_off_reached = False
    ON = 1
    OFF = 0
    form_vcol_steps = int((gate_code_end-gate_code_start)//form_inc) #this is  how many steps we will take
    set_vcol_steps = int((gate_code_end-gate_code_start)//sweep_inc) #this is  how many steps we will take
    status = 0    
    form_status = 1    
    board.set_kernel(kernel, swfix_en = swfix_en) # one of the 32 kernels is selected
    if prm.configure:
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=0 # the columns are disabled
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=0 # the rows are disabled

    #the row and col we want is selected
    if((x == 13 or x == 14) and swfix_en):
        board.COL_EN_tobe[14]=1
        board.COL_EN_tobe[13]=1
    else:
        board.COL_EN_tobe[x]=1
    board.ROW_EN_tobe[y]=1

    #Algorithm selections

    vtolerant = False
    re_form = False
    form_max = prm.form_max_cur
    while(target_reached == 0):
        sweep_cnt = sweep_cnt + 1
        if(form or re_form):
            init_dacs(ground_code, board, ref_code)
            voltagelist, currentlist, form_status = form_device(col_code_start, row_code_end, gate_code_end, x, y, ground_code, board, prm, ref_code, form_inc, vtolerant, form_max, on, fast_mode = False)
            target_reached = 1 
            t.sleep(0.01)
        target_on_reached = False
        target_off_reached = False    
        currentlist=[]
        voltagelist=[]
        if(set_current):
            init_dacs(ground_code, board, ref_code)
            #RESET
            print("Target sweep/set iteration:", sweep_cnt )
            target_reached = 0
            is_decreasing, is_increasing = 0, 0
            wait_for_off_curr = 0
            off_curr_overshoot_cnt= 0
            reset_vcol_steps = 0
            col_sweep_code = 0
            done = 0
            off_ratio, on_ratio = 0, 0
            prev_resist = 0
            i, k , m  = 0, 0, 0
            dec_cnt, cnt, oshoot_cnt, k, cdiff, p_cdiff, vdiff, pdiff = 0, 0, 0, 0, 0, 0, 0, 0
            
            board.set_compliance_control(ON)

            #if(not(on)):
            if(form_inc > 100):
                sweep_inc  = prm.sweep_inc
                col_sweep_code = col_code_start_new
                reset_vcol_steps = int((col_code_end-col_code_start_new)//sweep_inc) #this is  how many steps we will take
            else:    
                sweep_inc  = prm.sweep_inc
                col_sweep_code = col_code_start
                reset_vcol_steps = int((col_code_end-col_code_start)//sweep_inc) #this is  how many steps we will take
            #Sweep for on and off current in steops

            for i in range(reset_vcol_steps):
                #Configure
                board.config_forward_pass()
                avg_current = 0
                #Start programming column
                program(col_sweep_code,  row_code_start, gate_code_fwd, x, y, write_pulse_len, ground_code, board, ref_code)
                voltagelist.append(board.dac_calcvout(col_sweep_code)-board.dac_calcvout(ref_code))
                #if programmed voltage reaches over read volt, start reading at vread
                if(voltagelist[i] > (prm.vread-prm.vref)):
    
                    #for m in range(1):
                    current = read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)
                    currentlist.append(current)
                    abs_current = abs(currentlist[i])
                    init_current = abs(currentlist[k])
                    
                    if(target_current < init_current):
                        on = False
                    else:    
                        on = True
                        
                    if(prm.alg_option == 1):
                        if(on):
                            on_target = target_current
                            on_up_limit = on_target+on_current_margin
                            on_low_limit = on_target-on_current_margin
                        else:
                            off_target = target_current
                            off_up_limit = off_target+off_current_margin
                            off_low_limit = off_target-off_current_margin
                    else:
                        if(on):
                            on_target = target_current
                            on_up_limit = 500
                            on_low_limit = on_target-on_current_margin
                        else:
                            off_target = target_current
                            off_up_limit = off_target+off_current_margin
                            off_low_limit = 0                    
                    
                    #Overshoot and noise detection. These conditions are set based on various observations. The conditions are mostly to prevent the device from breaking. As it turns some RRAM devices break even from 
                    #mild overshoots. So I have tried to capture all possible overshoot scenarios
                    if(i > 4 and (currentlist[i] - currentlist[i-1]) > 2 and (currentlist[i-1] - currentlist[i-2]) > 2 and (currentlist[i-2] - currentlist[i-3]) > 2):
                        is_increasing = 1
                        is_decreasing = 0
                    elif(i > 4 and (currentlist[i-1] - currentlist[i]) > 2 and (currentlist[i-2] - currentlist[i-1]) > 2 and (currentlist[i-3] - currentlist[i-2]) > 2):  
                        is_increasing = 0
                        is_decreasing = 1
                    else:
                        is_increasing = 0
                        is_decreasing = 0
                    if(is_decreasing == 1 and not(on)):
                        wait_for_off_curr = 1    
                        
                    if(voltagelist[i] > prm.switching_voltage and done == 0):    
                        on_ratio = abs_current
                        off_ratio = abs_current/4
                        done = 1    
                    if(wait_for_off_curr == 1 and is_increasing == 1 ):
                        off_curr_overshoot_cnt = off_curr_overshoot_cnt + 1
                    else:
                        off_curr_overshoot_cnt = 0

                    if(sweep_cnt <= max_sweep_cnt-1  and (currentlist[i] - currentlist[i-1] > 8) and  (currentlist[i] - currentlist[i-2]   > 8) and (currentlist[i] - currentlist[i-3]   > 8) and (is_increasing == 0 and voltagelist[i] > 0.8 ) and (currentlist[i] != currentlist[i-1]) and (currentlist[i] != [i-2])):
                       if(DEBUG):   print("Unusual activity. So breaking the sweep")
                       is_noise = 1
                       break
                    else:
                        is_noise = 0
                   
                    if(currentlist[i] < 0):
                        actual_resist =  round((voltagelist[i]/currentlist[i])*10**3,0)
                        resist_diff = actual_resist - prev_resist
                        curr_diff = currentlist[i] - currentlist[i-1]
                        prev_resist = actual_resist
                    else:
                        resist_diff = 0

                    if(DEBUG):  print("Current at 0.3v", abs_current, "for Vcol:",   round(voltagelist[i],2))    

                    if(not(on)):
                        if(off_low_limit <= abs_current <= off_up_limit  and (target_off_reached == False)):
                            if(DEBUG):  print("OFF Target reached in reset",  round(voltagelist[i],2))      
                            target_off_reached = True   
                            offV_start = voltagelist[i]    
                        elif((currentlist[i] - init_current > 8) and sweep_cnt <= max_sweep_cnt-1):    
                            if(DEBUG):  print("OFF: Sudden rise in current. This might break the device. So breaking the sweep for now")
                            break
                        elif((off_curr_overshoot_cnt == 5 or abs_current > 450 or is_noise == 1) or curr_diff > 5 and done == 1 and sweep_cnt != max_sweep_cnt):
                            if(DEBUG):  print("OFF: Noise detected")
                            if(DEBUG):  print("Current at vread 0.3v", abs_current, "for Vcol:",   round(voltagelist[i],2))    
                            break
                        elif(currentlist[i] < off_target):
                            
                            break        
                        
                            
                    else:
                        if(on_low_limit <= abs_current <= on_up_limit and (target_on_reached == False)):
                            if(DEBUG):  print("On Target reached in reset",  round(voltagelist[i],2))   
                            target_on_reached = True
                        elif(((voltagelist[i] > prm.switching_voltage and currentlist[i] < target_current) or (init_current - currentlist[i] > 3))) :
                            if(DEBUG):  print("ON: Sudden rise in current. This might break the device. So breaking the sweep for now")
                            break    
                        elif((off_curr_overshoot_cnt == 5 or abs_current > 450 or is_noise == 1) or resist_diff < -2 and done == 1 and sweep_cnt != max_sweep_cnt):
                            if(DEBUG):  print("Current at vread 0.3v", abs_current, "for Vcol:",   round(voltagelist[i],2))    
                            if(DEBUG):  print("ON: Noise detected")
                            if(DEBUG):  print("Current at vread 0.3v", abs_current, "for Vcol:",   round(voltagelist[i],2))    
                            break

                    #ON and OFF current targets met   
                    if(target_on_reached or target_off_reached):
                        target_diff = target_current - currentlist[i]
                        #if(target_diff < -6):
                            #fine_steps = 0
                            # for fine_steps in range(10):
                                    # program(col_sweep_code,  row_code_start, gate_code_fwd, x, y, write_pulse_len, ground_code, board, ref_code)
                                    # fineC = read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)
                                    # col_sweep_code = col_sweep_code + 1;
                                    # voltagelist[i] = board.dac_calcvout(col_sweep_code)-board.dac_calcvout(ref_code)
                                    ## currentlist[i] = fineC
                                    ## input("continue")
                                    # print("Fine tuning current to ", fineC, "difference", (target_current - fineC))
                                    # currentlist[i] = fineC
                                    # if((target_current - fineC) > -6):    
                                        # break 

                        if(DEBUG):  print("targets met")                    
                        target_reached = 1
                        break
                else:
                    currentlist.append(0.0)
                    k  = k + 1
                col_sweep_code = col_sweep_code+1*sweep_inc
                
            if(target_reached == 1):
                if(on == True):
                    status = 1
                    print("****** Requested Current", target_current,  ": Device set to", round(currentlist[i],2),  "after", sweep_cnt, "attempts","******")
                    setcurrent = round(currentlist[i],2)
                else:
                    status = 1
                    print("****** Requested Current", target_current,  ": Device set to", round(currentlist[i],2),  "after", sweep_cnt, "attempts","******")
                    setcurrent = round(currentlist[i],2)
                break
            
             
            #SET
            re_form = False
            #gate_sweep_code = gate_code_start
            gate_sweep_code = gate_code_start_new
            dec_cnt, oshoot_cnt, k, cdiff, p_cdiff, pdiff = 0, 0, 0, 0, 0, 0
            if(fast_mode):  sweep_inc = sweep_inc *4
            else:  sweep_inc = sweep_inc
            set_vcol_steps = int((gate_code_end-gate_code_start_new)//sweep_inc) #this is  how many steps we will take
            #set_vcol_steps = int((gate_code_end-gate_code_start)//sweep_inc) #this is  how many steps we will take
            form = True
            for j in range(set_vcol_steps):
                if(not(on)):
                    re_form = False
                    form = True
                    if(abs(currentlist[i]) > off_target):
                        break
                else:
                    if(abs(currentlist[i]) > on_target):
                        break
                    
                board.set_compliance_control(OFF) 
                board.config_backward_pass()
                program(col_code_start, row_code_end, gate_sweep_code, x, y, write_pulse_len, ground_code, board, ref_code)
                voltagelist.append(-board.dac_calcvout(gate_sweep_code)+board.dac_calcvout(ref_code))
                        

                gate_sweep_code = gate_sweep_code+1*(sweep_inc)
                if(voltagelist[i+j] < -0.1):
                    currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code))
                    abs_current = abs(currentlist[i+j])
                    
                    #Break check Conditions
                    cdiff = abs(currentlist[i+j]) - abs(currentlist[i+k])
                    pdiff = abs(currentlist[i+j-1]) - abs(currentlist[i+j])
                    if(cdiff > 20):
                        dec_cnt = dec_cnt + 1
                    if(dec_cnt > 3 and pdiff > 15):
                        oshoot_cnt = oshoot_cnt + 1
                    if(DEBUG):  print("Current at", col_read_code, ":", abs_current, "for Vgate:",   round(voltagelist[i+j],2), "for vrow:", row_code_start, "cdiff", round(cdiff),"pdiff", round(p_cdiff), "dec", dec_cnt, "ocnt", oshoot_cnt)  
                                        
                                        
                    # Break if OFF target achieved
                    if(not(on)):
                        
                        if(off_low_limit <= abs_current <= off_up_limit  and (target_off_reached == False)):
                            if(DEBUG):  print("OFF Target reached in set",  round(voltagelist[i],2))      
                            target_off_reached = True
                            
                        elif(abs_current > target_current):
                            if(sweep_cnt == max_sweep_cnt): sweep_cnt = sweep_cnt - 1
                            break
                    else:
                        if(on_low_limit <= abs_current <= on_up_limit and (target_on_reached == False)):
                            if(DEBUG):  print("On Target reached in set",  round(voltagelist[i],2))   
                            target_on_reached = True    
                        elif(abs_current > target_current):
                            break           
                    
                    
                    if(target_on_reached or target_off_reached):
                        if(DEBUG):  print("targets met")                    
                        target_reached = 1
                        break                                
                                        
                    #Break if ovreshoot 
                    if(i+j-k >= 3 and oshoot_cnt > 3):    
                        if(DEBUG):  print("Current at vread 0.3v", ":", abs_current, "for Vgate:",   round(voltagelist[i+j],2), "for vrow:", row_code_start,"cdiff",round(cdiff),"pdiff", round(p_cdiff), "dec", dec_cnt, "ocnt", oshoot_cnt)                        
                        if(DEBUG):  print("Set : Overshoot or high noise")   
                        break
                    # Break if max current reached    break
                    if(gate_sweep_code > gate_code_end or abs_current > max_current):
                        if(DEBUG):  print("Current at vread 0.3v", ":", abs_current, "for Vgate:",   round(voltagelist[i+j],2), "cdiff", cdiff,"pdiff", p_cdiff, "dec", dec_cnt, "ocnt", oshoot_cnt)                        
                        if(DEBUG):  print("Limit reached")
                        break
                    # Break if ON target achieved    
                    
                else:
                    currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)) 
                    #if(DEBUG):  print("Current at", col_read_code,  "for Vgate:",   round(voltagelist[i+j],2))                        

                    k = k + 1   
                #sweep_inc = sweep_inc/2           
        if(target_reached == 1):
                if(on == True):
                    status = 1
                    print("****** Requested Current", target_current,  ": Device set to", abs_current,  "after", sweep_cnt, "attempts  ******")
                    setcurrent = round(currentlist[i+j],2)

                else:
                    status = 1
                    setcurrent = round(currentlist[i+j],2)
                    print("****** Requested Current", target_current, ": Device set to ", abs_current, "after",  sweep_cnt, "attempts  ******")
                break
        else:    
            if(sweep_cnt >= max_sweep_cnt):
                print("Unable to meet target")
                break    

        
        if(not(on)):
            form_max = form_max
        else: 
            form_max = form_max

    #we return these lists to plot
    return voltagelist, setcurrent, status
   
           

def sweep_IV (board, kernel, prm,x,y,vcol,vrow,vgate, backwards=True, swfix_en = False):

    vstart = prm.vstart
    vref = prm.vref
    vread = prm.vread - vstart

    col_code_start = board.dac_invertvout(abs(vstart))
    col_code_end = board.dac_invertvout(abs(vcol))
    row_code_start = board.dac_invertvout(abs(vstart))
    row_code_end = board.dac_invertvout(abs(vrow)) #3.4
    gate_code_start = board.dac_invertvout(abs(vstart))
    gate_code_end = board.dac_invertvout(abs(vstart + 3.2)) #4.8 DAC can only provide upto 4.85xx so limiting to 4.8
    gate_code_fwd = board.dac_invertvout(abs(vgate))
    ref_code = board.dac_invertvout(abs(vref))
    ground_code = board.dac_invertvout(abs(board.vground))

    board.set_kernel(kernel, swfix_en = swfix_en) # one of the 32 kernels is selected

    if prm.configure:
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=0 # the columns are disabled
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=0 # the rows are disabled

    #the row and col we want is selected
    if((x == 13 or x == 14) and swfix_en):
        board.COL_EN_tobe[14]=1
        board.COL_EN_tobe[13]=1
    else:
        board.COL_EN_tobe[x]=1
        board.ROW_EN_tobe[y]=1
    
    currentlist=[]
    voltagelist=[]

    if(backwards):
        sweep_inc = 20
        vtolerant = False
        init_dacs(ground_code, board, ref_code)
        #form function is used for backward sweep
        voltagelist, currentlist, status = form_device(col_code_start, row_code_end, gate_code_end, x, y, ground_code, board, prm, ref_code, sweep_inc, vtolerant, fast_mode = False)

    else:
        sweep_inc = 10 
        vtolerant = False
        #init_dacs(ground_code, board, ref_code)
        voltagelist, currentlist = fwd_sweep_serial(col_code_start, col_code_end, row_code_start, gate_code_fwd, gate_code_end, x, y, ground_code, board, ref_code, sweep_inc, vtolerant, fast_mode = False)
    return voltagelist, currentlist
 

def fwd_sweep_serial (col_code_start, col_code_end, row_code_start, gate_code_fwd, gate_code_end, x, y, ground_code, board, ref_code, sweep_inc, vtolerant,  fast_mode = False): 
    #init_dacs(ground_code, board, ref_code)
    currentlist=[]
    voltagelist=[]  
    #t.sleep(0.1)
    col_sweep_code = col_code_start
    board.set_compliance_control(1)
    col_read_code = board.dac_invertvout(abs(0.3 + 1.7))

    reset_vcol_steps = int((col_code_end-col_code_start)//sweep_inc) #this is  how many steps we will take
    write_pulse_len = prm.write_pulse_len
    read_pulse_len = prm.read_pulse_len
    board.config_forward_pass()
    slope, oshoot_cnt = 0, 0
    max_current = 260
    cur_dec = False
    #Sweep for on and off current in steops
    for i in range(reset_vcol_steps):
        #Start programming column
        program(col_sweep_code,  row_code_start, gate_code_fwd, x, y, write_pulse_len, ground_code, board, ref_code)
        voltagelist.append(board.dac_calcvout(col_sweep_code)-board.dac_calcvout(ref_code))
        #if programmed voltage reaches over read volt, start reading at vread
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code))
        #if(vtolerant):  currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code))
        #currentlist.append((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[y])
        currentlist.append((board.adc_predict_voltage(board.retrievecurrent_channel(y))-board.dac_calcvout(ref_code))/board.pots[y])
        t.sleep(0.1)
        actual_current = currentlist[i]*10**6
        col_sweep_code = col_sweep_code+1*sweep_inc
        #Find overshoots
        cdiff = currentlist[i-1]*10**6 - currentlist[i]*10**6
        if(i > 4):  slope = ((currentlist[i] - currentlist[i-3])/(voltagelist[i] -  voltagelist[i-3])) * 1000
        if(slope < -0.5): cur_dec = True
        if((cur_dec and slope > 0) or  (cur_dec and cdiff < -10)): oshoot_cnt = oshoot_cnt + 1;
        #if(((cur_dec and cdiff < -20) or oshoot_cnt >= 2 or (actual_current > max_current))  or (cur_dec and voltagelist[i] > 1.1) ): break
        if((cur_dec and voltagelist[i] > 1.1) or (cur_dec and cdiff > 40) or (actual_current > max_current) or (cur_dec and cdiff < -20) ): break
        
        #Debug
        if(DEBUG):  print("Current at", col_sweep_code, ":", actual_current, "for Vcol:",   voltagelist[i], "slope", slope, "cdiff", cdiff, "oshoot", oshoot_cnt)    
            
        
    reset_vcol_steps = int((col_sweep_code-col_code_start)//sweep_inc) #this is  how many steps we will take    
    for j in range(reset_vcol_steps):
        program(col_sweep_code,  row_code_start, gate_code_fwd, x, y, write_pulse_len, ground_code, board, ref_code)
        voltagelist.append(board.dac_calcvout(col_sweep_code)-board.dac_calcvout(ref_code))
        #currentlist.append(read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code))
        #currentlist.append((board.adc_predict_voltage(board.retrievecurrents()[y])-board.dac_calcvout(ref_code))/board.pots[y])
        currentlist.append((board.adc_predict_voltage(board.retrievecurrent_channel(y))-board.dac_calcvout(ref_code))/board.pots[y])
        actual_current = currentlist[i+j]*10**6
        t.sleep(0.1)
        if(DEBUG):  print("Current at", col_sweep_code, ":", actual_current, "for Vcol:",   voltagelist[i+j], "slope", slope, "cdiff", cdiff, "oshoot", oshoot_cnt, "***********")    
        col_sweep_code = col_sweep_code-1*sweep_inc
       
                
    return voltagelist, currentlist
 
def heatmap_gen (board,prm,kernel,x,y, vgate, swfix_en = False):

    vstart = prm.vstart
    vref = prm.vref
    vread = prm.vread - vstart

    col_read_code = board.dac_invertvout(abs(vread + vstart))
    row_code_start = board.dac_invertvout(abs(vstart))
    gate_code_end = board.dac_invertvout(abs(vgate)) #4.8 DAC can only provide upto 4.85xx so limiting to 4.8
    ref_code = board.dac_invertvout(abs(vref))
    ground_code = board.dac_invertvout(abs(board.vground))

    board.set_kernel(kernel, swfix_en = swfix_en) # one of the 32 kernels is selected
    
    if prm.configure:
        for i in range(board.xdim):
            board.COL_EN_tobe[i]=0 # the columns are disabled
        for i in range(board.ydim):
            board.ROW_EN_tobe[i]=0 # the rows are disabled

    #the row and col we want is selected
    #board.COL_EN_tobe[x]=1
    #board.COL_EN_tobe[y]=1
    
    if((x == 13 or x == 14) and swfix_en):
        board.COL_EN_tobe[14]=1
        board.COL_EN_tobe[13]=1
    else:
        board.COL_EN_tobe[x]=1
    board.ROW_EN_tobe[y]=1
    
    read_pulse_len = prm.read_pulse_len
    init_dacs(ground_code, board, ref_code)
    board.set_compliance_control(1)
    board.config_forward_pass()
    current = read_device(col_read_code, row_code_start, gate_code_end, x, y, read_pulse_len, ground_code, board, ref_code)
    print("Current at 0.3v", current)

    return current
