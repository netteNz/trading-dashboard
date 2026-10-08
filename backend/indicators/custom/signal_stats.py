"""
In-sample scorecard for combo markers: what price did in the N bars after each one.

This is the only indicator module that reads *future* bars, and only to score
markers that already exist. The markers themselves come from combo_signals.py,
which uses trailing data only. Nothing here feeds back into a marker.

The numbers are descriptive, not a backtest: no costs, no position sizing, and
the same bars the rule is shown on. The baseline (`base_up`) is there so a hit
rate can be compared with what any bar in the same window did.
"""
import numpy as np
import pandas as pd
import pandas_ta as ta


def _median(s: pd.Series):
    return None if s.empty else round(float(s.median()), 2)


def score_markers(df: pd.DataFrame, buy: pd.Series, sell: pd.Series,
                  horizon: int = 10, last: int | None = None) -> dict:
    """
    buy / sell: boolean Series on df.index, True on marker bars.
    last: only score markers in the last `last` rows (the displayed window).

    Returns:
        {"horizon": N, "base_up": share of window bars whose close rose N bars later,
         "buy":  {"n", "open", "hit", "median_move_pct", "median_mae_atr"},
         "sell": {...}}
    n counts markers with a full N-bar window after them; open counts the rest.
    hit is the share of n where price moved the marker's way. mae is the worst
    move against the marker within the N bars, in ATR(14) at the marker.
    """
    c, h, l = df["close"], df["high"], df["low"]
    atr = ta.atr(h, l, c, 14)
    fwd = c.shift(-horizon)
    # Lowest low / highest high over bars t+1 … t+horizon.
    fwd_low  = l[::-1].rolling(horizon, min_periods=horizon).min()[::-1].shift(-1)
    fwd_high = h[::-1].rolling(horizon, min_periods=horizon).max()[::-1].shift(-1)

    window = pd.Series(False, index=df.index)
    window.iloc[-last if last else 0:] = True
    complete = fwd.notna()

    def side(mask: pd.Series, sign: int) -> dict:
        mask = mask.fillna(False).astype(bool) & window
        scored = mask & complete
        move = (fwd[scored] / c[scored] - 1) * 100 * sign
        adverse = (c - fwd_low) if sign > 0 else (fwd_high - c)
        mae = (adverse[scored] / atr[scored]).replace([np.inf, -np.inf], np.nan).dropna()
        n = int(scored.sum())
        return {
            "n":               n,
            "open":            int((mask & ~complete).sum()),
            "hit":             round(float((move > 0).mean()), 3) if n else None,
            "median_move_pct": _median(move),
            "median_mae_atr":  _median(mae),
        }

    base = window & complete
    return {
        "horizon": horizon,
        "base_up": round(float((fwd[base] > c[base]).mean()), 3) if base.any() else None,
        "buy":     side(buy, 1),
        "sell":    side(sell, -1),
    }
