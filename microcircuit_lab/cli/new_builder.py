"""
``microcircuit-lab new-builder <name>``: create ``builders/<name>/``, a model
builder with a small example network to edit.

A builder is code that writes a network folder, ``configs/network/<name>/``,
which passes the usual checks when loaded. The new ``main()`` already writes an
example network; change its values to your model's. ``builders/toy_two_areas``
is a readable mid-size example, and ``builders/pd14`` and ``builders/humam`` are
full ones.

Usage: microcircuit-lab new-builder <name>
"""

import keyword
import sys
from pathlib import Path

BUILDERS_DIR = Path("builders")

STUB = '''\
"""{title} model: writes configs/network/{name}/ from the parameters of the model.

main() below builds a small example network to edit. When it grows too large
for one file, move the code into a build.py and keep this __init__.py as a
one-line re-export, like builders/pd14 and builders/humam.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from microcircuit_lab.builder_tools import delay, weight, write_network_directory


def main(argv: list[str] | None = None) -> None:
    """Entry point for `microcircuit-lab generate {name}`.

    The four blocks below are the contents of the files in
    configs/network/{name}/, without the key that opens each file
    (write_network_directory adds it). Replace the example values with this
    model's numbers. Every field, with units and defaults: docs/config_files.md.
    """
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate {name}", description="Generate the {name} network config."
    )
    parser.add_argument("--config-dir", default="configs")
    args = parser.parse_args(argv)

    # populations.yaml: one entry per population. initial_state: each neuron's
    # starting membrane potential (mV), drawn from a normal distribution;
    # background_indegree is optional (default 0.0). All fields: docs/config_files.md.
    initial_state = {"V_m": {"distribution": "normal", "mean": -65.0, "std": 5.0}}
    populations = [
        {"name": "E", "size": 800, "neuron": "lif",
         "initial_state": initial_state, "background_indegree": 1000},
        {"name": "I", "size": 200, "neuron": "lif",
         "initial_state": initial_state, "background_indegree": 1000},
    ]

    # neurons.yaml: neuron name -> NEST model + its parameters. The parameters
    # are NEST's (iaf_psc_exp's here) and are checked by NEST, not by the
    # core. A population refers to a neuron by this name.
    neurons = {
        "lif": {
            "model": "iaf_psc_exp",
            "parameters": {
                "C_m": 250.0, "tau_m": 10.0, "E_L": -65.0,
                "V_th": -50.0, "V_reset": -65.0, "t_ref": 2.0,
                "tau_syn_ex": 0.5, "tau_syn_in": 0.5, "I_e": 0.0,
            },
        },
    }

    # connectivity.yaml: one entry per connection. n_synapses is the total for
    # the connection (indegree * target size). The weight unit is "PSP" (mV,
    # converted to pA), "PSC" (pA) or "native"; delay is in ms. rel_std sets the
    # spread: 0 gives one fixed value, above 0 a normal distribution; pass
    # distribution= for another one.
    connections = [
        {"source": "E", "target": "E", "n_synapses": 64000,
         "weight": weight(0.15, unit="PSP", rel_std=0.1), "delay": delay(1.5, rel_std=0.5)},
        {"source": "E", "target": "I", "n_synapses": 16000,
         "weight": weight(0.15, unit="PSP", rel_std=0.1), "delay": delay(1.5, rel_std=0.5)},
        {"source": "I", "target": "E", "n_synapses": 16000,
         "weight": weight(-0.6, unit="PSP", rel_std=0.1), "delay": delay(0.75, rel_std=0.5)},
        {"source": "I", "target": "I", "n_synapses": 4000,
         "weight": weight(-0.6, unit="PSP", rel_std=0.1), "delay": delay(0.75, rel_std=0.5)},
    ]

    # background_inputs.yaml: population name -> its always-on Poisson input.
    background_inputs = {
        "E": {"rate": 8.0, "weight": weight(0.15, unit="PSP"), "delay": delay(1.5)},
        "I": {"rate": 8.0, "weight": weight(0.15, unit="PSP"), "delay": delay(1.5)},
    }

    write_network_directory(
        Path(args.config_dir) / "network" / "{name}",
        populations=populations,
        neurons=neurons,
        connections=connections,
        background_inputs=background_inputs,
    )
'''


def render_stub(name: str) -> str:
    """The ``__init__.py`` contents for a new builder named ``name``."""
    return STUB.replace("{title}", name.replace("_", " ").title()).replace("{name}", name)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit("Usage: microcircuit-lab new-builder <name>")

    name = argv[0]
    if not name.isidentifier() or keyword.iskeyword(name) or name != name.lower():
        sys.exit(f"{name!r} must be a lowercase Python identifier.")

    package = BUILDERS_DIR / name
    if package.exists():
        sys.exit(f"{package} already exists.")

    package.mkdir(parents=True)
    (package / "__init__.py").write_text(render_stub(name))
    print(f"Created {package / '__init__.py'}")
    print(
        f"It writes an example network as it is; change the values in main() to "
        f"your model's, then run `microcircuit-lab generate {name}`. Add a "
        f"README.md with your model's sources once it settles."
    )

