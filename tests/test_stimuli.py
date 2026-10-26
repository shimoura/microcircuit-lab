"""Tests for targeted stimulation devices (StimulusConfig)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from microcircuit_lab.backends.nest.simulator import NestBackend
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution
from microcircuit_lab.config.network import NetworkConfig
from microcircuit_lab.config.neurons import NeuronConfig, NeuronParams
from microcircuit_lab.config.populations import PopulationConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import (
    DcStimulusConfig,
    InhomogeneousPoissonStimulusConfig,
    PoissonStimulusConfig,
    StimulusConfig,
)
from microcircuit_lab.network.load import assemble_network, read_network_files


def _neuron(**overrides) -> NeuronConfig:
    params = dict(
        C_m=250.0,
        tau_m=10.0,
        tau_syn_ex=0.5,
        tau_syn_in=0.5,
        E_L=-65.0,
        V_reset=-65.0,
        V_th=-50.0,
        t_ref=2.0,
        I_e=0.0,
    )
    params.update(overrides)
    return NeuronConfig(name="exc", model="iaf_psc_exp", parameters=NeuronParams(**params))


def _population(name: str, neuron: NeuronConfig, size: int = 10) -> PopulationConfig:
    return PopulationConfig(
        name=name,
        size=size,
        neuron=neuron,
        initial_state={"V_m": {"distribution": "normal", "mean": -65.0, "std": 1.0}},
        background_indegree=0.0,
    )


def _weight(mean: float = 100.0, unit: str = "pA") -> WeightDistribution:
    return WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit=unit)


def _delay(mean: float = 1.0) -> DelayDistribution:
    return DelayDistribution(mean=mean, rel_std=0.0, distribution="fixed")


# -----------------------------------------------------------------------------
# StimulusConfig field validation
# -----------------------------------------------------------------------------
def test_dc_without_amplitude_raises():
    with pytest.raises(ValidationError, match="amplitude"):
        DcStimulusConfig(targets=["E"])


def test_poisson_without_rate_raises():
    with pytest.raises(ValidationError, match="rate"):
        PoissonStimulusConfig(targets=["E"], weight=_weight(), delay=_delay())


def test_poisson_without_weight_or_delay_raises():
    with pytest.raises(ValidationError, match="weight"):
        PoissonStimulusConfig(targets=["E"], rate=10.0)


def test_inhomogeneous_poisson_requires_rate_times_and_values():
    with pytest.raises(ValidationError, match="rate_times"):
        InhomogeneousPoissonStimulusConfig(
            targets=["E"],
            weight=_weight(),
            delay=_delay(),
        )


def test_dc_stimulus_needs_no_weight_or_delay():
    stimulus = DcStimulusConfig(targets=["E"], amplitude=100.0)
    assert not hasattr(stimulus, "weight")
    assert not hasattr(stimulus, "delay")


# -----------------------------------------------------------------------------
# NetworkConfig cross-field validation
# -----------------------------------------------------------------------------
def test_stimulus_targeting_unknown_population_raises():
    population = _population("E", _neuron())

    with pytest.raises(ValidationError, match="unknown"):
        NetworkConfig(
            populations={"E": population},
            connections=[],
            background_inputs={},
            stimuli=[DcStimulusConfig(targets=["nonexistent"], amplitude=100.0)],
        )


def test_network_without_stimuli_defaults_to_empty_list():
    population = _population("E", _neuron())
    network = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={},
    )
    assert network.stimuli == []


# -----------------------------------------------------------------------------
# YAML loading (stimuli.yaml is optional, wired through network.yaml manifest)
# -----------------------------------------------------------------------------
def test_loader_reads_stimuli_yaml_when_declared(tmp_path: Path) -> None:
    import shutil

    network_dir = tmp_path / "network"
    shutil.copytree("configs/network/toy", network_dir)

    manifest = yaml.safe_load((network_dir / "network.yaml").read_text())
    manifest["stimuli"] = "stimuli.yaml"
    (network_dir / "network.yaml").write_text(yaml.safe_dump(manifest))

    (network_dir / "stimuli.yaml").write_text(
        yaml.safe_dump(
            {
                "stimuli": [
                    {"type": "dc", "targets": ["E"], "amplitude": 200.0, "start": 50.0}
                ]
            }
        )
    )

    network_files = read_network_files(network_dir)
    config = assemble_network(network_files)

    assert len(config.stimuli) == 1
    assert config.stimuli[0].type == "dc"
    assert config.stimuli[0].amplitude == 200.0


def test_loader_rejects_stimulus_targeting_unknown_population(tmp_path: Path) -> None:
    import shutil

    network_dir = tmp_path / "network"
    shutil.copytree("configs/network/toy", network_dir)

    manifest = yaml.safe_load((network_dir / "network.yaml").read_text())
    manifest["stimuli"] = "stimuli.yaml"
    (network_dir / "network.yaml").write_text(yaml.safe_dump(manifest))

    (network_dir / "stimuli.yaml").write_text(
        yaml.safe_dump(
            {"stimuli": [{"type": "dc", "targets": ["nope"], "amplitude": 200.0}]}
        )
    )

    network_files = read_network_files(network_dir)
    with pytest.raises(ValueError, match="unknown population"):
        assemble_network(network_files)


def test_network_yaml_without_stimuli_key_still_loads() -> None:
    """Existing configs (no `stimuli:` entry in network.yaml) keep working."""

    network_files = read_network_files("configs/network/toy")
    config = assemble_network(network_files)
    assert config.stimuli == []


# -----------------------------------------------------------------------------
# NEST backend: device creation and end-to-end current-pulse behavior
# -----------------------------------------------------------------------------
def _isolated_network(stimuli: list[StimulusConfig]) -> NetworkConfig:
    """A single population with no background input and no recurrent
    connections, so any spiking is attributable only to `stimuli`."""

    population = _population("E", _neuron(), size=5)
    config = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={},
        stimuli=stimuli,
    )
    return config


def test_create_stimuli_builds_correct_nest_models():
    stimuli = [
        DcStimulusConfig(targets=["E"], amplitude=500.0, start=10.0, stop=20.0),
        PoissonStimulusConfig(
            targets=["E"], rate=50.0, weight=_weight(), delay=_delay(),
            start=0.0, stop=30.0,
        ),
        InhomogeneousPoissonStimulusConfig(
            targets=["E"],
            rate_times=[10.0, 20.0],
            rate_values=[50.0, 100.0],
            weight=_weight(),
            delay=_delay(),
        ),
    ]
    network = _isolated_network(stimuli)
    simulation_config = SimulationConfig.model_validate({"t_sim": 5.0, "print_time": False})

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()

    assert len(backend.stimulus_generators) == 3

    dc_stim, dc_device = backend.stimulus_generators[0]
    assert dc_device.get("model") == "dc_generator"
    assert dc_device.get("amplitude") == 500.0
    assert dc_device.get("stop") == 20.0

    poisson_stim, poisson_device = backend.stimulus_generators[1]
    assert poisson_device.get("model") == "poisson_generator"
    assert poisson_device.get("rate") == 50.0

    inhom_stim, inhom_device = backend.stimulus_generators[2]
    assert inhom_device.get("model") == "inhomogeneous_poisson_generator"
    assert list(inhom_device.get("rate_times")) == [10.0, 20.0]
    assert list(inhom_device.get("rate_values")) == [50.0, 100.0]


def test_dc_stimulus_drives_spiking_only_after_start():
    """Regression test for the primary use case: a constant-current pulse
    should be the only thing able to make this otherwise-silent, unconnected
    population spike, and only once the pulse starts."""

    stimuli = [
        DcStimulusConfig(targets=["E"], amplitude=2000.0, start=50.0, stop=150.0)
    ]
    network = _isolated_network(stimuli)
    simulation_config = SimulationConfig.model_validate(
        {"t_sim": 200.0, "print_time": False}
    )

    backend = NestBackend(network=network, simulation_config=simulation_config)
    backend.build()
    backend.simulate()

    events = backend.get_spike_events("E")
    assert len(events["times"]) > 0, "the DC pulse should have made the population spike"
    assert min(events["times"]) >= 50.0, "no spikes should occur before the pulse starts"
