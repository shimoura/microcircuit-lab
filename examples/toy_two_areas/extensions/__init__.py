"""The project's own models and definitions, one folder per simulator.

``brian2/`` holds the definitions for the Brian2 backend, which has no models of
its own (found by :func:`microcircuit_lab.backends.brian2.models.load_models`);
``nest/`` the project's distributions for NEST (found by
:func:`microcircuit_lab.backends.nest.distributions.load_functions`);
``nestml/`` is the place for NESTML models (compiled and installed with
``--nest-modules``).
"""
