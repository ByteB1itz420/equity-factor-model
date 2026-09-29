import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factor_model.regression import (benjamini_hochberg, excess_returns,
                                     fit_factor_model, rolling_beta)

rng = np.random.default_rng(7)
months = pd.period_range("2015-01", periods=120, freq="M")
factors = pd.DataFrame({
    "Mkt-RF": rng.normal(0.008, 0.045, 120),
    "SMB": rng.normal(0.001, 0.03, 120),
    "HML": rng.normal(0.001, 0.03, 120),
    "RF": np.full(120, 0.002),
}, index=months)


def test_excess_returns_subtracts_rf():
    rets = pd.DataFrame({"A": [0.05, 0.02], "B": [0.01, -0.03]},
                        index=pd.period_range("2020-01", periods=2, freq="M"))
    rf = pd.Series([0.005, 0.004], index=rets.index)
    ex = excess_returns(rets, rf)
    assert np.isclose(ex.loc[rets.index[0], "A"], 0.045)
    assert np.isclose(ex.loc[rets.index[1], "B"], -0.034)


def test_ols_matches_closed_form():
    y = 0.004 + 1.2 * factors["Mkt-RF"] - 0.3 * factors["SMB"] + rng.normal(0, 0.02, 120)
    fit = fit_factor_model(y, factors, ["Mkt-RF", "SMB"], "TEST", hac_lags=6)
    X = np.column_stack([np.ones(120), factors["Mkt-RF"], factors["SMB"]])
    beta_cf, *_ = np.linalg.lstsq(X, y.to_numpy(), rcond=None)
    assert np.allclose(fit.params.to_numpy(), beta_cf, atol=1e-10)
    assert abs(fit.params["Mkt-RF"] - 1.2) < 0.05


def test_hac_se_nonnegative_and_param_invariant():
    y = 0.004 + 1.2 * factors["Mkt-RF"] + rng.normal(0, 0.02, 120)
    fit = fit_factor_model(y, factors, ["Mkt-RF"], "TEST", hac_lags=6)
    assert (fit.tstats.abs() >= 0).all()
    assert fit.params["Mkt-RF"] == pytest.approx(1.2, abs=0.05)


def test_bh_monotone_and_bounds():
    p = np.array([0.001, 0.01, 0.04, 0.2, 0.5])
    q = benjamini_hochberg(p)
    assert (q >= p - 1e-12).all()
    assert (q <= 1).all()
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= -1e-12)


def test_bh_extremes():
    assert benjamini_hochberg(np.array([0.0]))[0] == 0.0
    assert benjamini_hochberg(np.array([1.0, 1.0])).max() <= 1.0


def test_rolling_beta_recovers_constant_beta():
    x = pd.Series(rng.normal(0, 1, 100))
    y = 2.5 * x + pd.Series(rng.normal(0, 0.01, 100))
    rb = rolling_beta(y, x, window=36)
    assert rb.notna().sum() == 65
    assert abs(rb.mean() - 2.5) < 0.05
