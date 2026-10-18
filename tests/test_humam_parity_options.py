"""Options that let a network reproduce the HuMAM model: the synaptic time
constant of inhibitory input in the DC compensation, and what to do with a
weight or delay drawn outside its allowed range."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from microcircuit_lab.backends.nest import NestBackend
from microcircuit_lab.config.network import (
    ConnectionConfig,
    DelayDistribution,
    NetworkConfig,
    NeuronConfig,
    NeuronParams,
    PopulationConfig,
    BackgroundInputConfig,
    ReferenceConfig,
    ScalingConfig,
    WeightDistribution,
)
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.io import delay, validate_network_config, weight, write_network_directory
from microcircuit_lab.network import Network, NetworkPreprocessor

TAU_SYN_EX = 2.0


def _network(
    *,
    tau_syn_in: float,
    background_indegree: float = 0.0,
    connections: list[ConnectionConfig] | None = None,
    scaling: ScalingConfig | None = None,
    reference: ReferenceConfig | None = None,
    bound_mode: str = "redraw",
) -> NetworkConfig:
    neuron = NeuronConfig(
        name="neuron",
        model="iaf_psc_exp",
        parameters=NeuronParams(
            C_m=250.0, tau_m=10.0, tau_syn_ex=TAU_SYN_EX, tau_syn_in=tau_syn_in,
            E_L=-65.0, V_reset=-65.0, V_th=-50.0, t_ref=2.0, I_e=0.0,
        ),
    )
    populations = {
        name: PopulationConfig(
            name=name, size=100, neuron=neuron, V0_mean=-58.0, V0_std=5.0,
            background_indegree=background_indegree,
        )
        for name in ("E", "I")
    }
    return NetworkConfig(
        populations=populations,
        connections=connections or [],
        background_inputs={},
        scaling=scaling or ScalingConfig(),
        reference=reference,
        bound_mode=bound_mode,
    )


def _psc(mean: float, unit: str = "PSC") -> WeightDistribution:
    return WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit=unit)


def _fixed_delay() -> DelayDistribution:
    return DelayDistribution(mean=1.5, rel_std=0.0, distribution="fixed")


# -----------------------------------------------------------------------------
# DC compensation uses the time constant of each kind of input
# -----------------------------------------------------------------------------
def _compensation_into_E(tau_syn_in: float) -> float:
    """The current the compensation adds to population E, in pA. E receives
    1000 excitatory synapses from E and 1000 inhibitory ones from I."""
    config = _network(
        tau_syn_in=tau_syn_in,
        connections=[
            ConnectionConfig(source="E", target="E", n_synapses=1000, weight=_psc(50.0), delay=_fixed_delay()),
            ConnectionConfig(source="I", target="E", n_synapses=1000, weight=_psc(-200.0), delay=_fixed_delay()),
        ],
        scaling=ScalingConfig(K_scaling=0.25),
        reference=ReferenceConfig(full_mean_rates={"E": 4.0, "I": 8.0}),
    )
    config = config.model_copy(
        update={
            "background_inputs": {
                name: BackgroundInputConfig(rate=0.0, weight=_psc(0.0), delay=_fixed_delay())
                for name in ("E", "I")
            }
        }
    )
    derived = NetworkPreprocessor(config).process()
    return derived.populations["E"].neuron.parameters.I_e


def test_compensation_uses_the_inhibitory_time_constant_for_inhibitory_input() -> None:
    tau_syn_in = 4.0
    indegree = 10.0
    excitatory = TAU_SYN_EX * 50.0 * indegree * 4.0
    inhibitory = tau_syn_in * -200.0 * indegree * 8.0
    expected = 0.001 * (1.0 - np.sqrt(0.25)) * (excitatory + inhibitory)

    assert _compensation_into_E(tau_syn_in) == pytest.approx(expected)


def test_compensation_is_unchanged_when_both_time_constants_are_equal() -> None:
    indegree = 10.0
    expected = 0.001 * (1.0 - np.sqrt(0.25)) * TAU_SYN_EX * indegree * (50.0 * 4.0 - 200.0 * 8.0)

    assert _compensation_into_E(TAU_SYN_EX) == pytest.approx(expected)


def test_compensation_sign_rule_also_holds_for_weights_given_as_psp() -> None:
    """A PSP weight keeps its sign when converted to a PSC, so an inhibitory
    PSP is compensated with tau_syn_in just like an inhibitory PSC."""
    from microcircuit_lab.network.synapses import psp_to_psc_iaf_psc_exp

    tau_syn_in = 4.0
    config = _network(
        tau_syn_in=tau_syn_in,
        connections=[
            ConnectionConfig(source="I", target="E", n_synapses=1000, weight=_psc(-0.5, "PSP"), delay=_fixed_delay()),
        ],
        scaling=ScalingConfig(K_scaling=0.25),
        reference=ReferenceConfig(full_mean_rates={"E": 4.0, "I": 8.0}),
    )
    config = config.model_copy(
        update={
            "background_inputs": {
                name: BackgroundInputConfig(rate=0.0, weight=_psc(0.0), delay=_fixed_delay())
                for name in ("E", "I")
            }
        }
    )
    psc = psp_to_psc_iaf_psc_exp(psp=-0.5, C_m=250.0, tau_m=10.0, tau_syn=tau_syn_in)
    expected = 0.001 * (1.0 - np.sqrt(0.25)) * tau_syn_in * psc * 10.0 * 8.0

    derived = NetworkPreprocessor(config).process()

    assert derived.populations["E"].neuron.parameters.I_e == pytest.approx(expected)


def test_background_compensation_uses_the_inhibitory_time_constant_for_inhibitory_input() -> None:
    tau_syn_in = 4.0
    config = _network(
        tau_syn_in=tau_syn_in,
        background_indegree=100.0,
        scaling=ScalingConfig(K_scaling=0.25),
        reference=ReferenceConfig(full_mean_rates={"E": 4.0, "I": 8.0}),
    )
    config = config.model_copy(
        update={
            "background_inputs": {
                "E": BackgroundInputConfig(rate=8.0, weight=_psc(-30.0), delay=_fixed_delay()),
                "I": BackgroundInputConfig(rate=8.0, weight=_psc(30.0), delay=_fixed_delay()),
            }
        }
    )
    expected_E = 0.001 * (1.0 - np.sqrt(0.25)) * tau_syn_in * -30.0 * 100.0 * 8.0
    expected_I = 0.001 * (1.0 - np.sqrt(0.25)) * TAU_SYN_EX * 30.0 * 100.0 * 8.0

    derived = NetworkPreprocessor(config).process()

    assert derived.populations["E"].neuron.parameters.I_e == pytest.approx(expected_E)
    assert derived.populations["I"].neuron.parameters.I_e == pytest.approx(expected_I)


# -----------------------------------------------------------------------------
# bound_mode and the minimum delay in the files
# -----------------------------------------------------------------------------
NEURON = {
    "C_m": 250.0, "tau_m": 10.0, "tau_syn_ex": 0.5, "tau_syn_in": 0.5,
    "E_L": -65.0, "V_reset": -65.0, "V_th": -50.0, "t_ref": 2.0, "I_e": 0.0,
}


def _write(tmp_path: Path, **overrides) -> Path:
    parts = dict(
        path=tmp_path / "net",
        populations=[
            {"name": "E", "size": 8, "neuron": "n", "V0_mean": -65.0, "V0_std": 5.0, "background_indegree": 10},
        ],
        neurons={"n": {"model": "iaf_psc_exp", "parameters": NEURON}},
        connections=[
            {"source": "E", "target": "E", "n_synapses": 20,
             "weight": weight(0.15, unit="PSP", rel_std=0.1),
             "delay": delay(1.5, rel_std=0.5, minimum=0.1)},
        ],
        background_inputs={"E": {"rate": 8.0, "weight": weight(0.15, unit="PSP"), "delay": delay(1.5)}},
    )
    parts.update(overrides)
    write_network_directory(**parts)
    return tmp_path / "net"


def test_bound_mode_and_minimum_delay_round_trip_through_the_files(tmp_path: Path) -> None:
    config = validate_network_config(_write(tmp_path, bound_mode="clip"))

    assert config.bound_mode == "clip"
    assert config.connections[0].delay.minimum == 0.1


def test_bound_mode_defaults_to_redraw_and_is_not_written(tmp_path: Path) -> None:
    network_dir = _write(tmp_path)

    assert validate_network_config(network_dir).bound_mode == "redraw"
    assert "bound_mode" not in (network_dir / "connectivity.yaml").read_text()


def test_a_delay_without_a_minimum_leaves_it_out_of_the_file() -> None:
    assert "minimum" not in delay(1.5, rel_std=0.5)
    assert delay(1.5, rel_std=0.5, minimum=0.1)["minimum"] == 0.1


# -----------------------------------------------------------------------------
# what NEST draws
# -----------------------------------------------------------------------------
def _draw_synapses(bound_mode: str, *, weight_mean: float, minimum: float, rel_std: float = 2.0):
    """Connect E to E with 4000 synapses whose weights and delays are wide
    enough that many draws fall outside their range; return both lists."""
    import nest

    wide_weight = WeightDistribution(mean=weight_mean, rel_std=rel_std, distribution="normal", unit="PSC")
    wide_delay = DelayDistribution(mean=1.0, rel_std=rel_std, distribution="normal", minimum=minimum)
    config = _network(
        tau_syn_in=TAU_SYN_EX,
        connections=[
            ConnectionConfig(source="E", target="E", n_synapses=4000, weight=wide_weight, delay=wide_delay),
        ],
        bound_mode=bound_mode,
    )
    network = Network(NetworkPreprocessor(config).process())
    backend = NestBackend(
        network=network,
        simulation_config=SimulationConfig.model_validate(
            {"t_sim": 10.0, "local_num_threads": 1, "print_time": False, "rng_seed": 7}
        ),
    )
    backend.build()

    excitatory = backend.populations["E"]
    values = nest.GetConnections(excitatory, excitatory).get(["weight", "delay"])
    return np.asarray(values["weight"]), np.asarray(values["delay"])


@pytest.mark.parametrize("weight_mean", [10.0, -10.0])
def test_clip_sets_out_of_range_weights_to_zero_and_redraw_does_not(weight_mean: float) -> None:
    clipped, _ = _draw_synapses("clip", weight_mean=weight_mean, minimum=0.5)
    redrawn, _ = _draw_synapses("redraw", weight_mean=weight_mean, minimum=0.5)

    sign = np.sign(weight_mean)
    assert np.all(clipped * sign >= 0.0)
    assert np.mean(clipped == 0.0) > 0.2
    assert np.all(redrawn * sign > 0.0)


def test_clip_sets_short_delays_to_the_minimum_and_redraw_does_not() -> None:
    _, clipped = _draw_synapses("clip", weight_mean=10.0, minimum=0.5)
    _, redrawn = _draw_synapses("redraw", weight_mean=10.0, minimum=0.5)

    assert np.all(clipped >= 0.5)
    assert np.mean(clipped == 0.5) > 0.3
    assert np.all(redrawn >= 0.5)
    assert np.mean(redrawn == 0.5) < 0.1


def test_clip_leaves_values_inside_their_range_unchanged() -> None:
    weights, delays = _draw_synapses("clip", weight_mean=10.0, minimum=0.5, rel_std=0.05)

    assert np.all(weights > 0.0)
    assert np.mean(weights == 10.0) < 0.01
    assert np.all(delays > 0.5)


@pytest.mark.parametrize("bound_mode", ["clip", "redraw"])
def test_a_minimum_delay_below_half_a_step_is_raised_not_rejected(bound_mode: str) -> None:
    """NEST rounds a delay below half a step to 0 and refuses it."""
    _, delays = _draw_synapses(bound_mode, weight_mean=10.0, minimum=0.01)

    assert np.all(delays >= 0.1)
