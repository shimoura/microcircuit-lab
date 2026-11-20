# Python API

The functions you call from a script, a builder or an analysis, with their docstrings. Their use, with examples: [Running from a script](scripts.md), [A new network model](new-network.md), [Analysing a run](analysis.md).

On GitHub this page shows only the names; the [documentation site](https://shimoura.github.io/microcircuit-lab/docs/api/) shows the docstrings, which are also in the code and in `help(...)`.

## Run and read

::: microcircuit_lab.Simulation
    options:
      members: [from_yaml, run, output_dir, is_main_process]

::: microcircuit_lab.read_network

::: microcircuit_lab.read_run

## Builder tools

::: microcircuit_lab.builder_tools
    options:
      members: [write_network_directory, write_network, weight, delay, zero_bound, num_synapses_from_conn_prob, psp_to_psc_iaf_psc_exp, psc_to_psp, scale_network, replace_background_by_mean_current, mean_current]

## Analysis

::: microcircuit_lab.analysis
    options:
      members: [compute_population_firing_rates, compute_neuron_firing_rates, compute_population_isi_cv, compute_neuron_isi_cv, compute_power_spectrum, compute_reference_deviation, list_areas, plot_raster, plot_firing_rates, plot_isi_cv, plot_power_spectrum, register_plot]
