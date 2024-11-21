import matplotlib.pyplot as plt
import time
#import Board
#from Board import controller

"""
These functions import the board and supportive functions.

The key thing imported, is the controller and it's dependencies. What this allows is for you to implement programs.

Using the dependent models of the parts, all communication should occur exactly as it would be either the real
Daffodil Board or with the model API.

If the imported library for the real board doesn't include certain libraries, such as the functions mapping
ADC/DAC values to physical quantities. Those would need to be externally created.

For this Daffodil API, we assume that the unit of voltage is volts and current is uA. 
"""

"""
The outerproduct.py program is designed to do outerproduct updates at the kernel level

it includes
1) an outerproduct primitive operation for either incrementing or decrementing an array
2) a full outerproduct operation which breaks up arbitrary vectors into 4
    primitive outerproducts depending on the sign of the members of the input vectors

This 4 fold decomposition guarantuess you will have no leakage paths during the update. This achives the minimum amount of leakage current.
In theory, you could do 2 primitive updates, but, with our current ReRAM chip, this would have enhanced leakage. I leave it to the reader to determine why 
as an exercise. This is also related to the choice of row assertions. If you do 4 updates you can leave lines floating, if you do 2, you will have unknown bias across floating rows.

In this application, outerproducts are performed using CLOCK CYCLE COUNTER INTEGER MULTIPLICATION. What that means is that depending on the
integer values in the vectors, we will have a specified number of events. Events are what define the state of the ReRAM array. 

For example, if the col_updates have largest integer value of 3 and the row_updates have a largest
integer value of 5, we will have a total of 15 events per outerproduct update. That's because we count to 5, 3 times. 

Events, at this time, do not have a sense of time. 

"""

def outer_product_primitive(board,vwrite,vgate,col_update,row_update,sig, configure=True):
    """
    The operation requires a board, write voltage, gate bias, and col/row_updates. The updates are integers. They will apply the bias an integer number of times.

    the sig specifies 0, positive (increment), or 1, negative (decrement) update operations.

    this operation will only work with POSITVE integers input into it

    #if the gate voltage is too low, the devices will not update. If it is intermediate, the devices will turn on, and then stop when they reach the
    current specified by the gate voltage. 
    """

    debug = False
    #we will need to modify the column_series, so copy these values. python passes pointers of lists
    col_series = col_update.copy()
    row_series = row_update.copy()

    if configure: 
        board.config_outerproduct()

    #based on the write vlues, this specifies all the DAC code values that need to be passed
    dac_code_write = board.dac_invertvout(abs(vwrite+board.vground))
    dac_code_zero = board.dac_invertvout(board.vground)
    dac_gate_code = board.dac_invertvout(abs(vgate))
    
    """
    the half value is special, the nonselected columns will have this voltage. this counterintuitive, but since we can't use negative numbers
    we must do a change of ground to do outerproduct updates
    this would work since we have a 2T-1R array
    we are going to cheat here since, even though we correctly configure the outerproduct operation
    we will not assert the lines with the half bias
    because of our chosen way of performing the updates, this is allowed, but we could do this in theoretically fewer operation but we would need to assert
    the half bias on all unselected lines to avoid uncontrollabe leakage currents which could potentially cause a read-disturb
    """
    dac_code_writehalf = board.dac_invertvout(abs(vwrite)/2 + board.vground) # the voltage across devices on non-active rows/columns
    dac_code_writehalf = board.dac_invertvout(board.vground) # experimental - zero bias on non-active rows/columns

    #these are the lists of biases 
    gatebiases=[]
    rowbiases=[]
    colbiases=[]

    if sig == 0:#if we are in the positive mode, the columns will have bias 
        dac_col_vol = dac_code_write
        dac_row_vol = dac_code_zero
    else: #if we are in the ngative mode, the rows will have bias. 
        dac_row_vol = dac_code_write
        dac_col_vol = dac_code_zero

    #we set everyting to the nonwrite configuration 
    for i in range(board.xdim):
        gatebiases.append(dac_code_zero)
        colbiases.append(dac_code_writehalf)
        board.COL_EN_tobe[i]=0
    for i in range(board.ydim):
        rowbiases.append(dac_code_writehalf)
        board.ROW_EN_tobe[i]=0

    #we assert our biases
    board.setcoldacs(colbiases)
    board.setgatedacs(gatebiases)
    board.setrowdacs(rowbiases)

    #for our clocked based integer multiplication, we ascertain the largest values
    maxcol = max(col_update)
    maxrow = max(row_update)

    if (debug):
        print('maxcol', 'maxrow', maxcol, maxrow)
        # possible optimzation - if max col OR max row 0, directly return

    for p in range(maxcol): # so we start an outerloop with the largest integer value in the column
        for i in range(len(col_series)): # we sweep the columns
            if col_series[i]>0: #if our vector has number in it, we use this column to update
                col_series[i]+=-1 #we decrement the value
                colbiases[i]=dac_col_vol #we give it the outerproduct value
                gatebiases[i]=dac_gate_code #we specify a nonzero gate bias
                board.COL_EN_tobe[i]=1 #we tell the board to assert it's value
            else:
                colbiases[i]=dac_code_writehalf #if we don't use it we give it the half voltage
                gatebiases[i]=dac_code_zero # we set the gate to zero
                board.COL_EN_tobe[i]=0 # we also do not assert the value
                #in the future, we may want to actually assert this line even though the gate bias is zero so that the line is biased.
                 #this would help control the impedance on the lines by not having floating wires. 
                
        #this sets the biases
        #we can hold these values here for quite a while until we do a whole roq sequence 
        
        if (debug):
            gatebiases_converted = [board.dac_calcvout(gatebias) for gatebias in gatebiases]
            colbiases_converted = [board.dac_calcvout(colbias) for colbias in colbiases]
            print('gatebiases', gatebiases_converted)
            print('colbiases', colbiases_converted)
        board.setcoldacs(colbiases)
        board.setgatedacs(gatebiases)

        #we reinitialize the row values. this is why we stored a copy 
        for h in range(len(row_series)):
            row_series[h]=row_update[h]
        
        for q in range(maxrow): #we now go into a loop the size of the maximum row 
            for j in range(len(row_series)):
                if row_series[j]>0: #if the vector has a nonzero value
                    row_series[j]+=-1 #we will decrement it
                    rowbiases[j]=dac_row_vol #we will give it's dac the right voltage
                    board.ROW_EN_tobe[j]=1 #we will assert the row during an event
                else:
                    rowbiases[j]=dac_code_writehalf #we will give it half bias
                    board.ROW_EN_tobe[j]=0 #we will not assert the row during an event. we could choose to assert this so as to better control the impedance of neighboring wires
            board.setrowdacs(rowbiases)#we will set the biases
            if (debug):
                rowbiases_converted = [board.dac_calcvout(rowbias) for rowbias in rowbiases]
                print('rowbiases', rowbiases_converted)
                print('asserting event')
                print('ROW enables', board.ROW_EN_tobe)
                print('COL enables', board.COL_EN_tobe)
            #we have an event
            board.event()
        #we then go back to the top and do the maxrows a total of maxcol time. We will get their product of events! 

    return True

