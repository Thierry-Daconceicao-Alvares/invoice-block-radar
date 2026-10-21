"""The capture chart every method in the project is judged by."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE = "#2457a6"
RED = "#c2462e"
STYLES = [
    dict(color=BLUE, lw=2.6),
    dict(color="#a86a00", lw=1.8),
    dict(color="#a86a00", lw=1.4, ls="-."),
    dict(color="#7d8b99", lw=1.6, ls="--"),
    dict(color="#4f8a6e", lw=1.4, ls="--"),
    dict(color="#b9c2cc", lw=1.4, ls=":"),
]


def gains_points(y: np.ndarray, score: np.ndarray, points: int = 101) -> list[list[float]]:
    """The capture curve as [share checked %, share found %] pairs, for the interface."""
    order = np.argsort(-score, kind="stable")
    found = np.concatenate([[0], np.cumsum(y[order])]) / y.sum()
    shares = np.linspace(0, 1, points)
    idx = np.round(shares * len(y)).astype(int)
    return [[round(float(s) * 100, 1), round(float(found[i]) * 100, 2)] for s, i in zip(shares, idx)]


def capture_chart(
    y: np.ndarray,
    curves: dict[str, np.ndarray],
    target: Path,
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    marker_share: float,
    marker_text: str,
) -> None:
    """Share of positives found when cases are worked riskiest first, per method.
    The first curve is drawn as the main one."""
    fig, ax = plt.subplots(figsize=(7.5, 5), dpi=150)
    shares = np.linspace(0, 1, 201)
    for style, (name, score) in zip(STYLES, curves.items()):
        order = np.argsort(-score, kind="stable")
        found = np.concatenate([[0], np.cumsum(y[order])]) / y.sum()
        idx = np.round(shares * len(y)).astype(int)
        ax.plot(shares * 100, found[idx] * 100, label=name, **style)
    ax.axvline(marker_share * 100, color=RED, lw=1, alpha=0.6)
    ax.text(marker_share * 100 + 1, 5, marker_text, color=RED, fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(target)
    plt.close(fig)
