# Architecture

Two views of the same system: the end-to-end analysis pipeline, and the module map.
Both describe the code as it exists in this repository - no aspirational boxes.

## End-to-end pipeline

```mermaid
flowchart LR
    subgraph Ingestion["Data ingestion (src/factor_model/data.py)"]
        YF["Yahoo Finance<br/>monthly adjusted closes<br/>16 tickers, 2014-11..2023-12"]
        KF["Ken French library<br/>FF5 factors + momentum (zip)"]
        AL["Align on monthly PeriodIndex<br/>pct_change, dropna<br/>provenance + sha256"]
        YF --> AL
        KF --> AL
    end

    subgraph Factors["Factor engine (regression.py)"]
        XR["Excess returns<br/>R_i - RF"]
        OLS["OLS per stock x model<br/>CAPM / FF3 / FF4 / FF5<br/>Newey-West HAC(6)"]
        BH["Benjamini-Hochberg<br/>q-values across 16 alphas"]
        DG["Diagnostics (diagnostics.py)<br/>Jarque-Bera, Ljung-Box(12)<br/>36m rolling beta"]
        XR --> OLS --> BH
        OLS --> DG
    end

    subgraph OOS["Out-of-sample evaluation"]
        TR["Train 2015-2020<br/>estimate betas"]
        TE["Test 2021-2023<br/>evaluated once"]
        R2["OOS R2 vs<br/>train-mean benchmark"]
        TR --> TE --> R2
    end

    subgraph BT["Backtest (backtest.py), 2021-2023"]
        SIG["12-1 momentum signal<br/>trailing data only"]
        W["Top-5 equal weight<br/>monthly rebalance"]
        TO["Drift-correct turnover<br/>cost grid 0/10/25/50 bps"]
        BM["Benchmarks<br/>equal-weight 16, SPY"]
        SIG --> W --> TO --> BM
    end

    subgraph Out["Frozen artifacts and products"]
        RES["results/<br/>CSV + JSON, sha256 manifest"]
        AUD["audit_snapshot.py<br/>re-hash and verify"]
        SITE["site/ explorer<br/>Chart.js, reads site/data JSON"]
        VER["Vercel deploy<br/>equity-factor-model.vercel.app"]
        RES --> AUD
        RES --> SITE --> VER
    end

    AL --> XR
    AL --> SIG
    OLS --> TR
    R2 --> RES
    BH --> RES
    DG --> RES
    TO --> RES
```

## Module map

```mermaid
classDiagram
    class data {
        <<module>>
        build_bundle(tickers, start, end, cache)
        load_factors(cache_dir)
        load_prices(tickers, start, end, cache)
        DataBundle: prices, returns, factors, retrieval
    }
    class regression {
        <<module>>
        fit_factor_model(y, factors, names, model, hac_lags)
        excess_returns(returns, rf)
        benjamini_hochberg(pvalues, q)
        rolling_beta(y, x, window)
        MODELS: CAPM, FF3, FF4, FF5
    }
    class diagnostics {
        <<module>>
        jarque_bera(resid)
        ljung_box(resid, lags)
    }
    class backtest {
        <<module>>
        momentum_signal(prices, lookback, skip)
        top_n_weights(signal_row, n)
        run_backtest(returns, signals, months, n, cost_bps)
        performance_stats(monthly, rf)
    }
    class run_analysis {
        <<script, experiments/>
        reads protocol.yaml
        writes results/ + site/data/ + manifest.json
    }
    class audit_snapshot {
        <<script, experiments/>
        verifies manifest sha256
    }
    class explorer {
        <<static site, site/>
        index.html + app.js + styles.css
        fetch site/data/*.json, Chart.js
    }

    run_analysis --> data
    run_analysis --> regression
    run_analysis --> diagnostics
    run_analysis --> backtest
    run_analysis ..> explorer : exports JSON
    audit_snapshot ..> run_analysis : audits outputs
```

## Backtest loop (no-lookahead invariant)

```mermaid
sequenceDiagram
    participant P as Prices (month-end)
    participant S as momentum_signal
    participant B as run_backtest
    participant R as results

    P->>S: closes through month t-2
    S->>B: signal for month t (12-1 momentum, shifted)
    Note over S,B: signal_t uses only data<br/>strictly before month t
    B->>B: drift prior weights by month t returns
    B->>B: turnover = |w_new - w_drift|<br/>net = gross - cost x turnover
    B->>R: monthly gross/net/turnover + holdings
    R->>R: equity curves, stats, cost grid
```
