"""What ``synapses.yaml`` may contain: one entry per synapse type, by name.

A connection, background input or stimulus names its synapse
(``synapse: nmda``); the entry holds the simulator's synapse model, its
parameters and the receptor port it reaches. Without ``synapse:``, the
simulator's default synapse is used, on the default receptor port.
"""

from __future__ import annotations

from pydantic import Field, StrictBool, StrictFloat, StrictInt

from microcircuit_lab.config.base import FrozenConfig


class SynapseEntry(FrozenConfig):
    """
    One entry of ``synapses.yaml`` (the file key is the synapse's name).

    Weight and delay are not set here: each connection draws its own.
    With a plastic model, the weights the core converts (``unit: PSP``) and
    compensates (scaling) are the initial ones.
    """

    model: str = Field(
        examples=["tsodyks2_synapse"],
        description="the simulator's synapse model name, e.g. static_synapse or stdp_synapse",
    )
    parameters: dict[str, StrictInt | StrictFloat | StrictBool] = Field(
        default_factory=dict,
        examples=[{"U": 0.5, "tau_rec": 800.0}],
        description="parameters passed to that model as-is; the backend validates them",
    )
    receptor_port: int | None = Field(
        default=None,
        ge=1,
        examples=[1],
        description="receptor port of the target neuron (e.g. 1 for AMPA in a multisynapse "
        "model); omit for the default port (0). PSP weights and the scaling compensation are "
        "only computed for the default port",
    )


class SynapsesFile(FrozenConfig):
    """``synapses.yaml`` (optional; only read when ``network.yaml`` names it)."""

    synapses: dict[str, SynapseEntry] = Field(
        default_factory=dict,
        description="one entry per synapse, keyed by any name; connections, background "
        "inputs and stimuli refer to it by that name",
    )
