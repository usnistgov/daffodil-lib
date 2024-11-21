API
===

The Daffodil API is designed to create an accurate stateful class of the operation of the Daffodil board as interacted with by an application.
Consequently, it should be possible to replace the Daffodil class with the actual Daffodil board without nescessarilly changing the written applications too much.

To accomplish this, the Daffodil API:

- Sets the correct state representation for all the Daffodil TTL signals for a desired configuration
- Communicates with the applications using only the ADC and DAC register values
- Provides warnings or throws errors if the application goes outside an approximate physical bound
- Provides a realistic model of the configuration and the outcome of specific operations e.g., if the gates are not biased in a 2T1R array you will get no output

This allows the Daffodil API to be used for two things:

- Writing first pass code of applications for the in development Daffodil board
- serve as a guide for the Daffodil board driver programming

The API has a few weaknesses. For now, the `event()` operation has no sense of timing or clocking. This is very important. 

.. autoclass:: daffodillib.Board.controller.Daffodil_Base
    :members:

.. autoclass:: daffodillib.Board.controller.Daffodil_Sim
    :members:

.. autoclass:: daffodillib.Board.controller.Daffodil_Phys
    :members:

.. autoclass:: daffodillib.network_layer.Linear
    :members:

.. automodule:: daffodillib.utils
    :members:

.. The following can be added - make sure to add numpy style docstrings to helper methods though
.. .. automodule:: daffodillib.read_array
..     :members:

.. .. automodule:: daffodillib.outerproduct
..     :members:

.. .. automodule:: daffodillib.IVcurve
..     :members:
..     :exclude-members: __init__
