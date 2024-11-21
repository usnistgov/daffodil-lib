import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from daffodillib.utils import testing_forward
from daffodillib.Board import controller
from daffodillib import network_layer

if __name__ == '__main__':

    # General parameters
    sim = True # whether to simulate the experiment using Daffodil_Sim or perform it experimentally on the board using Daffodil_Phys
    plot = True # for plotting the network layers
    
    # Debugging parameters - can be used to force Goff or Gon writes to all weights in place of a pre-trained solution
    force_reset = False
    force_set = False

    # Physical parameters
    vgate=5
    vread=0.1
    vref=1.7 + vread
    vset = 0.8
    vreset = 0.8
    dpot_r = 2*10**3 # or each dpot can be individually tuned based on inverting desired resistance

    # Instantiate the board
    if (sim): 
        board = controller.Daffodil_Sim('Generic')
        board.sim_device.dpot_r = dpot_r
    else: board=controller.Daffodil_Phys()

    board.set_dac_gain_mode(4093)
    board.set_dac_offset(0)

    Ds = board.invert_dpot_rout(dpot_r)
    board.set_dpot_D(Ds)
    board.set_compliance_control(1)
    board.setrefopamp(board.dac_invertvout(abs(vref)))
    
    # Network parameters
    # The pre-trained solutions are for a two layer perceptron network with dimensions 13 x 6 x 3
    layer_dims = [13, 6, 3]    # defining MLP size
    layer1_weight_shape = (layer_dims[0], layer_dims[1] * 2)
    layer2_weight_shape = (layer_dims[1], layer_dims[2] * 2)

    # Layer modes and offsets
    encoding = 'forward' # corresponding to applying voltages on columns and reading currents on rows
    mode = 'block'
    layer1_offsets = [(0, 11, 12)]
    layer2_offsets = [(1, 0, 0)]
    
    # Create network layers
    layer1 = network_layer.Linear(board, shape=[1, 1], weight_shape=layer1_weight_shape, vread=vread, vset=vset, vreset=vreset, vref=vref, vgate=vgate, encoding=encoding, mode=mode, offsets=layer1_offsets)
    layer2 = network_layer.Linear(board, shape=[1, 1], weight_shape=layer2_weight_shape, vread=vread, vset=vset, vreset=vreset, vref=vref, vgate=vgate, encoding=encoding, mode=mode, offsets=layer2_offsets)

    layers = [layer1, layer2]

    # Loading the wine dataset
    task_dir = 'wine'
    X_test = np.loadtxt(f'./{task_dir}/dataset/X_test.txt')
    Y_test = np.loadtxt(f'./{task_dir}/dataset/Y_test.txt')
    X_train = np.loadtxt(f'./{task_dir}/dataset/X_train.txt').T
    Y_train = np.loadtxt(f'./{task_dir}/dataset/Y_train.txt').T

    Gnorms_normalized = [0.5, 1, 1.5]

    # Single Gnorm for all layers
    Goff = board.sim_device.resetG
    Gon = board.sim_device.setG
    Gnorms = [i * (Gon - Goff) / board.sim_device.currentscale for i in Gnorms_normalized]

    results = {'Solution':[], 'Gnorm_normalized':[], 'Gnorm':[], 'Acc':[]}

    for solution in range(3): # a total of 300 pre-trained solutions are provided
        accs = []
        # Load the weights from the provided solutions
        print('\nSolution', solution)
        weight1 = np.loadtxt(f'./{task_dir}/solutions/{solution}_fc1_weight.txt')
        weight2 = np.loadtxt(f'./{task_dir}/solutions/{solution}_fc2_weight.txt')

        bias1 = np.loadtxt(f'./{task_dir}/solutions/{solution}_fc1_bias.txt')
        bias2 = np.loadtxt(f'./{task_dir}/solutions/{solution}_fc2_bias.txt')

        layer1.bias = bias1
        layer2.bias = bias2

        # for debugging            
        if force_reset:
            weight1 = np.zeros_like(weight1)
            weight2 = np.zeros_like(weight2)
        elif force_set:
            weight1 = np.ones_like(weight1)
            weight2 = np.ones_like(weight2)

        # Weight loading - responsible for the outerproduct writes to the underlying array
        layer1.load_weights_outerproduct_parallel(weight1, vgate=vgate)
        layer2.load_weights_outerproduct_parallel(weight2, vgate=vgate)

        # Required, as weight loading may have altered the reference voltage
        board.setrefopamp(board.dac_invertvout(abs(vref)))

        # Plot layers
        if (plot):
            path = Path("./plots/")
            path.mkdir(parents=True, exist_ok=True)

            layer1.plot_weights(vread, vref, slice=False)
            plt.savefig(f'plots/fc1_sim{sim}_solution{solution}.png')
            layer2.plot_weights(vread, vref, slice=True)
            plt.savefig(f'plots/fc2_sim{sim}_solution{solution}.png')

        for Gnorm_idx in range(len(Gnorms)):
            print('\nGnorm:', Gnorms[Gnorm_idx], Gnorms_normalized[Gnorm_idx])
            # Get accuracy estimate
            acc = testing_forward(layers, X_train, Y_train, Gnorms[Gnorm_idx], vread)
            print(f'Network Acc: {acc}')

            results['Solution'].append(solution)
            results['Gnorm_normalized'].append(Gnorms_normalized[Gnorm_idx])
            results['Gnorm'].append(Gnorms[Gnorm_idx])
            results['Acc'].append(acc)

    print(results)
    df = pd.DataFrame.from_dict(results)
    df.to_csv(f'gnorm_opt_summary_{encoding}.csv')