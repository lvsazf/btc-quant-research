## Current approved ST research extension — 2026-10-19

The sole hourly_job entry now also emits independent ST-H1-LO-v1 research signals and a continuous cost ledger. User approval Sentinel_e1f6c3f614f08191b1a16f4057fb41f9 authorizes research tracking, not economic validation, account trades or hosted stops. Current lock is T1B1_ST_RESEARCH_RUNTIME_V1_20261019, explicitly derived from the approved mark-corrected V3 manifest. T1/B1 native signal and economic rules are unchanged.

ST parameters and independent risk sizing are frozen in st_protocol.json. Its source is independent research, not Freqtrade native order/cost certification. First integration emits INITIALIZED with a reconstructed research target; never present prior historical entries as a new real-time buy. Later rounds include actual new research orders, potentially multiple transitions across a gap. WAIT means a maintained research target, not no calculation. Only after a COMPLETE state may results be presented. No hypothetical research fill is an actual account fill.

st_checkpoint.json persists a cumulative ledger from2026-07-13 UTC, no daily restart or terminal liquidation. At the current hour boundary only the open is used; unclosed high/low/close cannot trigger a stop. Stops are reconstructed from closed H1 bars in later observations and are never hosted. Hash-verified prior COMPLETE checkpoints and unchanged historical input prefixes are required; missing or revised evidence fails closed. Day contributions use continuous hourly curve differences. ST signal replay and receipt cashflow checks are separate from a second economic-path replay, which is not yet implemented.

# Fixed research runtime and restoration

The authoritative lock is `runtime_manifest.json`. Its file hashes cover all research Python/JSON except the lock itself (no self-referential hash). Git commit identity identifies the recorded lock revision; every run prints the lock SHA-256, actual HEAD, worktree status and loaded module paths. A dirty unrelated worktree is reported, not silently called clean. The original repository source base is retained separately from the eventual integration commit. V3 records Freqtrade import path, package version, source ancestry and worktree status; it does not hash-freeze the full native Freqtrade implementation or certify an entire environment image. Native source changes are not an additional V3 hard gate.

Before any research run:

```sh
/workspace/shared/btc-quant-worktree/.venv/bin/python /workspace/shared/btc-quant-worktree/research/t1-b1-v1/runtime_guard.py
```

Expected status is VERIFIED_RESEARCH_ONLY. Both historical and current CLI modes run this preflight before loading inputs or requesting public data. Missing/modified research files, Python path/version drift, relevant package version drift, Freqtrade import path drift, or unrelated Git source history stop the run. This is reproducibility checking, not a hostile-administrator security boundary.

For restoration, check out the verified integration commit in a separate directory first; do not reset or overwrite user changes. Recover the approved historical data separately and verify both historical_inputs.json and historical_cost_inputs.json. Recreate the same virtualenv with the recorded Python and dependency versions using official sources. Dependencies remain subject to normal install permissions; do not copy credentials. This deliverable does not claim to include an entire offline environment image or all transitive package wheels.

The current installation is deliberately pinned to `/workspace/shared/btc-quant-worktree`. If restored elsewhere, preflight must fail. After explicitly reviewing the new repository and Python paths, update the manifest as a new runtime lock revision, re-run the current focused research suite (27 tests at the V3 hourly acceptance; 14 was the earlier runtime-lock stage) and historical parity validation, and commit that review. Do not automatically rewrite paths, hashes, or dependency pins just to get past a mismatch. Frozen T1/B1 economic rule changes require a distinct research version, not merely a runtime lock change.

The runtime manifest copies the complete original frozen protocol for visibility, while the reference source hashes enforce the actual code. Protocol parameters, fees/slippage, funding, historical input hashes and UTC closed-bar assumptions remain unchanged. Recovery does not imply strategy adoption or change schedules. Only use the supplied research CLI: native Freqtrade trade startup may initialize account resources before strategy guards, so it is not an approved entrypoint. Native order/cost ledger equivalence remains unverified.

## Research execution presentation revision — 2026-10-19

`decision.research_execution` is the primary per-strategy research action display; `NO_EXECUTABLE_DECISION` and `account_execution_eligibility` only describe account execution eligibility and must not hide computed research results. This revision changes presentation only, not indicators, risk, sizing, ledger, sampling or schedules.

