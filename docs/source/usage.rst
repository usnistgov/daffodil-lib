Getting Started
===============

What is Daffodil?
------------------
Daffodil is a mixed-signal prototyping system developed for the memristive research community to standardize resistive neural network benchmarking.

**Daffodil-lib** is a Python library for the Daffodil prototyping system.


Installation
------------

To use `daffodil-lib`, clone this repository, and install it locally using pip:

.. code-block:: console

   (.env) $ git clone <LINK>

   (.env) $ pip install daffodillib/


Example Code
------------

Navigate to the examples directory.

.. code-block:: console

   (.env) $ python infer_wine.py

This file provides an example implementation for performing fully-connected neural network inference on the Daffodil board. The entire system is simulated end-to-end. 

Software neural network weights are loaded onto simulated crossbars of programmable memory devices and the forward pass operation is emulated. 
A total of 300 ternary weight solutions (2-layer perceptron network) trained to classify the Wine Dataset are provided. Refer to the API for more details.

Contributors
------------

* Osama Yousuf
* Martin Lueker-Boden
* Karthick Ramu
* Mitchell Fream
* Matthew W. Daniels
* Brian Hoskins
* Gina Adam

Papers/Citing
-------------

The following papers describe, and utilize, the Daffodil prototyping system in more detail:

* Hoskins, Brian, et al. "A system for validating resistive neural network prototypes." International Conference on Neuromorphic Systems 2021. `Link <https://dl.acm.org/doi/abs/10.1145/3477145.3477260>`__.
* Yousuf, Osama, et al. "Layer Ensemble Averaging for Improving Memristor-Based Artificial Neural Network Performance." `Link <https://arxiv.org/abs/2404.15621>`__.