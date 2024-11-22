# daffodil-lib: an API for measurement of resistive device arrays

This repository provides a Python library for interfacing with Daffodil, a flexible-interface platform designed for research and development of two-terminal resistive memory and selector devices. The original design and vision for Daffodil was described in [this paper by Hoskins et al.](https://doi.org/10.1145/3477145.3477260), though it has evolved considerably since then. Daffodil mainly targets 18kb two-terminal analog memory device arrays that resulted from the [Nanotechnology Xccelerator project](https://www.nist.gov/programs-projects/nanotechnology-xccelerator).

The code provided here should be regarded as an **alpha version**. It has been demonstrated to work in a restricted experimental setup, first demonstrated in [a paper by Yousuf et al.](https://doi.org/10.48550/arXiv.2404.15621) who use it to measure and operate a memristive neural network. The current release is intended to provide an initial virtual interface to research groups interested in using a Daffodil system who wish to start developing the appropriate experimental control codes before receiving a Daffodil board.
The core feature provided by this library is the definition of a pure abstract virtual class `Daffodil_Base`, as well as two implementations of this class: `Daffodil_Phys`, and `Daffodil_Sim`. The `Daffodil_Sim` class mimics the behavior of an ideal control board. The `Daffodil_Phys` class operates the physical Daffodil board, which currently exists in a pre-release version. 

Operating `Daffodil_Phys` requires fabricating a printed circuit board according to certain specifications, integrating it as a daughterboard to an FPGA, and creating an interface such as that provided by the [daffodil-fpga](https://github.com/usnistgov/daffodil-fpga) library. Eventually, we plan to support this full-stack setup, but at the moment this option should be regarded as experimental and pre-release. If you are interested acquiring a physical experimental setup for use with the `Daffodil_Base` class, or otherwise would like to contact the developers, you can either submit an issue or email NIST's Alternative Computing Group at [altcomp@nist.gov](mailto:altcomp@nist.gov).


## Dependencies & Installation

This library depends on several other Python libraries, which are listed in `requirements.txt`. The recommended installation method is to create a lightweight virtual environment with the `python -m venv env` command, and then install the dependencies and daffodil-lib using pip. For instance,

```bash
$ python -m venv .env
$ source .env/bin/activate
(.env) $ pip install -r requirements.txt
(.env) $ pip install daffodillib
```

The library can then be imported like any other Python library. The script `examples/infer_wine.py` shows a basic example of using the `Daffodil_Sim` class to emulate the operation of a neural network inference engine based on a memristive device array.

To compile the API documentation, run `make html` from within the `docs` directory. The current API documentation will be hosted online soon.

## Citation

If you use this library, please cite this repository according to the information in `CITATION.cff`.

Depending on your usage, it may also be appropriate to cite the following papers:
 - *A system for validating resistive neural network prototypes* ([doi:10.1145/3477145.3477260](https://doi.org/10.1145/3477145.3477260)), which first proposed the Daffodil platform;
 - *Layer Ensemble Averaging for Improving Memristor-Based Artificial Neural Network Performance* ([doi:10.48550/arXiv.2404.15621](https://doi.org/10.48550/arXiv.2404.15621)), the first published work to utilize a fully-integrated Daffodil system

## Acknowledgements

This library was developed by multiple parties as part of a collaboration between the [National Institute of Standards and Technology (NIST)](https://nist.gov), [The George Washington University (GWU)](https://gwu.edu), and [Western Digital Research](https://www.westerndigital.com/company/innovation/academic-collaborations). This library as a whole is licensed under the BSD-3 license (see LICENSE); however, specific contributions and modifications made by employees of NIST are provided as a public service and are not subject to copyright protection within the United States (see LICENSE-NIST). 

# Contact and Collaboration

Research groups interested in collaborating on this project are encouraged to reach out to either the [Alternative Computing Group](https://www.nist.gov/pml/nanoscale-device-characterization-division/alternative-computing-group) at NIST or to the [Adaptive Devices and Microsystems (ADAM) group](https://adam.seas.gwu.edu) at GWU.

**NIST Contact**:<br>
Dr. Matthew W. Daniels<br>
[matthew.daniels@nist.gov](mailto:matthew.daniels@nist.gov)<br>
Alternative Computing Group<br>
Nanoscale Device Characterization Division<br>
Physical Measurement Laboratory

**GWU Contact**:<br>
Prof. Gina Adam<br>
[GinaAdam@gwu.edu](mailto:GinaAdam@gwu.edu)<br>
Adaptive Devices and Microsystems Group<br>
Department of Electrical and Computer Engineering
