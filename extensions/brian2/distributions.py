"""NEST's exponential distribution (nest.random.exponential), for weights,
delays and neuron values: ``{distribution: exponential, beta: 2}`` draws values
with mean ``beta``."""

from microcircuit_lab.backends.brian2.models import Distribution

# 1 - rand() is above 0, so its log is finite.
exponential = Distribution(name="exponential", expression="-beta*log(1 - rand())")
