"""Tests for targeted stimulation devices (StimulusConfig)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from microcircuit_lab.backends.nest import NestBackend
from microcircuit_lab.config.network import (
    DelayDistribution,
    NetworkConfig,
    NeuronConfig,
    NeuronParams,
    PopulationConfig,
    ScalingConfig,
    StimulusConfig,
    WeightDistribution,
)
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.io.config import NetworkConfigLoader
from microcircuit_lab.io.files import read_network_directory
from microcircuit_lab.network import Network, NetworkPreprocessor
from microcircuit_lab.network.synapses import psp_to_psc_iaf_psc_exp


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
        V0_mean=-65.0,
        V0_std=1.0,
        background_indegree=0.0,
    )


def _weight(mean: float = 100.0, unit: str = "PSC") -> WeightDistribution:
    return WeightDistribution(mean=mean, rel_std=0.0, distribution="fixed", unit=unit)


def _delay(mean: float = 1.0) -> DelayDistribution:
    return DelayDistribution(mean=mean, rel_std=0.0, distribution="fixed")


# -----------------------------------------------------------------------------
# StimulusConfig field validation
# -----------------------------------------------------------------------------
def test_dc_without_amplitude_raises():
    with pytest.raises(ValidationError, match="amplitude"):
        StimulusConfig(type="dc", targets=["E"])


def test_poisson_without_rate_raises():
    with pytest.raises(ValidationError, match="rate"):
        StimulusConfig(type="poisson", targets=["E"], weight=_weight(), delay=_delay())


def test_poisson_without_weight_or_delay_raises():
    with pytest.raises(ValidationError, match="weight"):
        StimulusConfig(type="poisson", targets=["E"], rate=10.0)


def test_inhomogeneous_poisson_requires_rate_times_and_values():
    with pytest.raises(ValidationError, match="rate_times"):
        StimulusConfig(
            type="inhomogeneous_poisson",
            targets=["E"],
            weight=_weight(),
            delay=_delay(),
        )


def test_inhomogeneous_poisson_rate_times_must_match_length():
    with pytest.raises(ValidationError, match="same length"):
        StimulusConfig(
            type="inhomogeneous_poisson",
            targets=["E"],
            rate_times=[10.0, 20.0],
            rate_values=[5.0],
            weight=_weight(),
            delay=_delay(),
        )


def test_inhomogeneous_poisson_rate_times_must_be_increasing():
    with pytest.raises(ValidationError, match="increasing"):
        StimulusConfig(
            type="inhomogeneous_poisson",
            targets=["E"],
            rate_times=[20.0, 10.0],
            rate_values=[5.0, 8.0],
            weight=_weight(),
            delay=_delay(),
        )


def test_stop_must_be_after_start():
    with pytest.raises(ValidationError, match="stop"):
        StimulusConfig(type="dc", targets=["E"], amplitude=100.0, start=50.0, stop=10.0)


def test_dc_stimulus_needs_no_weight_or_delay():
    stimulus = StimulusConfig(type="dc", targets=["E"], amplitude=100.0)
    assert stimulus.weight is None
    assert stimulus.delay is None


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
            stimuli=[StimulusConfig(type="dc", targets=["nonexistent"], amplitude=100.0)],
            scaling=ScalingConfig(),
        )


def test_network_without_stimuli_defaults_to_empty_list():
    population = _population("E", _neuron())
    network = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={},
        scaling=ScalingConfig(),
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

    network_files = read_network_directory(network_dir)
    config = NetworkConfigLoader(network_files).build()

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

    network_files = read_network_directory(network_dir)
    with pytest.raises(ValueError, match="Unknown population"):
        NetworkConfigLoader(network_files).build()


def test_network_yaml_without_stimuli_key_still_loads() -> None:
    """Existing configs (no `stimuli:` entry in network.yaml) keep working."""

    network_files = read_network_directory("configs/network/toy")
    config = NetworkConfigLoader(network_files).build()
    assert config.stimuli == []


# -----------------------------------------------------------------------------
# PSP -> PSC conversion (must not silently skip stimulus weights)
# -----------------------------------------------------------------------------
def test_stimulus_psp_weight_is_converted_like_connections():
    network_files = read_network_directory("configs/network/toy")
    config = NetworkConfigLoader(network_files).build()

    stimulus = StimulusConfig(
        type="poisson",
        targets=["E", "I"],
        rate=10.0,
        weight=WeightDistribution(mean=0.15, rel_std=0.0, distribution="fixed", unit="PSP"),
        delay=_delay(),
    )
    config = config.model_copy(update={"stimuli": [stimulus]})

    processed = NetworkPreprocessor(config).process()

    converted = processed.stimuli[0].weight
    assert converted.unit == "PSC"

    e_params = config.populations["E"].neuron.parameters
    expected = psp_to_psc_iaf_psc_exp(
        psp=0.15, C_m=e_params.C_m, tau_m=e_params.tau_m, tau_syn=e_params.tau_syn_ex
    )
    # E and I share identical neuron parameters in the toy network, so both
    # populations convert the same PSP amplitude to the same PSC amplitude.
    assert converted.mean == pytest.approx(expected)


def test_stimulus_psp_weight_raises_when_targets_have_different_neuron_params():
    fast = _population("fast", _neuron(tau_syn_ex=0.5))
    slow = _population("slow", _neuron(tau_syn_ex=2.0))

    stimulus = StimulusConfig(
        type="poisson",
        targets=["fast", "slow"],
        rate=10.0,
        weight=WeightDistribution(mean=0.15, rel_std=0.0, distribution="fixed", unit="PSP"),
        delay=_delay(),
    )

    network = NetworkConfig(
        populations={"fast": fast, "slow": slow},
        connections=[],
        background_inputs={},
        stimuli=[stimulus],
        scaling=ScalingConfig(),
    )

    with pytest.raises(ValueError, match="don't all use the same"):
        NetworkPreprocessor(network).process()


def test_dc_stimulus_has_no_weight_to_convert():
    population = _population("E", _neuron())
    stimulus = StimulusConfig(type="dc", targets=["E"], amplitude=200.0)

    network = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={},
        stimuli=[stimulus],
        scaling=ScalingConfig(),
    )

    processed = NetworkPreprocessor(network).process()
    assert processed.stimuli[0].weight is None


# -----------------------------------------------------------------------------
# NEST backend: device creation and end-to-end current-pulse behavior
# -----------------------------------------------------------------------------
def _isolated_network(stimuli: list[StimulusConfig]) -> Network:
    """A single population with no background input and no recurrent
    connections, so any spiking is attributable only to `stimuli`."""

    population = _population("E", _neuron(), size=5)
    config = NetworkConfig(
        populations={"E": population},
        connections=[],
        background_inputs={},
        stimuli=stimuli,
        scaling=ScalingConfig(),
    )
    return Network(config)


def test_create_stimulus_devices_builds_correct_nest_models():
    stimuli = [
        StimulusConfig(type="dc", targets=["E"], amplitude=500.0, start=10.0, stop=20.0),
        StimulusConfig(
            type="poisson", targets=["E"], rate=50.0, weight=_weight(), delay=_delay(),
            start=0.0, stop=30.0,
        ),
        StimulusConfig(
            type="inhomogeneous_poisson",
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

    assert len(backend.stimulus_devices) == 3

    dc_stim, dc_device = backend.stimulus_devices[0]
    assert dc_device.get("model") == "dc_generator"
    assert dc_device.get("amplitude") == 500.0
    assert dc_device.get("stop") == 20.0

    poisson_stim, poisson_device = backend.stimulus_devices[1]
    assert poisson_device.get("model") == "poisson_generator"
    assert poisson_device.get("rate") == 50.0

    inhom_stim, inhom_device = backend.stimulus_devices[2]
    assert inhom_device.get("model") == "inhomogeneous_poisson_generator"
    assert list(inhom_device.get("rate_times")) == [10.0, 20.0]
    assert list(inhom_device.get("rate_values")) == [50.0, 100.0]


def test_dc_stimulus_drives_spiking_only_after_start():
    """Regression test for the primary use case: a constant-current pulse
    should be the only thing able to make this otherwise-silent, unconnected
    population spike, and only once the pulse starts."""

    stimuli = [
        StimulusConfig(type="dc", targets=["E"], amplitude=2000.0, start=50.0, stop=150.0)
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