def outer_product(board,vwrite_set,vwrite_reset,vgate,row_update,col_update, configure=True):
    """
    This is the more general outerproduct operation. It can use both positive and negative integers. It does this by partitioning the programming operations into 4 outerproduct primitives
    it does this based on the sign. ++, +-, -+, --. Extracted values are written to zero
    """

    #we start by creating 4 lists. we can do this easily using the copy function just to make starting easier
    col_series_pos = col_update.copy() # +columns
    col_series_neg = col_update.copy()  # -columns
    row_series_pos = row_update.copy()   # +rows
    row_series_neg = row_update.copy()    # -rows

    for i in range(len(col_update)):
        if col_update[i]>0: #if a member of the column update is greater than zero
            col_series_pos[i]=col_update[i] #keep it in the positive
            col_series_neg[i]=0 #set it to zero in the negative
        elif col_update[i]<0: #if we are less than zero
            col_series_neg[i]=abs(col_update[i]) #set it to abs value in the negative
            col_series_pos[i]=0 #set it to zero in the positive
        else: # they are probably both zero anyway so 
            col_series_neg[i]=0 #set it to zero
            col_series_pos[i]=0 #set it to zero

    for i in range(len(row_update)):
        if row_update[i]>0: #if a member of the column update is greater than zero
            row_series_pos[i]=row_update[i] #keep it in the positive
            row_series_neg[i]=0 #set it to zero in the negative
        elif row_update[i]<0: #if we are less than zero
            row_series_neg[i]=abs(row_update[i]) #set it to abs value in the negative
            row_series_pos[i]=0 #set it to zero in the positive
        else: #they are probably both zero anyway so 
            row_series_neg[i]=0 #set it to zero
            row_series_pos[i]=0 #set it to zero


    # set/reset voltages seem to be the opposite
    outer_product_primitive(board,vwrite_reset,vgate,col_series_pos,row_series_pos,0, configure) # ++ outerproduct
    outer_product_primitive(board,vwrite_reset,vgate,col_series_neg,row_series_neg,0, False) # -- outerproduct
    outer_product_primitive(board,vwrite_set,vgate,col_series_neg,row_series_pos,1, False) # -+ outerproduct
    outer_product_primitive(board,vwrite_set,vgate,col_series_pos,row_series_neg,1, False)  # +- outerproduct  
    return True


