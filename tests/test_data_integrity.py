"""Integrity checks over the frozen artifacts (run after experiments/run_analysis.py)."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


@pytest.mark.skipif(not (RESULTS / "manifest.json").exists(), reason="results not generated")
def test_manifest_hashes_match():
    manifest = json.loads((RESULTS / "manifest.json").read_text())
    for name, digest in manifest.items():
        actual = hashlib.sha256((RESULTS / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name} changed since the frozen run"


@pytest.mark.skipif(not (RESULTS / "factor_loadings.csv").exists(), reason="results not generated")
def test_frozen_loadings_shape_and_sanity():
    ld = pd.read_csv(RESULTS / "factor_loadings.csv")
    assert set(ld["model"]) == {"CAPM", "FF3", "FF4", "FF5"}
    assert ld["ticker"].nunique() == 16
    assert len(ld) == 64
    assert (ld["nobs"] == 108).all()
    iwm = ld[(ld["ticker"] == "IWM") & (ld["model"] == "FF3")].iloc[0]
    assert iwm["r2"] > 0.95  # passive ETF: factors must explain nearly everything
