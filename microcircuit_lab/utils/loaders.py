from pathlib import Path

import pandas as pd

from microcircuit_lab.utils.io import read_yaml


def load_data(path: str | Path):
    """
    Load structured configuration data.

    Supported formats
    -----------------
    yaml
    parquet
    csv
    """

    path = Path(path)

    suffix = path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        return read_yaml(path)

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(f"Unsupported file format '{suffix}'.")
