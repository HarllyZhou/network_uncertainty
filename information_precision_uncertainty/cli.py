from __future__ import annotations

import argparse

from .config import AnalysisConfig
from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Test whether firm information is less precise in volatile environments.")
    parser.add_argument("--config", default="information_precision_uncertainty/config/sbu_baseline.yaml")
    args = parser.parse_args()
    run(AnalysisConfig.from_yaml(args.config))


if __name__ == "__main__":
    main()

