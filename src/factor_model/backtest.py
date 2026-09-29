"""Long-only momentum-tilt backtest, strictly out of sample, transaction-cost aware.

Signal for return month t uses only total returns from months t-12 .. t-2
(the standard 12-1 momentum definition): nothing from month t-1 or later.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def momentum_signal(prices: pd.DataFrame, lookback: int = 12, skip: int = 1) -> pd.DataFrame:
    """12-1 momentum: price(t-1-skip) / price(t-lookback-skip) - 1, per month t.

    Row t is fully computable from prices observed strictly before month t.
    """
    sig = prices.shift(skip) / prices.shift(lookback + skip) - 1.0
    sig.index = sig.index + 1  # signal decided with data through t-1 applies to month t+1
    return sig


def top_n_weights(signal_row: pd.Series, n: int) -> pd.Series:
    valid = signal_row.dropna()
    w = pd.Series(0.0, index=signal_row.index)
    if len(valid) >= n:
        w[valid.nlargest(n).index] = 1.0 / n
    return w


def run_backtest(returns: pd.DataFrame, signals: pd.DataFrame, months,
                 n_positions: int = 5, cost_bps: float = 10.0) -> dict:
    """Monthly rebalance to top-`n_positions` equal weight, costs on one-way turnover."""
    cost = cost_bps / 1e4
    idx = [m for m in months if m in returns.index]
    w_prev = pd.Series(0.0, index=returns.columns)
    gross, net, turnover, holdings = [], [], [], []
    for m in idx:
        r = returns.loc[m].fillna(0.0)
        drift = w_prev * (1 + r)
        w_drift = drift / drift.sum() if drift.sum() > 0 else w_prev
        w_new = top_n_weights(signals.loc[m], n_positions) if m in signals.index else w_drift
        to = float((w_new - w_drift).abs().sum())
        g = float((w_new * r).sum())
        gross.append(g)
        net.append(g - cost * to)
        turnover.append(to)
        holdings.append(list(w_new[w_new > 0].index))
        w_prev = w_new
    frame = pd.DataFrame({"gross": gross, "net": net, "turnover": turnover}, index=idx)
    return {"monthly": frame, "holdings": holdings}


def equity_curve(monthly_returns: pd.Series) -> pd.Series:
    return (1 + monthly_returns).cumprod()


def performance_stats(monthly_returns: pd.Series, rf: pd.Series | None = None) -> dict:
    n = len(monthly_returns)
    total = float((1 + monthly_returns).prod())
    cagr = total ** (12 / n) - 1
    vol = float(monthly_returns.std(ddof=1) * np.sqrt(12))
    if rf is not None:
        excess = monthly_returns - rf.reindex(monthly_returns.index).fillna(0.0)
    else:
        excess = monthly_returns
    sharpe = float(excess.mean() / monthly_returns.std(ddof=1) * np.sqrt(12)) if monthly_returns.std(ddof=1) > 0 else float("nan")
    curve = equity_curve(monthly_returns)
    dd = curve / curve.cummax() - 1
    return {"months": n, "total_return": total - 1, "cagr": float(cagr),
            "ann_vol": vol, "sharpe": sharpe, "max_drawdown": float(dd.min()),
            "hit_rate": float((monthly_returns > 0).mean())}