ST position provenance comes from the same round's verified `st_checkpoint.json`: historical entry signal/time, raw open, cost-adjusted research fill, quantity, fixed stop and planned risk. `INITIALIZED` has no new entry/order even when the reconstructed position is long. A historical position's entry price must never be presented as an invitation to enter now. Subsequent `new_order_details` retains every incremental event in sequence and adds UTC timestamp labels. A no-change observation explicitly says no new research entry/exit. Research prices are not current actionable quotes or account fills.

T1/B1 remain signal-only in this hourly path; current quantity/entry-price/protective-stop/target are not calculated or not defined and stay missing, rather than zero. Their defined daily exit conditions are shown. ST has no fixed profit target or entry deadline; do not invent either. Account validity duration, allowed price deviation and leverage/margin constraints remain explicitly undefined. These gaps do not suppress research signals. The ST 0.5% research risk is not the old 20 USDT budget and not a guaranteed loss cap.

Compatibility: `run_research.py`, `signal_report.py`, all signal/economic and ST checkpoint source files are byte-identical. Old packages remain immutable; exact archived signal replay remains supported by the existing source checks. Historical display augmentation, if requested, must be a separate derived artifact, never replacement of an original round.

Intrabar stops: the hourly-end ledger timestamp is not a known trigger/fill time. Display uses null execution_time_utc and an H1 interval; only ledger_time_utc preserves the bookkeeping timestamp. Opening-price events are research accounting timestamps, not live account fills.


## Current signal advice presentation — 2026-10-19 (supersedes older chat display guidance)

The hourly chat now reads `decision.signal_advice` for the three independent strategies. New current signals say buy long or sell/close long; no short strategy is introduced. The latest verified ticker is a reference price with its actual quote and receipt time, not a historical simulated fill. Signal time is separate; intrabar stop times retain the H1 interval when exact time is unknown. Only genuine new current actions show these details. Every hourly round still reports, including unchanged target states. Initialization and caught-up past events are not new entries. All event sequence details remain recorded; an earlier event superseded within the same interval is not an invitation to execute it now.

Do not display exact BTC quantities, old position/entry details, or historical ST holdings in the routine chat. New actions may state an allocation only from the frozen strategy basis: T1/B1 at most 90% of that strategy's available cash including entry fee (not account assets or guaranteed exact exposure); ST only the matched new research entry's fee-inclusive spending divided by its explicit pre-entry research equity; otherwise allocation is not calculated. Exits close the strategy position, not open short. A research allocation calculated using its original fill is separate from the current ticker reference price. No personal account mapping or new sizing rule is implied.

The old research_execution fields and research ledgers remain unchanged for backtest/review and comparison. They are not a prerequisite for adding T1/B1 advice and are not the chat template. No new continuous T1/B1 ledger, protective stop, manual reaction-time/expiry rule, fee change or timing rule has been added. A missing daily-boundary observation is explicitly flagged, not silently WAIT. Stable signal event IDs deduplicate observations, not delivery receipts: the external notifier must reconcile original notification evidence before any repeat; unknown notification state must not be retried blindly. This module neither sends nor certifies messages. Original same-round COMPLETE/FAILED/INTERRUPTED handling is unchanged.


## Target/action clarity revision — 2026-10-19 (latest display guidance)

Read each `decision.signal_advice.strategies[name].presentation` first for chat rendering. `target_text` states the strategy target, never the account holding. `action_text` independently states the current advice. Normal example: “趋势策略：目标持仓；本轮无新增买卖建议。” This does not authorize a missed entry, averaging in or reentry. A genuine CURRENT action still uses the original event reference_price and suggested_fraction; no computed economic fields are changed.

Display precedence: DATA_ERROR, OBSERVATION_GAP, repeated notification reconciliation, historical-only catchup, current new action, initialization, then normal no-change. Never use terminal MAINTAIN alone to mask exceptions or interval events. Preserve `event_sequence` order, show prior superseded / historical events as context rather than current instructions, and retain original exact-time/null/H1-interval distinctions. Missing presentation in old packets must be interpreted from original status/events using this same precedence, not written back into those immutable archives.

Keep the three existing chat blocks, actual sample time and verified evidence link. Frontend wording only; signal/economic rules, sampling, research ledger, daily review, task identity and schedules stay unchanged.
