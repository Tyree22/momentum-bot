#!/usr/bin/env python3
"""
momentum_rebalance.py

Autonomous monthly cross-sectional momentum strategy on liquid sector ETFs.

Strategy (real-backtested, see README.md):
  - Universe: 11 SPDR sector ETFs
  - Signal: 12-1 month momentum (trailing 12-month return, skipping the
    most recent month to avoid short-term reversal contamination)
  - Rebalance: monthly, hold top 3 equal-weighted
  - No trend-timing overlay, no per-position stop-loss -- both were tested
    against this exact strategy and found to hurt, not help (see README.md)

Mode: DRY RUN ONLY. This script computes what the strategy WOULD do and
logs it to state.json. It does NOT place any real trades. Real execution
(via a broker) is a deliberate future step, not wired in yet.

Run monthly via a scheduled cloud routine. Idempotent: safe to re-run
within the same month -- it will report "already rebalanced" and take
no further action rather than double-trading.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

UNIVERSE = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"]
TOP_N = 3
LOOKBACK_MONTHS = 12
STATE_FILE = Path(__file__).parent / "state.json"
STARTING_BALANCE = 10_000.0


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "mode": "dry_run",
        "starting_balance": STARTING_BALANCE,
        "current_holdings": {},
        "cash": STARTING_BALANCE,
        "last_rebalance_month": None,
        "history": [],
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def fetch_data():
    end = datetime.now(timezone.utc)
    start = end - pd.Timedelta(days=450)
    data = yf.download(
        UNIVERSE,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )["Close"]
    return data.dropna(how="all")


def compute_ranking(data):
    """Momentum ranking as of the last FULLY COMPLETED month.

    Deliberately excludes the current, still-forming month's partial data --
    this exact bug was caught and fixed while setting up the dry-run
    baseline on 2026-09-23 (a naive resample('ME').last() silently treats
    today's partial month as if it were a real month-end).
    """
    monthly = data.resample("ME").last()
    current_month_period = pd.Timestamp(datetime.now(timezone.utc)).to_period("M")
    monthly = monthly[monthly.index.to_period("M") != current_month_period]
    if len(monthly) < LOOKBACK_MONTHS + 1:
        raise RuntimeError(f"Not enough monthly history: {len(monthly)} < {LOOKBACK_MONTHS + 1}")
    mom = (monthly.iloc[-1] / monthly.iloc[-1 - LOOKBACK_MONTHS] - 1).dropna()
    mom = mom.sort_values(ascending=False)
    formation_month = monthly.index[-1].strftime("%Y-%m")
    return mom, formation_month


def latest_price(data, ticker):
    return float(data[ticker].dropna().iloc[-1])


def compute_portfolio_value(state, data):
    if not state["current_holdings"]:
        return state["cash"]
    total = state["cash"]
    for tk, pos in state["current_holdings"].items():
        try:
            px = latest_price(data, tk)
        except Exception:
            px = pos["entry_price"]
        total += pos["shares"] * px
    return total


def main():
    now = datetime.now(timezone.utc)
    this_month = now.strftime("%Y-%m")
    state = load_state()

    print(f"[MomentumBot] Run at {now.isoformat()} | mode={state['mode']}")

    data = fetch_data()
    ranking, formation_month = compute_ranking(data)

    print(f"\n12-1 Momentum ranking (formation month-end: {formation_month}):")
    for tk, v in ranking.items():
        print(f"  {tk:6s} {v * 100:+7.2f}%")

    top_n = ranking.head(TOP_N).index.tolist()
    print(f"\nTop {TOP_N}: {top_n}")

    if state["last_rebalance_month"] == this_month:
        current_value = compute_portfolio_value(state, data)
        print(
            f"\nAlready rebalanced for {this_month} -- no action. "
            f"Current holdings: {list(state['current_holdings'].keys())}, "
            f"portfolio value: ${current_value:,.2f}"
        )
        return

    portfolio_value = compute_portfolio_value(state, data)
    prices = {tk: latest_price(data, tk) for tk in top_n}

    old_holdings = list(state["current_holdings"].keys())
    new_weight = 1.0 / TOP_N
    new_holdings = {}
    for tk in top_n:
        shares = (portfolio_value * new_weight) / prices[tk]
        new_holdings[tk] = {
            "entry_price": prices[tk],
            "entry_date": now.date().isoformat(),
            "shares": round(shares, 4),
        }

    note = (
        f"Rebalanced {this_month}: {old_holdings or '(none -- initial)'} -> {top_n}. "
        f"Portfolio value at rebalance: ${portfolio_value:,.2f}"
    )
    print(f"\n{note}")

    state["current_holdings"] = new_holdings
    state["cash"] = 0.0
    state["last_rebalance_month"] = this_month
    state["history"].append(
        {
            "date": now.isoformat(),
            "formation_month": formation_month,
            "action": "rebalance",
            "old_holdings": old_holdings,
            "new_holdings": top_n,
            "full_ranking": {k: round(float(v), 4) for k, v in ranking.items()},
            "portfolio_value": round(portfolio_value, 2),
            "note": note,
        }
    )
    save_state(state)
    print("\nState saved.")


if __name__ == "__main__":
    main()
