"""Minimalna algebra liniowa (regresja grzbietowa) bez zaleznosci zewnetrznych."""

from __future__ import annotations

from typing import Sequence


def solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Rozwiazuje uklad rownan metoda eliminacji Gaussa z wyborem elementu."""
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            continue
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for row in range(n):
            if row == col:
                continue
            scale = a[row][col]
            if scale:
                a[row] = [v - scale * w for v, w in zip(a[row], a[col])]
    return [a[i][n] for i in range(n)]


def ridge(
    features: Sequence[Sequence[float]],
    target: Sequence[float],
    weights: Sequence[float] | None = None,
    alpha: float = 1.0,
) -> list[float]:
    """Regresja grzbietowa z wyrazem wolnym na koncu wektora wspolczynnikow.

    Zwraca ``[w_1, ..., w_k, intercept]``. Kara ``alpha`` nie dotyczy wyrazu
    wolnego - przy malej probce (jedna liga, jeden sezon) to ona decyduje
    o stabilnosci wspolczynnikow.
    """
    if not features:
        return []
    k = len(features[0])
    n = len(features)
    w = list(weights) if weights is not None else [1.0] * n

    design = [list(row) + [1.0] for row in features]
    size = k + 1
    xtx = [[0.0] * size for _ in range(size)]
    xty = [0.0] * size
    for row, y, weight in zip(design, target, w):
        if weight <= 0:
            continue
        for i in range(size):
            xty[i] += weight * row[i] * y
            for j in range(size):
                xtx[i][j] += weight * row[i] * row[j]
    for i in range(k):
        xtx[i][i] += alpha
    return solve(xtx, xty)


def predict(coefficients: Sequence[float], row: Sequence[float]) -> float:
    if not coefficients:
        return 0.0
    return sum(c * v for c, v in zip(coefficients, row)) + coefficients[-1]


def standardize(columns: Sequence[Sequence[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    """Centruje i skaluje kolumny; zwraca (dane, srednie, odchylenia)."""
    if not columns:
        return [], [], []
    k = len(columns[0])
    n = len(columns)
    means = [sum(row[i] for row in columns) / n for i in range(k)]
    stds = []
    for i in range(k):
        var = sum((row[i] - means[i]) ** 2 for row in columns) / max(n - 1, 1)
        stds.append(var ** 0.5 or 1.0)
    scaled = [[(row[i] - means[i]) / stds[i] for i in range(k)] for row in columns]
    return scaled, means, stds
