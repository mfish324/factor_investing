"""
Corporate-action helpers shared by the backtest engine and factor calculators.
"""

import pandas as pd


def flexible_to_datetime(values, errors: str = "coerce"):
    """
    Convert date-like values to datetimes, handling epoch integers correctly.

    pd.to_datetime interprets bare integers as NANOSECONDS since epoch, which
    silently turns epoch-second/millisecond timestamps (as produced by
    DataFrame.to_json round-trips) into ~1970 dates. That failure mode broke
    PointInTimeView truncation for cached financials: every filing looked
    ancient, so nothing was ever truncated (look-ahead). This helper detects
    the epoch unit by magnitude instead.
    """
    ser = values if isinstance(values, pd.Series) else pd.Series(values)
    if pd.api.types.is_numeric_dtype(ser):
        numeric = pd.to_numeric(ser, errors="coerce").abs()
        peak = numeric.max()
        if pd.isna(peak):
            return pd.to_datetime(ser, errors=errors)
        if peak < 1e11:        # epoch seconds (1973-5138)
            unit = "s"
        elif peak < 1e14:      # epoch milliseconds
            unit = "ms"
        elif peak < 1e17:      # epoch microseconds
            unit = "us"
        else:                  # epoch nanoseconds
            unit = "ns"
        return pd.to_datetime(ser, unit=unit, errors=errors)
    return pd.to_datetime(ser, errors=errors)


def cumulative_split_factor(splits: list, since_date) -> float:
    """
    Product of (split_to / split_from) for every split AFTER `since_date`.

    A 1-for-4 split (split_from=1, split_to=4) means one old share became
    four new shares, so the share-count scaling factor is 4.

    Polygon's adjusted prices reflect today's split-adjusted basis. To
    convert as-reported-then quantities to today's basis:
    - share counts: multiply by this factor
    - per-share amounts (EPS, dividend per share): divide by this factor
    """
    if not splits:
        return 1.0
    since_ts = pd.Timestamp(since_date)
    factor = 1.0
    for s in splits:
        try:
            exec_ts = pd.Timestamp(s.get("execution_date"))
        except Exception:
            continue
        if pd.isna(exec_ts) or exec_ts <= since_ts:
            continue
        sf = s.get("split_from")
        st = s.get("split_to")
        try:
            sf = float(sf)
            st = float(st)
        except (TypeError, ValueError):
            continue
        if sf > 0 and st > 0:
            factor *= st / sf
    return factor
