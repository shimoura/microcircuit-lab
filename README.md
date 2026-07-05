# Microcircuit Lab

**Microcircuit Lab** is a flexible Python framework for building, configuring, simulating, and analyzing biologically inspired neural microcircuit models.

The framework is designed for computational neuroscience research, providing reusable infrastructure for implementing published microcircuit models, exploring parameter spaces, and running simulations using different simulator backends.

---

## Features

* Modular architecture for neural microcircuit modeling
* Configuration-driven simulations using YAML files
* Pydantic-based configuration validation
* Flexible network scaling utilities
* Support for multiple reference models
* Extensible backend architecture
* Built-in analysis and visualization tools
* Designed for reproducible computational neuroscience workflows

---

## Project Structure

```text
microcircuit-lab/
├── microcircuit_lab/
│   ├── analysis/
│   ├── backend/
│   ├── builders/
│   ├── config/
│   ├── importers/
│   ├── network/
│   ├── reference_models/
│   ├── simulation/
│   └── utils/
├── examples/
├── tests/
├── docs/
└── pyproject.toml
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/<username>/microcircuit-lab.git
cd microcircuit-lab
```

### Create a Python environment

Create and activate a new environment using Mamba:

```bash
mamba create -n microcircuit-lab python=3.12
mamba activate microcircuit-lab
```

### Install the package

Install Microcircuit Lab in editable mode:

```bash
pip install -e .
```

To install the optional development dependencies:

```bash
pip install -e ".[dev]"
```


## Quick Start

Run a simulation:

```bash
python run.py
```

or from your own scripts:

```python
import microcircuit_lab
```

See the `examples/` directory for complete examples.

---

## Configuration

Microcircuit Lab uses YAML configuration files validated through Pydantic models.

Typical configuration files include:

```text
config/
├── network.yaml
├── simulation.yaml
├── populations.yaml
├── connectivity.yaml
└── scaling.yaml
```

Configurations define:

* neuronal populations
* neuron models
* synaptic connectivity
* external inputs
* scaling parameters
* simulation settings
* output options

---

## Reference Models

Reference implementations are located under

```text
microcircuit_lab/reference_models/
```

Each reference model contains the biological parameters required to reproduce a published network model while remaining independent of the simulation backend.

---

## Backend Architecture

Simulation backends are separated from model definitions.

Current backend:

* NEST

The architecture is designed to support additional simulators in the future.

---

## Analysis

The framework provides tools for analyzing simulation results, including:

* spike activity
* population statistics
* raster plots
* firing rates
* custom analysis pipelines

Additional analyses can be implemented independently of the simulator backend.

---

## Testing

Run the test suite with:

```bash
pytest
```

---

## Roadmap

Planned features include:

* Additional published reference models
* Multiple simulator backends
* Expanded analysis tools
* Improved documentation
* Example notebooks

---

## Contributing

Contributions are welcome through pull requests and issue reports.

Please ensure new code includes tests where appropriate and follows the project's coding style.

---

## License

See the project's LICENSE file for licensing information.
