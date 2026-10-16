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
