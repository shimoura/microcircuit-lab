#!/usr/bin/env bash
set -euo pipefail

# Create python venv
python -m venv .venv
source .venv/bin/activate

# Install NEST from source; NEST_WITH_MPI=ON for several MPI processes
NEST_VERSION="${NEST_VERSION:-v3.10}"
NEST_WITH_MPI="${NEST_WITH_MPI:-OFF}"

git clone https://github.com/nest/nest-simulator.git --single-branch --branch "$NEST_VERSION" --depth 1
pip install -r nest-simulator/requirements_pynest.txt

mkdir build_dir
cd build_dir

cmake -Dwith-ltdl=ON \
      -Dwith-mpi="$NEST_WITH_MPI" \
      -Dwith-boost=ON \
      ../nest-simulator

make -j"$(nproc)"
make -j"$(nproc)" install

cd ../
rm -rf nest-simulator build_dir

# Install microcircuit_lab
pip install -e ".[dev,nestml]"
