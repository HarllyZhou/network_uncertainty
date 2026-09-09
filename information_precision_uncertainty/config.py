from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AnalysisConfig:
    raw_data: Path = Path("information_precision_uncertainty/data/raw/SBU_microdata.dta")
    output_dir: Path = Path("information_precision_uncertainty/outputs")
    criterion: str = "bic"
    max_ar: int = 4
    max_ma: int = 4
    n_jobs: int = 8
    optimizer_maxiter: int = 75
    min_arima_obs: int = 18
    windows: list[int] = field(default_factory=lambda: [6, 9, 12])
    baseline_window: int = 9
    min_rolling_obs: int | None = None
    n_bins: int = 5
    bootstrap_reps: int = 499
    seed: int = 271828
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    max_firms: int | None = None
    reuse_checkpoint: bool = False
    volatility_alignment: str = "target"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AnalysisConfig":
        path = Path(path)
        values = yaml.safe_load(path.read_text()) or {}
        if "raw_data" in values:
            values["raw_data"] = Path(values["raw_data"])
        if "output_dir" in values:
            values["output_dir"] = Path(values["output_dir"])
        cfg = cls(**values)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.criterion not in {"aic", "bic"}:
            raise ValueError("criterion must be 'aic' or 'bic'")
        if self.baseline_window not in self.windows:
            raise ValueError("baseline_window must be included in windows")
        if not 0 <= self.max_ar <= 4 or not 0 <= self.max_ma <= 4:
            raise ValueError("AR and MA orders must lie in [0, 4]")
        if self.n_jobs < 1 or self.optimizer_maxiter < 1:
            raise ValueError("n_jobs and optimizer_maxiter must be positive")
        if not 0 < self.winsor_lower < self.winsor_upper < 1:
            raise ValueError("invalid winsorization quantiles")
        if self.volatility_alignment not in {"origin", "target"}:
            raise ValueError("volatility_alignment must be 'origin' or 'target'")
