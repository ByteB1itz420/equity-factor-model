# Multi-Factor Equity Pricing — Project Report

**Ayush Singh** · sample: Jan 2015 - Dec 2023, monthly · universe: 16 US large caps + IWM
Data: Yahoo Finance auto-adjusted closes (retrieval date stamped in `results/provenance.json`),
Kenneth French Data Library (FF5 factors + momentum). One scripted pipeline generates every
number in this report (`experiments/run_analysis.py`); `experiments/audit_snapshot.py`
re-verifies the artifact hashes.

## 1. Question

How much of a stock's monthly return variation is explained by systematic factors
(market, size, value, profitability, investment, momentum), does that structure hold
out of sample, and can factor information support a portfolio decision that survives
transaction costs?

## 2. Methodology

- **Specification.** All regressions use excess returns, R_i − RF. (The original
  notebook's headline FF3 regression used raw returns; that spec error is corrected here.
  The point estimates move little, but the intercept is only interpretable as alpha
  under the excess-return spec.)
- **Inference.** OLS with Newey-West HAC standard errors, lag 6, throughout. Monthly
  equity returns are autocorrelated and heteroskedastic, so plain OLS t-stats overstate
  significance.
- **Multiple testing.** 16 alphas per model are judged jointly with Benjamini-Hochberg
  q-values at q = 0.05, not with 16 independent 5% tests.
- **Diagnostics.** Jarque-Bera (normality) and Ljung-Box(12) (residual autocorrelation);
  36-month rolling market betas for stability.
- **Out-of-sample.** Betas estimated on 2015-2020 (72 months) only; the 2021-2023
  window (36 months) was evaluated once. OOS R² is benchmarked against the train-mean
  predictor, the honest null for a return model.
- **Backtest.** Signal for month t uses total returns through month t−2 only
  (12-1 momentum). Top 5 of 16, equal weight, monthly rebalance, 2021-2023. Net returns
  subtract cost × one-way turnover on a 0/10/25/50 bps grid. Benchmarks: equal-weight
  universe, SPY.

## 3. Factor regressions (full sample, 108 months)

**AAPL, FF3:** beta_MKT 1.29, beta_SMB −0.34, beta_HML −0.49, R² 0.56. The signs say
exactly what AAPL is: high-beta, large, growth. Alpha is +0.85%/mo with BH q = 0.20 -
indistinguishable from zero once testing is done honestly.

**Cross-section:** after BH control, significant alphas (FF3) remain only for
MSFT (+1.08%/mo, q=0.002), NVDA (+3.45%/mo, q=0.034) and IWM (−0.17%/mo, q=0.034).
The IWM case is the teaching point: a passively indexed ETF has R² = 0.99 and a
tiny *negative* alpha that is nonetheless statistically significant - residual variance
is so small that even the fee/tracking drag is detectable. Statistical and economic
significance are different things; the table shows both.

**IWM mechanics:** beta_SMB 0.85, R² 0.99 - a constructed small-cap vehicle loads on the
small-cap factor almost by definition. This is the sanity check that the pipeline is wired
correctly.

**Momentum (FF4):** UMD is insignificant for 14 of 16 names - the expected result for
heavily-followed large caps. The notebook's headline exception, META (beta_UMD −0.60,
plain-OLS p = 0.008), does **not** survive Newey-West inference (HAC p = 0.08). The
point estimate is unchanged; the confidence was overstated. This is the clearest
demonstration in the project that inference method changes conclusions.

**Residuals (AAPL FF3):** Ljung-Box p = 0.70 - no residual autocorrelation, the factor
set is not missing an obvious systematic component. Jarque-Bera p ≈ 1e-4 - residuals
have fat tails (skew −0.49, excess kurtosis 1.75), which is itself an argument for the
HAC standard errors used throughout.

**Rolling beta:** AAPL's 36-month market beta stays in a 1.0-1.5 band - exposure is
persistent but time-varying, which is why a single full-sample beta is a summary, not
a law.

## 4. Out-of-sample validation (train 2015-2020 → test 2021-2023)

| Model | mean train R² | mean OOS R² |
|---|---|---|
| CAPM | 0.44 | 0.35 |
| FF3 | 0.53 | **0.50** |
| FF4 | 0.54 | 0.45 |
| FF5 | 0.57 | **0.52** |

The factor structure generalizes: FF3 keeps 50% explanatory power on data the regression
never saw, versus a train-mean benchmark. Adding UMD *hurts* out of sample (0.50 → 0.45),
consistent with the in-sample insignificance of momentum in this universe - an in-sample
R² gain that does not generalize is overfitting, and it is caught here by design.

## 5. Backtest (2021-2023, strictly out of sample)

Top-5 12-1 momentum tilt vs equal-weight 16 and SPY:

| Series | Total | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| Momentum tilt, gross | +73.9% | 20.3% | 24.1% | 0.80 | −16.6% |
| Momentum tilt, net 10bps | +71.0% | 19.6% | 24.1% | 0.78 | −16.7% |
| Momentum tilt, net 50bps | +59.9% | 16.9% | 24.1% | 0.68 | −17.3% |
| Equal-weight 16 | +69.1% | 19.1% | 19.2% | **0.90** | −23.6% |
| SPY | +32.9% | 9.9% | 17.6% | 0.51 | −23.9% |

Honest reading, in the order an interviewer will probe it:

1. The tilt beat SPY on total return and drawdown, helped by heavy NVDA exposure
   (held 27 of 36 months) through the 2023 run.
2. It did **not** beat the equal-weight universe on risk-adjusted terms
   (Sharpe 0.78 vs 0.90). The tilt concentrated in high-vol names and got paid for it
   in return, not in efficiency.
3. Turnover averages ~5.7×/year, so the edge is cost-fragile: at 50 bps the total
   return gives back 14 points vs gross.
4. The universe is hindsight-selected survivors; every backtest number here is
   optimistic by construction, and 36 months is one regime. No alpha is claimed.

What the backtest actually demonstrates: a strictly no-lookahead signal pipeline,
drift-correct turnover accounting, cost stress-testing, and the discipline to report
a benchmark that beats the strategy.

## 6. Limitations

- Survivorship-biased universe (16 stocks chosen today, evaluated over the past).
- Monthly frequency only; no intraday or execution modeling beyond a linear cost.
- Single test window; no walk-forward re-estimation of the tilt parameters.
- FF factors are US-market constructions; nothing here transfers to other markets
  without re-estimation.

## 7. Reproducibility

`python experiments/run_analysis.py` regenerates every artifact and the site's data
from source. `results/manifest.json` holds sha256 of each frozen artifact;
`experiments/audit_snapshot.py` verifies them. 14 pytest tests cover the math
(closed-form OLS equivalence, BH properties), the no-lookahead invariant, and the
frozen artifacts' integrity. Parameters are frozen in `experiments/protocol.yaml`,
committed before any results artifact.
