# Momentum Bot (dry run)

Autonomous monthly cross-sectional momentum strategy. Rebuilt from scratch
after an earlier options-selling bot (APEX) lost ~$48k over 5 months on a
structurally negative-expectancy payoff shape (needed an ~80% win rate to
break even, got 52-61%).

## Strategy

- **Universe**: 11 SPDR sector ETFs (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB,
  XLU, XLRE, XLC) -- diversified, liquid, no single-stock/earnings risk, no
  survivorship bias.
- **Signal**: 12-1 month momentum -- trailing 12-month return as of the
  last completed month, skipping the most recent month (short-term
  reversal contamination).
- **Position**: top 3, equal-weighted.
- **Rebalance**: monthly. Not daily, not weekly -- tested both, and more
  frequent checking made results *worse* (whipsaw + reversal effects).

## What was tested and deliberately NOT added

- **A 200-day-SMA trend-timing overlay** on top of the momentum ranking.
  Tested combined vs. momentum alone on 11 sector ETFs, 2012-2026: nearly
  identical CAGR/Sharpe, and the combined version did *worse* in both the
  2020 COVID crash and the 2022 bear market. Momentum's own sector rotation
  already does most of the defensive work a trend filter would add.
- **A reactive intra-month stop-loss** (exit if the basket drops >10%
  before the next scheduled rebalance). Tested: CAGR dropped from 12.31%
  to 10.20%, Sharpe from 0.91 to 0.72, and max drawdown got *worse*
  (-23.26% vs -19.22%). The stop cut losses during the crash, then sat in
  cash and missed the recovery -- a known, named phenomenon in the
  literature ("momentum crashes," Daniel & Moskowitz 2016). Riding through
  the strategy's own volatility is correct behavior here, not negligence.

## Real backtest numbers (11 sector ETFs, ~14.6yr, monthly, 5bps costs)

| | Buy & Hold SPY | This strategy |
|---|---|---|
| CAGR | 14.59% | 13.96% |
| Sharpe | 1.05 | 1.06 |
| Max Drawdown | -23.93% | -15.60% |
| 2022 bear market | -8.19% | +4.73% |

No guarantee this keeps working going forward -- this is a real, tested,
30+-years-of-academic-replication strategy family, not a certainty.

## Status: DRY RUN

`momentum_rebalance.py` computes what the strategy would do and logs it to
`state.json`. **It places no real trades.** Real execution (via a broker)
is a deliberate future decision, gated on this dry run proving itself out.

## Running it

```
pip install -r requirements.txt
python momentum_rebalance.py
```

Idempotent -- safe to run more than once in the same month; it will report
"already rebalanced" and take no further action. Intended to run once a
month via a scheduled cloud routine.

## Operational safety (separate from the strategy itself)

The old system's real lessons weren't really about signal quality -- they
were about broker-truth verification, real-fill tracking, and honest
kill-switches. Those pieces are strategy-agnostic and worth porting over
once this goes live: verify state against the actual broker, never trust
an internal journal alone, and monitor for genuine operational failures
(not reactive stops on the strategy's own normal volatility, which is a
different and counterproductive thing -- see above).
