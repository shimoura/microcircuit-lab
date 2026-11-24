# Tutorials

Six short tutorials, in order. The first four use a terminal and a text editor, which is how the package is used every day; the last two are notebooks, for experiments in Python. All of them share one project folder, made in the first.

| | Tutorial | You learn to | Time |
| :- | :--- | :--- | :--- |
| 1 | [Your first run](1_first_run.md) | make a project, run a network model, find the results | 5 min |
| 2 | [Change a parameter](2_change_a_parameter.md) | change a number of a network model, a setting of the run, the simulator | 5 min |
| 3 | [Your own network model](3_own_network_model.md) | write a network model by hand, in five short YAML files, and read an error | 10 min |
| 4 | [A builder](4_builder.md) | let code write the files from a paper's tables, and change one number | 10 min |
| 5 | [A parameter sweep](5_parameter_sweep.ipynb) (notebook) | run a network model for several values of one number and plot the rates | 5 min |
| 6 | [NEST and Brian2](6_nest_and_brian2.ipynb) (notebook) | run the same files on both simulators and compare | 5 min |

You need the package with NEST ([Installation](../installation.md)). Tutorials 5 and 6 also need Jupyter (`pip install jupyterlab`), and 6 needs Brian2 (`pip install brian2`).

## Reading them

- A box marked **Terminal** is typed in a terminal, in your project folder; a box marked **Output** is what it prints. NEST prints more lines while it works; they are left out.
- A box titled with a file path is that file, as you write it in an editor.
- The notebooks run in your project folder: download one with the button at the top of its page, put it there, and start `jupyter lab` in that folder.
