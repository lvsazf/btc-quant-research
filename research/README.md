# BTC quant research and engine snapshot

This single repository contains the complete tracked Freqtrade 2026.9 source snapshot at the repository root, with project-specific historical research under `research/`. **No adopted trading strategy, investment advice or live-trading deployment is provided.**

## Layout

- Repository root: all 782 files tracked by official Freqtrade commit `1f394eaebc2f46a83d26971388628707802f8602`, including source, tests, documentation, example configurations, licenses and upstream-tracked binary fixtures/build resources.
- `research/smoke/`: minimal framework and accounting smoke research.
- `research/sr-h1-v1/`: frozen Structure Reclaim H1 v1, reference rules, native adapter, tests and historical audit scripts.
- `research/SOURCE_MANIFEST.json`: hashes for 37 original research artifacts, with paths relative to `research/`.
- `research/UPSTREAM_MANIFEST.json`: every upstream tracked path, file mode, Git blob SHA and SHA-256. Upstream paths are relative to repository root.

Official source: https://github.com/freqtrade/freqtrade

Version: `2026.9`. Original upstream tree: `669d5e1f6c067a36048344fc0b97256a195c4fbe`.

This is a complete tracked source snapshot, **not the full upstream Git history**, a fork relationship, submodule, virtual environment or ready-running service. Future engine changes can be committed in this same repository, separately from strategy changes.

## Research status and limits

The frozen historical decision remains **REJECT_FROZEN_CANDIDATE**, with insufficient trade-count evidence. Publication does not adopt the strategy or claim a new backtest. Historical dates and research limits do not define current monitoring schedules or approved trading constraints.

Original research source bytes are preserved, including old absolute cloud paths. Original `REPRODUCE.txt` files describe the original complete evidence package: their statements that research datasets are included do not apply to this public repository. Official upstream test datasets are distinct from those missing project-specific research inputs.

No private credentials, account information, recovered virtual environment, runtime logs, user market-data collection or generated project backtest archives are included. Upstream's already-tracked public test data and wheel files are intentionally retained for source-tree completeness. Credential-empty research configurations have `dry_run: true`; this is not evidence of an active paper-trading process. Do not infer permission to run trading or expose an API server.

See [RESTORE.md](RESTORE.md) for recovery and upgrade boundaries, and [PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md) for inspection scope. The official root README and license files remain unmodified.
