"""Values drawn independently for every neuron of a population.

Used by neuron parameters (``neurons.yaml``) and initial states
(``populations.yaml``): a value there is a number, the same for every neuron,
or drawn for every neuron, written as a drawn weight or delay is
(``config/connectivity.py``), with the same names and bounds:
``{distribution: normal, mean: -58, std: 10}``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, StrictFloat, StrictInt

from microcircuit_lab.config.connectivity import BoundMode, DrawnValue


class DrawnNeuronValue(DrawnValue):
    """
    A value drawn for every neuron from a ``distribution``: normal or
    lognormal, with ``mean`` and ``std``; uniform, with ``min`` and ``max``;
    or another name, which the simulator looks up (its own, e.g. NEST's
    ``exponential``, or the project's), with its arguments as keys of their
    own (``{distribution: exponential, beta: 2}``). Optional bounds, as for
    a weight.
    """

    kind: ClassVar[str] = "neuron"

    distribution: str = Field(
        examples=["normal"],
        description="how each neuron's value is drawn: normal or lognormal, with mean and std; uniform, "
        "with min and max; or another name, which the simulator looks up (its own, e.g. NEST's "
        "exponential, or the project's), with its arguments as keys of their own (e.g. beta: 2)",
    )
    mean: float | None = Field(default=None, examples=[-58.0], description="mean of the drawn values (normal, lognormal)")
    std: float | None = Field(
        default=None, ge=0.0, examples=[10.0], description="standard deviation of the drawn values (normal, lognormal)"
    )
    min: float | None = Field(default=None, description="smallest value a uniform draw gives")
    max: float | None = Field(default=None, description="largest value a uniform draw gives")
    lower_bound: float | None = Field(default=None, description="smallest allowed drawn value; omit for none")
    upper_bound: float | None = Field(default=None, description="largest allowed drawn value; omit for none")
    bound_mode: BoundMode | None = Field(
        default=None,
        description="with a bound: what to do with a drawn value past it: redraw draws it again, clip sets it "
        "to the bound",
    )


PerNeuronValue = StrictInt | StrictFloat | DrawnNeuronValue
