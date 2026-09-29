import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factor_model import backtest as bt

months = pd.period_range("2018-01", periods=60, freq="M")
tickers = [f"T{i}" for i in range(8)]
rng = np.random.default_rng(3)
prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0.005, 0.05, (61, 8)), axis=0),
                      index=pd.period_range("2017-12", periods=61, freq="M"), columns=tickers)
returns = prices.pct_change().dropna()


def test_signal_uses_only_past_data():
    """Shifting future prices must not change an already-decided signal."""
    sig = bt.momentum_signal(prices)
    m = months[30]
    mutated = prices.copy()
    mutated.loc[mutated.index >= m - 1] *= 5  # corrupt everything from m-1 onward
    sig2 = bt.momentum_signal(mutated)
    assert np.allclose(sig.loc[m].dropna(), sig2.loc[m].dropna())


def test_weights_sum_to_one_and_top_n():
    row = pd.Series({t: i for i, t in enumerate(tickers)})
    w = bt.top_n_weights(row, 3)
    assert w.sum() == 1.0
    assert (w > 0).sum() == 3
    assert set(w[w > 0].index) == {"T7", "T6", "T5"}


def test_zero_cost_equals_gross():
    res = bt.run_backtest(returns, bt.momentum_signal(prices), months[-24:], 5, cost_bps=0)
    assert np.allclose(res["monthly"]["gross"], res["monthly"]["net"])


def test_costs_monotone():
    nets = []
    for bps in [0, 10, 50, 200]:
        res = bt.run_backtest(returns, bt.momentum_signal(prices), months[-24:], 5, float(bps))
        nets.append((1 + res["monthly"]["net"]).prod())
    assert all(a >= b for a, b in zip(nets, nets[1:]))


def test_turnover_bounds():
    res = bt.run_backtest(returns, bt.momentum_signal(prices), months[-24:], 5, 10)
    assert (res["monthly"]["turnover"] >= -1e-12).all()
    assert (res["monthly"]["turnover"] <= 2.0 + 1e-9).all()


def test_performance_stats_shapes():
    s = bt.performance_stats(returns["T0"])
    for k in ["cagr", "ann_vol", "sharpe", "max_drawdown", "hit_rate"]:
        assert k in s
    assert -1 <= s["max_drawdown"] <= 0
    assert 0 <= s["hit_rate"] <= 1
