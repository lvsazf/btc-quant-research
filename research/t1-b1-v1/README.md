# Frozen T1 / B1 research integration

Status: research candidates, NOT adopted. No account client, trading, A signal, scheduler, or daemon. Integration version: `T1B1_RESEARCH_V1_PORT_20261016`.

## What is integrated

- Freqtrade native `IStrategy` / `StrategyResolver` signal interfaces: `FrozenT1Research`, `FrozenB1Research`.
- The original frozen rule engine and audited economic simulator are copied byte-for-byte into `reference/`, with SHA-256 checks on import. No official engine or rejected SR-H1 baseline is changed.
- A one-shot historical research entrypoint and a one-shot current public Bitget snapshot entrypoint.
- Historical acceptance compares both native signal streams against the frozen rules over 26,304 H1 rows. The integrated historical economic simulation reproduces the original actual-funded baseline results.

This is NOT certification of the standard Freqtrade order/cost backtester. `confirm_trade_entry` deliberately returns false; calling ordinary Freqtrade backtesting would produce no entries. For economic historical research use `run_research.py historical`, which uses the preserved simulator, not the native order ledger. The placeholder native stoploss is never an executed research risk rule. Both adapters reject live/dry-run modes and require an explicit research marker. Do not launch them through `freqtrade trade`: Freqtrade may initialize exchange/wallet access before strategy guards execute. Only the supplied one-shot CLI is audited as account-free. No claim of equivalence between native exchange execution and research is made.

## Frozen rules and evaluation

The exact protocol is `reference/btc-trend-breakout-20261016/protocol.json`; its original isolation wording describes that historical experiment. This subsequent integration is separately authorized, without changing strategy semantics.

T1 uses a completed UTC daily close versus its 50-day SMA. B1 uses a completed daily close versus the previous 20 complete days' high for entry and previous 10 days' low for exit, excluding the current day. State is retained between events. Complete daily signals are available at the next H1 open. The current native adapter emits desired state, not an incremental trade or a verified holding.

Research capital is 1,000 USDT, 90% entry notional inclusive fees, quantity floored to 0.0001 BTC, no leverage/borrowing/shorts. These hypotheses DO NOT meet the old 20 USDT single-trade loss budget, and that budget is not an overall loss cap. Bitget perpetual funding is charged; this is not spot. Fee assumption 0.0006 per side; baseline adverse spread/slippage 0.0002. Original fixed stress scenarios and diagnostic study remain preserved, not reselected here.

Compare net equity, matched HOLD and CASH, hourly drawdown and recovery, exposure, costs, and robustness. Engineering parity does not demonstrate investment merit. Old history has been viewed and is diagnostic, not blind out-of-sample. Historical evidence is the main evaluation basis; new snapshots check execution/data consistency, not an endless requirement for fresh profitability proof. Do not rebacktest the whole history hourly.

## Commands

Use the repository's existing `.venv/bin/python`. The direct historical/current commands below are for separately authorized research validation only; their new output directories preserve those distinct experiments. They are NOT the hourly task entrypoint. Hourly execution must use `hourly_job.py` as documented in [HOURLY_ENTRY.md](HOURLY_ENTRY.md), with the verified original task ID, scheduled timestamp and stable storage root. Never change directories or round identity to bypass same-round deduplication.

```sh
.venv/bin/python research/t1-b1-v1/run_research.py historical \
  --history-root /workspace/shared/btc-quant-research-20261010 \
  --output /workspace/shared/btc-quant-runs/CHOOSE_NEW_RUN/historical

.venv/bin/python research/t1-b1-v1/run_research.py current \
  --history-root /workspace/shared/btc-quant-research-20261010 \
  --output /workspace/shared/btc-quant-runs/CHOOSE_NEW_RUN/current

.venv/bin/python -m unittest discover -s research/t1-b1-v1/tests -v
```

History input OHLCV hashes must match `historical_inputs.json`; historical funding/mark hashes must match `historical_cost_inputs.json`. Current mode bridges at most 1,000 hours from that anchor, checks contiguous completed H1 bars and mark/funding coverage, then fetches fresh time/ticker after calculations. It rejects data older than 60 seconds, abnormal future time, or crossing the hour boundary during calculation. HTTP/code and raw responses are preserved. It has no account/position knowledge and cannot provide an executable recommendation.

## Historical initial integration acceptance (2026-10-16)

`/workspace/shared/btc-quant-runs/t1b1-integration-20261016/`:
- `tests.log`: 11 tests passed, exit 0.
- `historical/result.json`: completed; historical command exit 0; T1 and B1 each match 26,304 native signal rows.
- Actual-funded baseline window: 2026-07-13 00:00 UTC to 2026-10-10 17:00 UTC exclusive. Final equities: CASH 1000, HOLD 1254.8665542124083, T1 1189.1949575689544, B1 1074.38798335933 USDT. This reproduces earlier results, not new profit evidence.
- `current/raw/time_initial*`: initial time call succeeded. That earlier snapshot did not complete and produced no current result or signal. A later authorized, separate current-authorized-retry run completed successfully; the earlier incomplete-run evidence remains preserved separately.

Known nonblocking warning: original frozen CSV loader produces ResourceWarning about unclosed reads; its source is deliberately preserved. Test harness paths refer to this cloud data installation. This package is a minimal research integration, not a standalone deployed service.

## Historical renewed-authority current acceptance

`current-authorized-retry/result.json` exited 0 at 2026-10-16 05:12:45 UTC (13:12:45 Beijing). Eight public responses were HTTP 200/code 00000. Added 131 complete H1 bars, through 05:00 UTC exclusive; each native signal stream matched 26,435 rows. Final time age 4,976 ms and ticker age 248 ms. T1 desired LONG, B1 desired CASH, research only, not holdings/orders/adoption. This verifies current input and rule execution, not investment effectiveness.

Current hourly wrapper acceptance and limitations are recorded in [HOURLY_ENTRY.md](HOURLY_ENTRY.md). Earlier test counts and direct current runs above describe their historical stages, not the current focused suite or complete external archive/notification acceptance.
