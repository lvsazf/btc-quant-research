## Current approved ST research extension — 2026-10-19

The sole hourly_job entry now also emits independent ST-H1-LO-v1 research signals and a continuous cost ledger. User approval Sentinel_e1f6c3f614f08191b1a16f4057fb41f9 authorizes research tracking, not economic validation, account trades or hosted stops. Current lock is T1B1_ST_RESEARCH_RUNTIME_V1_20261019, explicitly derived from the approved mark-corrected V3 manifest. T1/B1 native signal and economic rules are unchanged.

ST parameters and independent risk sizing are frozen in st_protocol.json. Its source is independent research, not Freqtrade native order/cost certification. First integration emits INITIALIZED with a reconstructed research target; never present prior historical entries as a new real-time buy. Later rounds include actual new research orders, potentially multiple transitions across a gap. WAIT means a maintained research target, not no calculation. Only after a COMPLETE state may results be presented. No hypothetical research fill is an actual account fill.

st_checkpoint.json persists a cumulative ledger from2026-07-13 UTC, no daily restart or terminal liquidation. At the current hour boundary only the open is used; unclosed high/low/close cannot trigger a stop. Stops are reconstructed from closed H1 bars in later observations and are never hosted. Hash-verified prior COMPLETE checkpoints and unchanged historical input prefixes are required; missing or revised evidence fails closed. Day contributions use continuous hourly curve differences. ST signal replay and receipt cashflow checks are separate from a second economic-path replay, which is not yet implemented.

# Single-hour entrypoint (no scheduler installed)

Purpose: machine-calculated decision support for manual execution. Current T1/B1 are NOT_ADOPTED, so computation can COMPLETE while decision is NO_EXECUTABLE_DECISION. Report the real calculated target states and transitions first, and execution eligibility separately. NO_EXECUTABLE_DECISION is not market C or a claim that computation did not run. Individual strategy events may be WAIT, meaning no new target-state transition, while the retained LONG/CASH target is still a real calculated result. Missing execution rules, actual capital/holdings, or deadlines are never invented.

## Exact invocation

```sh
/workspace/shared/btc-quant-worktree/.venv/bin/python \
 /workspace/shared/btc-quant-worktree/research/t1-b1-v1/hourly_job.py \
 --task-id ORIGINAL_VERIFIED_AUTOMATION_ID \
 --scheduled-utc ACTUAL_SCHEDULED_ISO_TIMESTAMP_WITH_TIMEZONE \
 --storage-root /workspace/shared/btc-quant-runs/hourly-observations \
 --history-root /workspace/shared/btc-quant-research-20261010
```

The external original task supplies its real ID and scheduled timestamp. Do not guess an ID or assign a manual run to a scheduled slot. No task configuration is changed by this CLI. Manual acceptance uses a separate task ID, separate storage-root and --manual-validation.

## Output / idempotency

Round key = first24 hex SHA256(task-id + canonical UTC scheduled time). Under storage-root/<round-id>:
- run.lock: nonblocking process lock. Active duplicate returns ALREADY_RUNNING without sampling.
- state.json: atomic stage journal with task/attempt/time/status, decision, pending Google and notification status. Terminal duplicates return DUPLICATE_NOT_RUN. If the old process ended without terminal receipt, mark INTERRUPTED when the lock is next acquired. A hard kill may leave RUNNING until then; this is not a running-process monitor.
- input_index.json and storage-root/inputs/<sha256>.csv: immutable hash-verified input copies, shared locally across rounds.
- run/: public response evidence and native strategy result; execution.log stays local.
- decision.json and summary.json: three sections, decision/reasons, relevant market/asof, machine signal basis. Caller must check terminal state before using any partial summary.
- google-evidence.json: self-contained UTF-8 JSON archive with per-file hashes, full anchored historical input CSVs, raw snapshot and source snapshot. All contents read back and verified before COMPLETE. Parent/child runtime hashes and archived source hashes must agree.
- lifecycle.json: phase snapshot before packaging; final archive hash/terminal receipt stays in state.json to avoid recursive self-hashing.

This initial standalone archive duplicates anchored CSV bytes in each uploaded bundle for reliable restoration (about1.66MB in manual acceptance), while local blobs deduplicate them. A later separately verified stable Google input archive reference can reduce uploads; it is not implemented here. Google sync and notification receipts remain PENDING_NOT_ATTEMPTED / NOT_SUBMITTED until an authorized external connector records actual outcomes. No Google credentials, API writes, or automatic messages are built in.

Failure/no-runtime/no-input/stale/unready/conflicting package versions produce FAILED/INTERRUPTED and ERROR_NO_DECISION. Do not publish normal decisions from such a folder. Raw subprocess errors and execution logs remain local, not automatically archived. This wrapper intentionally does not automatically resample failed rounds, invent attempts, delete partial folders, or retry ambiguous notifications. An operator may investigate and separately authorize recovery while preserving the old round. Same-round success is reused, not refreshed to a different market time.

## Remaining original observation requirements

This package fetches only strategy-required public data and uses actual Freqtrade advise_* outputs. It does not silently satisfy independent OI, full hourly/4H/weekly/monthly or macro observation work, existing candidate lifecycle validation or yesterday's true-run replay. Existing valid background may be referenced with its old source time, explicitly not refreshed. These unimplemented supplements do not block calculation of existing frozen strategy signals; missing applicable candidate checks still forbid executable recommendations. Do not append discretionary filters to frozen T1/B1. Do not start a separate assistant market-feed chain or overwrite machine signals with macro commentary.

The updater currently bridges at most1000 hours from the fixed historical anchor; its single history-funding page contains at most100 events, so funding coverage can fail earlier (roughly800 hours at an8-hour interval, potentially shorter if the interval changes). Missing funding is not filled with zero; it is bounded, not perpetual incremental data maintenance. An ongoing incremental-anchor update needs its own verified implementation. Time/ticker freshness checks happen at the end of calculation; later delivery must cite actual asof, not claim the saved price remains current.

## Acceptance on 2026-10-16

27 focused tests passed, including stable timezone-normalized round keys, prior failure/success reuse, interrupted journal, actual subprocess lock contention, missing adoption, stale/future data checks, and source drift rejection. Real local missing-input failure and duplicate failure were exercised without network. One real public read-only manual run completed at06:19:27 UTC, then its duplicate returned without sampling. Source and packaged evidence hashes are checked separately. Final source-drift checks were hardened after that run and tested offline; no second market sample was taken. Timeout/SIGKILL crash injection has not been fully exercised. Full upstream test suite previously stopped at missing pytest-xdist; focused tests do not imply upstream suite success.

The CLI itself performs no account read, orders, strategy adoption, new service, schedule mutation or Google upload. This code boundary does not prohibit authorized outer connectors from archiving evidence or updating the original task prompt. Local calculation success, Drive archive verification, Sheets writeback and notification acceptance are separate stages; partial external completion must not be reported as full-chain success. Existing frozen economic rules and rejected SR baseline are untouched.

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
