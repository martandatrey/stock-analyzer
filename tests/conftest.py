import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_prices(n=300, start=100.0, drift=0.001, seed=1, start_date="2025-06-02"):
    rng = np.random.default_rng(seed)
    close = start * np.cumprod(1 + drift + rng.normal(0, 0.01, n))
    idx = pd.bdate_range(start_date, periods=n)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                         "volume": rng.integers(1_000_000, 2_000_000, n).astype(float)}, index=idx)


@pytest.fixture
def prices():
    return make_prices()
