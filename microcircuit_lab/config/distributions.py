"""Values drawn independently for every neuron of a population.

Used by neuron parameters (``neurons.yaml``) and initial states
(``populations.yaml``): a value there is a number, the same for every neuron,
or a distribution to draw one value per neuron from.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class DrawnValue(BaseModel):
    """
    A value drawn for every neuron from one of the simulator's distributions.

    ``distribution`` names it; the other keys are its arguments, passed as
    given, e.g. ``{distribution: normal, mean: -58, std: 10}`` or
    ``{distribution: exponential, beta: 2}``. The backend looks the name up
    and requires every argument (each backend has its own list, see its
    ``distributions.py``); the simulator checks the values.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    __pydantic_extra__: dict[str, StrictInt | StrictFloat] = Field(init=False)

    distribution: str


PerNeuronValue = StrictInt | StrictFloat | DrawnValue
