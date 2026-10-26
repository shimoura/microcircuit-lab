"""The core on a multi-area network whose areas have different layers and cell types.

Uses ``configs/network/toy_two_areas``: area A has L23-L6 with E, PV and SOM
cells, area B has no L4 and adds VIP cells; some neuron entries are shared by
several populations, others are split by layer. Nothing here relies on the
population names meaning E or I: the checks work from the weights and neuron
parameters in the config.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from microcircuit_lab import Simulation
from microcircuit_lab.analysis import list_areas, select_populations
from microcircuit_lab.builder_tools import scale_network
from microcircuit_lab.network.load import assemble_network, read_network_files

NETWORK = "configs/network/toy_two_areas"


def _config(**scaling):
    config = assemble_network(read_network_files(NETWORK))
    if scaling:
        config = scale_network(config, scaled_from="toy_two_areas", **scaling)
    return config


def _mean_input(network) -> dict[str, float]:
    """Mean synaptic input current (pA) of each population of a network:
    sum over inputs of indegree * PSC * source rate * tau_syn, plus I_e.
    Recurrent sources fire at the reference rates; tau_syn is the target's
    tau_syn_ex for a positive PSC and tau_syn_in for a negative one."""
    rates = network.reference.full_mean_rates
    current = {}
    for name, population in network.populations.items():
        parameters = population.neuron.parameters
        background = network.poisson_background[name]
        total = parameters.I_e + 0.001 * parameters.tau_syn_ex * background.weight.mean * background.generator_rate
        current[name] = total

    for connection in network.connections.to_yaml_rows():
        target = network.populations[connection["target"]]
        parameters = target.neuron.parameters
        weight = connection["weight"]["mean"]
        tau = parameters.tau_syn_ex if weight > 0 else parameters.tau_syn_in
        indegree = connection["n_synapses"] / target.size
        current[connection["target"]] += (
            0.001 * tau * indegree * weight * rates[connection["source"]]
        )
    return current


def test_areas_keep_their_own_layers_and_cell_types():
    populations = _config().populations

    assert len(populations) == 24
    assert "A__L4_E" in populations
    assert not any(name.startswith("B__L4_") for name in populations)
    assert [name for name in populations if name.endswith("_VIP")] == [
        "B__L23_VIP",
        "B__L5_VIP",
        "B__L6_VIP",
    ]


def test_area_selection_finds_each_area():
    simulation = SimpleNamespace(network=_config())

    assert list_areas(simulation) == ["A", "B"]
    assert len(select_populations(simulation, None, "A")) == 12
    assert len(select_populations(simulation, None, "B")) == 12


def test_a_single_area_network_has_no_areas():
    simulation = SimpleNamespace(network=assemble_network(read_network_files("configs/network/toy")))

    assert list_areas(simulation) == []


def test_weights_follow_each_target_neuron():
    """A__L23_PV and A__L5_PV use different neuron entries that differ only
    in C_m, so the builder writes the same PSP as currents in the ratio of
    their capacitances."""
    network = _config()
    psc = {
        connection["target"]: connection["weight"]["mean"]
        for connection in network.connections.to_yaml_rows()
        if connection["source"] == "A__L23_E" and connection["target"] in ("A__L23_PV", "A__L5_PV")
    }
    c_m = {name: network.populations[name].neuron.parameters.C_m for name in psc}

    assert c_m["A__L23_PV"] != c_m["A__L5_PV"]
    assert psc["A__L5_PV"] / psc["A__L23_PV"] == pytest.approx(c_m["A__L5_PV"] / c_m["A__L23_PV"])


@pytest.mark.parametrize(
    ("N_scaling", "K_scaling"),
    [(1.0, 0.5), (0.5, 0.5), (0.5, 0.2)],
)
def test_scaling_preserves_the_mean_input_of_every_population(N_scaling, K_scaling):
    full = _mean_input(_config())
    scaled = _mean_input(
        _config(N_scaling=N_scaling, K_scaling=K_scaling)
    )

    names = list(full)
    np.testing.assert_allclose(
        [scaled[name] for name in names], [full[name] for name in names], rtol=0.02
    )


def test_every_population_spikes(tmp_path):
    simulation = Simulation.from_yaml(network_name="toy_two_areas")
    simulation.simulation_config = simulation.simulation_config.model_copy(
        update={
            "t_sim": 300.0,
            "print_time": False,
            "output": simulation.simulation_config.output.model_copy(
                update={"output_dir": tmp_path, "overwrite": True}
            ),
        }
    )
    simulation.run()

    silent = [
        name
        for name in simulation.backend.populations
        if len(simulation.backend.get_spike_events(name)["times"]) == 0
    ]
    assert silent == []
