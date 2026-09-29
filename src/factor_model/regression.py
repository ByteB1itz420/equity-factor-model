"""Factor regressions with Newey-West (HAC) inference and multiple-testing control."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

MODELS: dict[str, list[str]] = {
    "CAPM": ["Mkt-RF"],
    "FF3": ["Mkt-RF", "SMB", "HML"],
    "FF4": ["Mkt-RF", "SMB", "HML", "UMD"],
    "FF5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
}


@dataclass(frozen=True)
class FactorFit:
    model: str
    params: pd.Series          # const + factor betas (monthly, decimal)
    tstats: pd.Series          # Newey-West t-statistics
    pvalues: pd.Series         # Newey-West p-values
    r2: float
    adj_r2: float
    nobs: int
    fitted: pd.Series
    resid: pd.Series


def fit_factor_model(excess_returns: pd.Series, factors: pd.DataFrame,
                     factor_names: list[str], model: str,
                     hac_lags: int = 6) -> FactorFit:
    """OLS of excess returns on a constant and the given factors, HAC inference."""
    df = pd.concat([excess_returns.rename("y"), factors[factor_names]], axis=1).dropna()
    X = sm.add_constant(df[factor_names])
    res = sm.OLS(df["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    return FactorFit(
        model=model, params=res.params, tstats=res.tvalues, pvalues=res.pvalues,
        r2=float(res.rsquared), adj_r2=float(res.rsquared_adj), nobs=int(res.nobs),
        fitted=res.fittedvalues, resid=res.resid,
    )


def excess_returns(returns: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    """R_i - RF aligned by month; this is the correct left-hand side for CAPM/FF."""
    return returns.sub(rf, axis=0).dropna(how="any")


def benjamini_hochberg(pvalues: np.ndarray, q: float = 0.05) -> np.ndarray:
    """BH-adjusted p-values (q-values)."""
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    # enforce monotonicity from the largest rank down
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(ranked, 0, 1)
    return out


def rolling_beta(y: pd.Series, x: pd.Series, window: int = 36) -> pd.Series:
    """Rolling OLS slope of y on x over `window` months (min_periods=window)."""
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    betas = {}
    xv = df["x"].to_numpy()
    yv = df["y"].to_numpy()
    for i in range(window - 1, len(df)):
        xw = xv[i - window + 1: i + 1]
        yw = yv[i - window + 1: i + 1]
        var = np.var(xw, ddof=1)
        betas[df.index[i]] = np.cov(xw, yw, ddof=1)[0, 1] / var if var > 0 else np.nan
    return pd.Series(betas)
