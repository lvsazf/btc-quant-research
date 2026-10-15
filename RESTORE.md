# Recovery and future synchronization

## Recover software separately from research inputs

1. Obtain the official Freqtrade repository and check out exactly commit `1f394eaebc2f46a83d26971388628707802f8602` (2026.9). Preserve upstream licensing.
2. Create an isolated Python virtual environment. Install the pinned dependency snapshot, replacing the snapshot's old `-e file:///workspace/.../upstream` line with an editable install of the checkout you actually created. Do not install the stale local URI blindly.
3. Verify `python -m pip check`, `freqtrade --version`, and `python -c "import freqtrade; print(freqtrade.__file__)"`. A successful CLI check proves environment availability only, not a running strategy or backtest.
4. Recover the separately retained public-market data/evidence archive. Validate the recorded hashes and coverage using the archived manifests. This Git repository intentionally does not contain those datasets.
5. The frozen scripts contain absolute historical `/workspace/shared/...` paths. Restore those paths in an isolated workspace or make an explicitly documented path-only adaptation in a new version. Do not silently change the frozen protocol or treat an adapted file as byte-identical.
6. Run tests and backtests only with complete inputs, in a separate work copy. `run_research.py --run` writes result files and can overwrite same-labelled results. Preserve old evidence and never run it over the sole archive.

## Synchronization policy for this project

For authorized future code changes: inspect diffs, exclude secrets/private account information/raw datasets/runtime artifacts, run applicable checks, commit the exact changed files, push normally without force, then verify the remote commit and disclose tests not run. Never claim a local-only commit is remotely backed up. No scheduled sync daemon, deployment, account connection or trading is established by this policy.

## Licensing

The Freqtrade GPL-3.0 license text is retained in the original upstream license files. No license is stripped or replaced. Custom-source licensing has not yet been selected; making this repository public alone does not establish an open-source license or grant blanket MIT rights. Review provenance and applicable derivative-work obligations before redistributing or adding a repository-wide license.
