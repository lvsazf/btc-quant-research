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
