from __future__ import annotations

import ast
from dataclasses import dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "financial_uncertainty": "<FILL_IN>",
        "factset_revere": "<FILL_IN>",
        "factset_supply_chain": "<FILL_IN>",
        "capital_iq_supply_chain": "<FILL_IN>",
    },
    "wrds": {
        "fundamentals_library_candidates": ["comp", "comp_na_daily_all", "comp_na_annual_all"],
        "fundamentals_table_candidates": ["funda"],
        "customer_segment_library_candidates": ["comp", "compseg", "comp_segments", "wrdsapps"],
        "customer_segment_keywords": ["customer", "cust", "segment", "segments", "supply", "supplier"],
    },
    "pipeline": {
        "start_year": None,
        "end_year": None,
        "financial_uncertainty_value_column": None,
        "compute_expensive_network_metrics": True,
        "run_diagnostic_regressions": True,
        "write_csv": True,
        "write_parquet": True,
    },
}


@dataclass(frozen=True)
class OutputPaths:
    raw: Path = PROJECT_ROOT / "data" / "raw"
    interim: Path = PROJECT_ROOT / "data" / "interim"
    processed: Path = PROJECT_ROOT / "data" / "processed"
    tables: Path = PROJECT_ROOT / "data" / "output" / "tables"
    regressions: Path = PROJECT_ROOT / "data" / "output" / "regression_checks"
    logs: Path = PROJECT_ROOT / "data" / "logs"

    def ensure(self) -> None:
        for path in (self.raw, self.interim, self.processed, self.tables, self.regressions, self.logs):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class PipelineConfig:
    values: dict[str, Any] = field(default_factory=lambda: deepcopy(DEFAULT_CONFIG))
    outputs: OutputPaths = field(default_factory=OutputPaths)

    @property
    def fu_path(self) -> Path | None:
        raw = self.values["paths"].get("financial_uncertainty")
        if not raw or raw == "<FILL_IN>":
            return None
        path = Path(raw).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def optional_network_paths(self) -> dict[str, Path]:
        paths = {}
        for key in ("factset_revere", "factset_supply_chain", "capital_iq_supply_chain"):
            raw = self.values["paths"].get(key)
            if raw and raw != "<FILL_IN>":
                path = Path(raw).expanduser()
                paths[key] = path if path.is_absolute() else PROJECT_ROOT / path
        return paths

    @property
    def start_year(self) -> int | None:
        value = self.values["pipeline"].get("start_year")
        return int(value) if value not in (None, "") else None

    @property
    def end_year(self) -> int | None:
        value = self.values["pipeline"].get("end_year")
        return int(value) if value not in (None, "") else None

    @property
    def run_diagnostic_regressions(self) -> bool:
        return bool(self.values["pipeline"].get("run_diagnostic_regressions", True))

    @property
    def financial_uncertainty_value_column(self) -> str | None:
        value = self.values["pipeline"].get("financial_uncertainty_value_column")
        return str(value) if value not in (None, "") else None

    @property
    def compute_expensive_network_metrics(self) -> bool:
        return bool(self.values["pipeline"].get("compute_expensive_network_metrics", True))

    @property
    def write_csv(self) -> bool:
        return bool(self.values["pipeline"].get("write_csv", True))

    @property
    def write_parquet(self) -> bool:
        return bool(self.values["pipeline"].get("write_parquet", True))


def _deep_update(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None = None) -> PipelineConfig:
    config_path = Path(path) if path else PROJECT_ROOT / "config" / "pipeline_config.yaml"
    values = deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        loaded = _load_yaml_like_config(config_path)
        values = _deep_update(DEFAULT_CONFIG, loaded)
    return PipelineConfig(values=values)


def _load_yaml_like_config(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return _load_simple_config(path)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_simple_config(path: Path) -> dict[str, Any]:
    """Small fallback parser for this repo's flat two-level YAML template."""
    parsed: dict[str, Any] = {}
    current_section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            parsed[current_section] = {}
            continue
        if current_section is None or ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        parsed[current_section][key.strip()] = _parse_simple_value(value.strip())
    return parsed


def _parse_simple_value(value: str) -> Any:
    if value == "":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
