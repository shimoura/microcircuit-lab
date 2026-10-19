"""Create builders/<name>/ with a runnable main() example.

A builder is any code whose output is a directory under
configs/network/<name>/ that passes microcircuit_lab.network.load.load_network.
This makes the package that `microcircuit-lab generate` discovers, with a
main() that already builds and writes a small example network -- edit the
payload values to match your model (see builders/pd14/
for a minimal real one, .../humam/ for a full one).

Usage: microcircuit-lab new-builder <name>
"""

import keyword
import sys
from pathlib import Path

BUILDERS_DIR = Path("builders")

STUB = '''\
"""{title} model -- writes configs/network/{name}/ from this model's parameters.

main() below builds a small example network to edit. When it outgrows one
file, move the logic into a build.py and keep this __init__.py a one-line
re-export, like builders/pd14 and .../humam.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from microcircuit_lab.builder_tools import delay, weight, write_network_directory


def main(argv: list[str] | None = None) -> None:
    """Entry point for `microcircuit-lab generate {name}`.

    The four payloads below are the configs/network/{name}/ files with their
    top-level wrapper key removed (write_network_directory adds it back) --
    replace the example values with this model's numbers. Full field list,
    types and which are required: the modules in microcircuit_lab/config/.
    """
    parser = argparse.ArgumentParser(
        prog="microcircuit-lab generate {name}", description="Generate the {name} network config."
    )
    parser.add_argument("--config-dir", default="configs")
    args = parser.parse_args(argv)

    # populations.yaml: one dict per population. V0_mean / V0_std are the
    # mean and spread of the initial membrane potential (mV);
    # background_indegree is optional (default 0.0).
    populations = [
        {"name": "E", "size": 800, "neuron": "lif",
         "V0_mean": -65.0, "V0_std": 5.0, "background_indegree": 1000},
        {"name": "I", "size": 200, "neuron": "lif",
         "V0_mean": -65.0, "V0_std": 5.0, "background_indegree": 1000},
    ]

    # neurons.yaml: neuron name -> simulator model + its parameters. The
    # parameter keys are the backend's (iaf_psc_exp's here); this layer
    # does not check them. populations refer to a neuron by its name.
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

    # connectivity.yaml: one dict per projection. n_synapses is the
    # projection total (indegree * target size). weight unit is "PSP" (mV,
    # converted), "PSC" (pA) or "native"; delay is in ms. Both infer a
    # fixed vs normal spread from rel_std -- pass distribution= for others.
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

    # background_inputs.yaml: population name -> always-on external drive.
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
        f"It writes an example network as-is; edit the payloads in main() to match "
        f"your model, then `microcircuit-lab generate {name}`. Add a README.md and "
        f"tests/test_{name}.py once the builder settles."
    )

