# BTC quant research archive

Public source archive for historical Bitget BTC/USDT:USDT research using Freqtrade 2026.9. **Not an adopted trading strategy, not investment advice, not a live-trading deployment.** No exchange account or credentials are required for the archived research.

## Status

- `smoke/`: minimal framework and accounting smoke research, not a trading recommendation.
- `sr-h1-v1/`: frozen Structure Reclaim H1 v1, reference rules, native Freqtrade adapter, tests, and historical audit scripts.
- Historical decision: **REJECT_FROZEN_CANDIDATE**, with insufficient trade-count evidence. Publishing the code does not change that decision.
- Original protocols are historical frozen artifacts, including their old dates and constraints. They do not define current monitoring schedules or current approved risk limits.
- This is a source preservation snapshot. No new backtest result is claimed by this commit.

## Runtime

Official upstream: https://github.com/freqtrade/freqtrade

Version: `2026.9`; commit: `1f394eaebc2f46a83d26971388628707802f8602`.

The recovered runtime uses an isolated Python virtual environment and an editable install of the unmodified upstream checkout. It is not a Docker image. Official engine source is not vendored here. Dependency snapshots are under `smoke/installed-requirements.txt` and `sr-h1-v1/upstream_version/`.

## What is and is not preserved

Preserved: original custom Python scripts, research strategy, execution adapter, frozen protocol and hashes, tests, credential-empty research configurations, dependency versions, manifests and the historical adoption decision.

Excluded: credentials, account balances/identifiers, virtual environments, caches, official source checkout, raw market datasets, generated trade/results archives and runtime logs. Configurations have `dry_run: true`; that is a safety setting, not evidence that live paper trading was started. Do not run `trade` or expose an API server from this archive.

`SOURCE_MANIFEST.json` records each copied source file's SHA-256. Source bytes are preserved, including historical absolute paths. Original `REPRODUCE.txt` files describe the original complete evidence package, not the smaller public archive; their statements that datasets are included do **not** apply to this repository.

See [RESTORE.md](RESTORE.md) for recovery boundaries, and [PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md) for inspection scope.
