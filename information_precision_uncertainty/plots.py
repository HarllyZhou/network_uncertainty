from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_decomposition(bins: pd.DataFrame, output: str | Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    designs = [
        ("mean_fe2", "E[forecast error² | bin]", "Forecast-error numerator"),
        ("mean_normalized_fe2", "E[forecast error² / volatility² | bin]",
         "Normalized forecast error"),
    ]
    for ax, (column, ylabel, title) in zip(axes, designs):
        y = bins[column]
        lower, upper = bins[f"{column}_lo"], bins[f"{column}_hi"]
        ax.errorbar(
            bins["mean_sigma"], y, yerr=[y - lower, upper - y],
            fmt="o-", capsize=3,
        )
        ax.set(xlabel="Mean ARIMA-residual volatility in bin", ylabel=ylabel, title=title)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_bins(bins: pd.DataFrame, output: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    y = bins["ratio_of_moments"]
    if {"ratio_of_moments_lo", "ratio_of_moments_hi"} <= set(bins):
        yerr = [y - bins["ratio_of_moments_lo"], bins["ratio_of_moments_hi"] - y]
        ax.errorbar(bins["mean_sigma"], y, yerr=yerr, fmt="o-", capsize=3)
    else:
        ax.plot(bins["mean_sigma"], y, "o-")
    ax.axhline(1, color="0.6", lw=1, ls="--")
    ax.set(xlabel="Mean ARIMA-residual volatility in bin",
           ylabel="Var(forecast error) / E[volatility²]",
           title="Normalized forecast-error variance by volatility bin")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_structural_mapping(bins: pd.DataFrame, output: str | Path) -> None:
    valid = bins.dropna(subset=["tau2_model_implied"])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if len(valid) >= 2:
        ax.plot(valid["mean_sigma"], valid["tau2_model_implied"], "o-")
    elif len(valid) == 1:
        ax.scatter(valid["mean_sigma"], valid["tau2_model_implied"])
        ax.text(
            0.5, 0.12,
            f"Only 1 of {len(bins)} bins satisfies 0 <= R < 1; no structural curve is identified.",
            transform=ax.transAxes, ha="center",
        )
    else:
        ax.text(
            0.5, 0.5, "No bin satisfies 0 <= R < 1; mapping unavailable.",
            transform=ax.transAxes, ha="center", va="center",
        )
    ax.set(xlabel="Mean ARIMA-residual volatility in bin",
           ylabel="Model-implied signal-noise variance, tau²",
           title="Gaussian benchmark structural interpretation")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)
