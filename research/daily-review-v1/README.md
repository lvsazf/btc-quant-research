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

The previously documented evaluate_candidate.py did not exist. Do not invoke it or treat that documentation as implementation evidence. candidate_registry.py is the minimum offline evidence register. evaluate_candidate.py is a deliberately narrow executable identity-candidate engineering check, reusing the frozen ST feature and ledger implementation; it is not a general arbitrary-code optimizer. Use candidate_registry.py --help for register, ingest, prospective and import-public commands. For the executable engineering check, use evaluate_candidate.py --protocol FROZEN_JSON --inputs INPUT_JSON --inputs-sha256 VERIFIED_HASH --output NEW_DIRECTORY. Its supported adapter and exact comparison-grid contract are validated before execution; see --help. A real candidate outside the supported contract needs a separately reviewed implementation, not an invented pass. Existing specialized public research code remains the economic calculation source; only results bound to the frozen parent/code/input/window/risk/cost protocol may be registered. Historical imported comparisons remain seen-data diagnostics, including every failed sample. A registered result does not pass a strategy or adopt it.

Forward conditions must be frozen before genuinely new observations are collected, with timestamped plan and hashes. Missing numeric decision thresholds remain PENDING_USER_CONFIRMATION, not invented or relaxed. No parameter tuning, strategy adoption or hourly replacement is performed by this daily CLI. Outer review must explicitly record data/engineering diagnosis separately from economic review, the decision to hold or research a candidate, supporting and opposing evidence, and the next verification action. The default report states economic review NOT_PERFORMED, not an unsupported conclusion that optimization is unnecessary.

## Acceptance limits

The 2026-10-19 engineering repair uses all 24 saved 2026-10-18 archives, retaining 22 missing original terminal receipts, plus the separately identified 2026-10-19 first formal ST archive as a later cutoff input. Only two covered-day originals can be replayed; full backtest data does not establish full observation coverage. A separate current-day partial check verifies the ST INITIALIZED event, not a full day. Focused offline tests and real saved-input run evidence do not imply complete external Google/Sheets/notification acceptance or the full upstream suite. Source hashes and actual Git identity are recorded separately from the frozen economic version.

## Completion and evidence gates

Each supplied hourly archive must have its original adjacent state.json receipt with status COMPLETE, matching round_id and archive_sha256. A missing, failed or mismatched receipt is an explicit input evidence issue, not assumed completion. Receipt content/hash is retained in the daily report. When restoring from Google, restore the separately verified original receipt as well; the bundle's pre-packaging lifecycle snapshot is not a substitute for a terminal receipt.

Backtest coverage and observation coverage are reported independently. Full scheduled observation coverage requires all 24 distinct Beijing-day hourly :03 slots with externally verified scheduled provenance and COMPLETE receipts; complete historical candles or a complete backtest never prove those observations happened. Package kind is neutral DAILY_REVIEW_EVIDENCE. REVIEW_WITH_EVIDENCE_ISSUES and INVALID_BACKTEST_PARTIAL exit 2; BLOCKED_PARTIAL exits 1. Exit 0 may still be PARTIAL_DAY_DIAGNOSTIC or coverage-limited, so consumers must inspect both explicit coverage sections rather than call all exit-0 reports full-day success.

## Independent branches and ST activation

The fixed T1/B1/CASH/HOLD backtest is attempted first. ST checkpoint and actual-round checks continue even if cost/backtest processing fails; native and ST round checks do not suppress one another. Aggregate status retains blocked/partial branches and all evidence issues, never turns a surviving branch into whole-chain acceptance. ST_ACTIVATION.json records the original first formal 2026-10-19 07:03 UTC round and receipt hashes. Planned ST slots before this instant are NOT_APPLICABLE, not missing; post-activation completion is separate from full 24-hour calendar coverage. A historical checkpoint reconstruction cannot prove earlier ST observations.

ST cumulative metrics carry their actual checkpoint asof, which may be later than the covered date; covered-day contribution is independently bounded. ST uses a different risk policy from T1/B1, so those results do not establish like-for-like superiority. Receipt arithmetic/event consistency and independent signal checks are not a second independent economic execution-path replay.

Partial current-day engineering runs split planned slots into due, completed-due, genuinely missing-due and future-not-yet-due as of report generation. Future slots are never labelled missed execution; full calendar-day completion remains separate. Runtime preflight failure writes a BLOCKED_PARTIAL report and hash-checked failure bundle without starting calculations.
