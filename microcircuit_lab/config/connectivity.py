"""What ``connectivity.yaml`` may contain: one row per projection.

``WeightDistribution`` and ``DelayDistribution`` are also used by background
inputs and stimuli.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from microcircuit_lab.config.base import FrozenConfig


class WeightDistribution(FrozenConfig):
    """
    Distribution of synaptic weights.

    ``unit`` is required and has no default, so a forgotten field cannot run with
    the wrong conversion. It sets what ``mean`` means:

    - "PSP": amplitude of the post-synaptic potential (mV). ``prepare_network``
      converts it to a current amplitude. This only makes sense for a
      current-based integrate-and-fire neuron with exponential synaptic
      currents; ``network.units.convert_psp_to_psc`` lists the neuron parameters
      it needs.
    - "PSC": amplitude of the post-synaptic current (pA), used as given.
    - "native": used exactly as given, in the unit of the neuron model (for
      example nS for a conductance-based model). Use it when no PSP conversion
      exists for the neuron. Its mean current is unknown, so the scaling
      compensation leaves it out.
    """

    mean: float = Field(
        examples=[0.15],
        description="amplitude, in the unit set by `unit`; a negative weight is inhibitory",
    )
    rel_std: float = Field(ge=0.0, examples=[0.1], description="standard deviation / |mean|")

    # To add a distribution: list it here (and in DelayDistribution below if it
    # applies to delays) and draw it in create_weight_spec /
    # create_delay_parameter (backends/nest_parameters.py).
    distribution: Literal[
        "normal",
        "uniform",
        "lognormal",
        "fixed",
    ] = Field(
        default="normal",
        description="how each weight is drawn, with that mean and standard deviation",
    )

    unit: Literal[
        "PSC",
        "PSP",
        "native",
    ] = Field(
        examples=["PSP"],
        description="PSP: mV, converted to pA; PSC: pA, used as given; native: used as given (e.g. nS)",
    )


class DelayDistribution(FrozenConfig):
    """Distribution describing synaptic delays."""

    mean: float = Field(gt=0.0, examples=[1.5], description="mean delay (ms)")
    rel_std: float = Field(ge=0.0, examples=[0.5], description="standard deviation / mean")
    distribution: Literal["normal", "uniform", "lognormal", "fixed"] = Field(
        default="normal",
        description="how each delay is drawn, with that mean and standard deviation",
    )
    minimum: float | None = Field(
        default=None,
        gt=0.0,
        examples=[0.1],
        description="smallest allowed delay (ms) of a drawn delay, never below half the "
        "simulation step; omit for half the simulation step",
    )


# The field holding the number each connection rule takes.
RULE_NUMBER = {
    "fixed_total_number": "n_synapses",
    "fixed_indegree": "indegree",
    "fixed_outdegree": "outdegree",
    "pairwise_bernoulli": "p",
}


class ConnectionConfig(FrozenConfig):
    """
    Description of one projection between two populations.

    ``rule`` says how the synapses are placed, and takes one number:

    - ``fixed_total_number``: ``n_synapses`` synapses in total;
    - ``fixed_indegree``: ``indegree`` synapses onto each target neuron;
    - ``fixed_outdegree``: ``outdegree`` synapses from each source neuron;
    - ``pairwise_bernoulli``: each source-target pair connected with
      probability ``p``.

    The core computes with the expected number of synapses
    (``network.quantities.expected_synapses``) and scales the given number
    with the network (``network.scaling.scale_rule_number``).
    """

    source: str = Field(examples=["L4_E"], description="source population name")
    target: str = Field(examples=["L23_E"], description="target population name")
    rule: Literal["fixed_total_number", "fixed_indegree", "fixed_outdegree", "pairwise_bernoulli"] = (
        Field(
            default="fixed_total_number",
            description="how the synapses are placed; each rule takes its own number "
            "(n_synapses, indegree, outdegree or p)",
        )
    )
    n_synapses: int | None = Field(
        default=None,
        ge=0,
        examples=[1440000],
        description="fixed_total_number: total number of synapses in the projection",
    )
    indegree: int | None = Field(
        default=None, ge=0, description="fixed_indegree: synapses onto each target neuron"
    )
    outdegree: int | None = Field(
        default=None, ge=0, description="fixed_outdegree: synapses from each source neuron"
    )
    p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="pairwise_bernoulli: probability that a source-target pair is connected",
    )
    allow_autapses: bool | None = Field(
        default=None,
        description="whether a neuron may connect to itself; omit for the simulator's default",
    )
    allow_multapses: bool | None = Field(
        default=None,
        description="whether a pair may have several synapses; omit for the simulator's default",
    )
    synapse: str | None = Field(
        default=None,
        examples=["depressing"],
        description="name of an entry in synapses.yaml; omit for the default synapse",
    )
    weight: WeightDistribution = Field(description="weight of each synapse")
    delay: DelayDistribution = Field(description="delay of each synapse")

    @model_validator(mode="after")
    def _check_number_matches_rule(self) -> ConnectionConfig:
        needed = RULE_NUMBER[self.rule]
        others = [
            name for name in RULE_NUMBER.values() if name != needed and getattr(self, name) is not None
        ]
        if getattr(self, needed) is None or others:
            raise ValueError(
                f"rule {self.rule!r} takes the number {needed!r} and no other"
                + (f"; remove {others}" if others else "")
            )
        return self

    @property
    def number(self) -> int | float:
        """The number the rule takes (``n_synapses``, ``indegree``, ...)."""
        return getattr(self, RULE_NUMBER[self.rule])


class ConnectivityFile(FrozenConfig):
    """``connectivity.yaml``.

    Each row is a :class:`ConnectionConfig`: ``source``/``target`` names, a
    ``rule`` with its number, an optional ``synapse`` and a ``weight`` /
    ``delay`` distribution (above). A pair may have several rows with
    different synapses (e.g. AMPA and NMDA).
    """

    connections: list[ConnectionConfig] = Field(
        description="one entry per (source, target, synapse); leave a pair out rather "
        "than writing n_synapses: 0"
    )
    bound_mode: Literal["redraw", "clip"] = Field(
        default="redraw",
        description="what to do with a drawn weight or delay outside its allowed "
        "range: 'redraw' draws again, 'clip' replaces it by the limit; applies to "
        "all weights and delays of the network, background inputs included",
    )
