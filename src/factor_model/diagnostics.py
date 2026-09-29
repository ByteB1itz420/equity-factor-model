"""Residual diagnostics for fitted factor models."""
from __future__ import annotations

import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox


def jarque_bera(resid: pd.Series) -> dict:
    """Normality test: H0 = residuals are normally distributed."""
    jb, p = stats.jarque_bera(resid)
    return {"stat": float(jb), "pvalue": float(p),
            "skew": float(stats.skew(resid)), "excess_kurtosis": float(stats.kurtosis(resid))}


def ljung_box(resid: pd.Series, lags: int = 12) -> dict:
    """Autocorrelation test: H0 = residuals are uncorrelated up to `lags`."""
    out = acorr_ljungbox(resid, lags=[lags], return_df=True)
    return {"lags": lags, "stat": float(out["lb_stat"].iloc[0]),
            "pvalue": float(out["lb_pvalue"].iloc[0])}
