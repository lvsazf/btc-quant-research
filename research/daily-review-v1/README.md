# Daily fixed-backtest and actual-round review

The daily entrypoint first runs the preserved audited research economic ledger, then reconciles explicitly supplied actual hourly archives. It does not claim native Freqtrade order/cost certification. No account, order, scheduling, Google write, or strategy adoption occurs here. The hourly package and lock remain unchanged.

## Fixed protocol

See PROTOCOL.json. Cumulative start is 2026-07-13 00:00 UTC, the available actual-funding anchor. End is the requested Beijing natural day's 24:00 (16:00 UTC), capped to complete trade/mark/funding coverage. Complete daily indicators use UTC 00:00, not Beijing midnight. Full historical prewarm determines states; the ledger starts only once at the fixed anchor, not afresh each day. The original end-of-test liquidation result remains separate. Day contribution uses continuous marked equity before that artificial liquidation and actual rule fees/funding within the day. It is research, never actual account performance.

Missing cost data is not zero-filled. Later supplementary mark evidence must include retrieval time, HTTP status and code, and is labelled post-hoc, not information available at the original observation. Only given real round IDs are reconciled; candles cannot establish past observation coverage. Differing historical rule/source hashes yield unsupported-version status, not a silent replay with today's rules. Notification and fills are not inferred.

## Invocation

Use existing .venv/bin/python research/daily-review-v1/daily_review.py --date YYYY-MM-DD --round PATH_TO_REAL_GOOGLE_EVIDENCE_JSON [--round ANOTHER_REAL_ARCHIVE] --history-root /workspace/shared/btc-quant-research-20261010 --output NEW_REPORT_DIRECTORY [--mark-supplement POSTHOC_MARK_JSON].

The outer existing daily task resolves yesterday in Asia/Shanghai, provides actual stored archives, and preserves failed/partial results. This CLI does not list or mutate tasks. A new output directory preserves prior reports; outer task must avoid duplicate publication. Reports, cumulative ledgers, normalized reproducible backtest inputs and a hash-verified JSON evidence bundle are written locally. Original archive SHA references remain in the report; they must remain available alongside the bundle to replay hourly observations. Original state/Google/notification receipts are not overwritten. No cancelled write is retried.

## Evidence-driven optimization path

No daily forced tuning. Data/runner problems are separated from economic shortcomings. If a genuine hypothesis is warranted, place isolated candidate code and protocol under candidates/NEW_VERSION; preserve original T1/B1 and all failed baselines. Protocol requires version, hypothesis, supporting evidence, falsification, validation_plan, code_sha256 and adopted:false. Code exports desired_states(full_closed_H1_history), returning available-time integer milliseconds to boolean desired state. It must be causal, account-free and reviewed before execution.

Run existing .venv/bin/python research/daily-review-v1/evaluate_candidate.py --inputs REPORT/backtest_inputs.json --inputs-sha256 VERIFIED_HASH --candidate candidates/NEW_VERSION/candidate.py --protocol candidates/NEW_VERSION/protocol.json --output NEW_CANDIDATE_RESULT_DIRECTORY.

This executable research path evaluates candidate, CASH, HOLD and unchanged T1/B1 on identical inputs, original sizing/cost ledger and all four predeclared fee/delay scenarios. Prefix checks are necessary diagnostics, not causality proof. The protocol must specify held-out or forward validation; previously seen history is never labelled blind. No candidate is automatically adopted or installed into hourly. A separate explicit decision is required to switch a version.

## Acceptance limits

Current hand validation uses only saved 2026-10-16 manual and scheduled rounds, not a full day. Focused offline tests and real saved-input run evidence do not imply complete external Google/Sheets/notification acceptance or the full upstream suite. Source hashes and actual Git identity are recorded separately from the frozen economic version.

## Completion and evidence gates

Each supplied hourly archive must have its original adjacent state.json receipt with status COMPLETE, matching round_id and archive_sha256. A missing, failed or mismatched receipt is an explicit input evidence issue, not assumed completion. Receipt content/hash is retained in the daily report. When restoring from Google, restore the separately verified original receipt as well; the bundle's pre-packaging lifecycle snapshot is not a substitute for a terminal receipt.

Backtest coverage and observation coverage are reported independently. Full scheduled observation coverage requires all 24 distinct Beijing-day hourly :03 slots with externally verified scheduled provenance and COMPLETE receipts; complete historical candles or a complete backtest never prove those observations happened. Package kind is neutral DAILY_REVIEW_EVIDENCE. REVIEW_WITH_EVIDENCE_ISSUES and INVALID_BACKTEST_PARTIAL exit 2; BLOCKED_PARTIAL exits 1. Exit 0 may still be PARTIAL_DAY_DIAGNOSTIC or coverage-limited, so consumers must inspect both explicit coverage sections rather than call all exit-0 reports full-day success.
