import numpy as np

def testing_forward(layers, X, y, Gnorm, vread):
    """Function for performing neural network inference.

    Parameters
    ----------
    layers : list[network_layer.Linear]
        A list of Linear layer objects representing a neural network.
    X : list[list[float]]
        Dataset features.
    y : list[float]
        Dataset labels.

    Returns
    ----------
    acc : float
        The classification accuracy of the network represented by `layers` on the `(X, y)` dataset
    """
    vread_forward = vread
    count = 0
    test_sample_num = X.shape[0]
    for j in range(test_sample_num):
        if (j%len(y)//3==0):
            print(f'Sample {j}/{test_sample_num}')
        x = X[j]
        for layer_idx in range(len(layers)):
            x = (x * vread_forward).tolist()
            x = layers[layer_idx].forward_pass(x)
            x = (np.array(x[::2]) - np.array(x[1::2])) # assume differential block mode of mapping in each layer
            x =  x / (Gnorm * vread) + layers[layer_idx].bias
            x = np.tanh(x)

        winner = np.argmax(x)
        winner_truth = np.argmax(y[j])

        if (winner == winner_truth):
            count = count + 1

    acc = count/test_sample_num * 100
    return acc

# Helper functions for binding ADC/DAC/DPOT part classes to corresponding hardware interfaces
def find_device_iio(n):
    directory = '/sys/bus/iio/devices/iio:device' + str(n)
    try:
        with open(directory + '/name') as f:
            f.read()
    except:
        raise Exception("Could not find iio device number {}".format(n))
    return directory

def find_device_spi(n):
    directory = '/sys/bus/spi/devices/spi13.' + str(n)
    try:
        with open(directory + '/modalias') as f:
            f.read()
    except:
        raise Exception("Could not find spi device number {}".format(n))
    return directory