# Contributing

First ask whether the change belongs in the core. Behaviour that only your project needs goes in your project's `builders/` or `analyses/`, which the core finds without edits. Change the core when the fix or feature would help any project.

1. Fork the repository on GitHub and clone your fork.
2. Install it editable: `pip install -e ".[dev]"`. Tests that run a simulation need NEST; see the installation section of [microcircuit_lab/README.md](microcircuit_lab/README.md) for the ways to get it.
3. Create a branch, make the change and add a test for it.
4. Run `ruff check .` and `pytest`. CI runs both.
5. Push the branch to your fork and open a pull request into `main`.

To pull later changes into your fork, add this repository as a remote: `git remote add upstream git@github.com:shimoura/microcircuit-lab.git`.

## Code style

- Docstrings explain what the code does and why; comments are full lines above the code, never at the end of a line.
- Keep it plain and easy to read for someone who is not a software developer: no extra layers, no logic written twice.
- Core tests check the core and how it reads a builder's output. They must not depend on any specific builder.
