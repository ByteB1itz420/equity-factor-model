"""Data loaders: Yahoo monthly adjusted prices and Ken French factor series.

All series are aligned on a monthly PeriodIndex so timestamps can never
silently mismatch (Yahoo stamps monthly bars on the first calendar day,
Ken French rows are YYYYMM).
"""
from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FF5_URL = f"{FF_BASE}/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM_URL = f"{FF_BASE}/F-F_Momentum_Factor_CSV.zip"


@dataclass(frozen=True)
class DataBundle:
    prices: pd.DataFrame        # adjusted close, PeriodIndex[M], one column per ticker
    returns: pd.DataFrame       # simple monthly returns
    factors: pd.DataFrame       # Mkt-RF, SMB, HML, RMW, CMA, RF, UMD (decimal, PeriodIndex[M])
    retrieval: dict             # provenance: urls, retrieval timestamp, sha256 of raw payloads


def _fetch_zip_csv(url: str, cache_dir: Path) -> tuple[pd.DataFrame, dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw = urllib.request.urlretrieve(url, cache_dir / url.rsplit("/", 1)[-1])[0]
    payload = Path(raw).read_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        inner = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        text = z.read(inner).decode("utf-8", errors="replace")
    meta = {"url": url, "sha256": hashlib.sha256(payload).hexdigest()}
    return text, meta


def _parse_french_monthly(text: str) -> pd.DataFrame:
    """Parse a Ken French CSV: keep 6-digit YYYYMM rows, percent -> decimal."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header_idx = next(i for i, ln in enumerate(lines) if ln.startswith(","))
    cols = ["date"] + [c.strip() for c in lines[header_idx].split(",")[1:] if c.strip()]
    rows = []
    for ln in lines[header_idx + 1:]:
        key = ln.split(",")[0].strip()
        if len(key) == 6 and key.isdigit():
            vals = [v.strip() for v in ln.split(",")[1:1 + len(cols) - 1]]
            rows.append([key] + vals)
        elif key and not key[0].isdigit() and rows:
            break
    df = pd.DataFrame(rows, columns=cols)
    df["date"] = pd.PeriodIndex(df["date"], freq="M")
    df = df.set_index("date")
    return df.apply(pd.to_numeric, errors="coerce") / 100.0


def load_factors(cache_dir: Path) -> tuple[pd.DataFrame, dict]:
    ff5_text, ff5_meta = _fetch_zip_csv(FF5_URL, cache_dir)
    mom_text, mom_meta = _fetch_zip_csv(MOM_URL, cache_dir)
    ff5 = _parse_french_monthly(ff5_text)
    mom = _parse_french_monthly(mom_text)
    mom = mom.rename(columns={mom.columns[0]: "UMD"})
    factors = ff5.join(mom[["UMD"]], how="left")
    return factors, {"ff5": ff5_meta, "momentum": mom_meta}


def load_prices(tickers: list[str], start: str, end: str, cache_dir: Path) -> tuple[pd.DataFrame, dict]:
    import yfinance as yf

    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = {}
    raw_hashes = {}
    for t in tickers:
        df = yf.download(t, start=start, end=end, interval="1mo", auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for {t}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df[["Close"]].rename(columns={"Close": t})
        close.index = close.index.to_period("M")
        frames[t] = close
        raw_hashes[t] = hashlib.sha256(df.to_csv().encode()).hexdigest()
        close.to_csv(cache_dir / f"prices_{t}.csv")
    prices = pd.concat(frames.values(), axis=1).dropna()
    return prices, {"source": "yfinance auto_adjust=True interval=1mo",
                    "window": {"start": start, "end": end},
                    "per_ticker_sha256": raw_hashes}


def build_bundle(tickers: list[str], price_start: str, price_end: str,
                 cache_dir: Path) -> DataBundle:
    prices, price_meta = load_prices(tickers, price_start, price_end, cache_dir)
    factors, factor_meta = load_factors(cache_dir)
    returns = prices.pct_change().dropna(how="any")
    # align on the intersection of months
    common = returns.index.intersection(factors.index)
    returns = returns.loc[common]
    factors = factors.loc[common]
    prices = prices.loc[prices.index.intersection(common.union(prices.index))]
    retrieval = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prices": price_meta,
        "factors": factor_meta,
    }
    return DataBundle(prices=prices, returns=returns, factors=factors, retrieval=retrieval)
