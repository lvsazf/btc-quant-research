# Restore, modify and upgrade in one repository

## Source layout

Clone this repository. Its root already contains the official Freqtrade 2026.9 tracked source snapshot, fixed at commit `1f394eaebc2f46a83d26971388628707802f8602`. Do not create a second engine repository or depend on a submodule to obtain this snapshot. `research/UPSTREAM_MANIFEST.json` covers every upstream tracked file and mode. Research-specific paths in `SOURCE_MANIFEST.json` are relative to `research/`.

## Restore a research environment

1. Use an isolated Python virtual environment. Follow the included official installation documentation and platform prerequisites. Installing dependencies is separate from possessing the source.
2. The historical dependency manifests are `research/smoke/installed-requirements.txt` and `research/sr-h1-v1/upstream_version/installed-requirements.txt`. Their editable `file://` line points to an old cloud path: replace it with an editable installation of this repository root in the new environment. Do not blindly reuse a nonexistent absolute path.
3. Verify dependency consistency, reported version and imported module location. A working CLI is not proof that research replay or a continuously running service succeeded.
4. Recover the project-specific market inputs separately and verify their original manifests. They are not included. Official test fixtures included at root are not substitutes for those research inputs.
5. Preserved research scripts contain original absolute paths and assumptions about sibling directories. Either recreate those paths in an isolated research workspace, or make an explicit, reviewed path-portability change in a new commit. Do not silently modify frozen protocol files or present an untested invocation as turnkey.
6. Run tests and backtests only when their inputs are available, with a separate output workspace. `run_research.py --run` can overwrite same-named result files. Do not overwrite the sole evidence archive. Never start live trading or an API service as a restoration check.

## Future changes and upstream upgrades

Engine modifications belong in the root source tree; custom strategies, research protocols and related documentation belong under `research/`. Preserve historical frozen versions and their hashes. Use distinct commits for source upgrades, portability fixes and strategy changes so their effects remain reviewable.

Before an upgrade, record the exact target upstream tag/commit and compare it with the original baseline plus local patches. Prefer upstream functionality when it already solves a requirement; avoid carrying redundant patches. Review licenses and conflicts, test affected behavior, and update the upstream manifest only when the new snapshot is actually adopted. Preserve previous Git commits as recovery points. Do not overwrite custom changes using an unreviewed bulk source replacement.

For authorized future synchronization: inspect every staged path and diff, exclude private credentials and generated runtime artifacts, run applicable checks, push normally without force, and verify the remote commit and changed contents. This document does not create a background sync service, deploy anything or authorize trading. Public source storage alone does not guarantee durable availability of the separate runtime or datasets.

## Licensing

Retain official root and third-party license notices. No blanket MIT or other new license is assigned to the project-specific additions. Public visibility alone does not grant an additional license. Review provenance and GPL/derivative-work obligations before choosing a license for custom code or advertising the entire project as fully licensed open source.
