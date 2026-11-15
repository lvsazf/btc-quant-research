# Approved public-data pagination recovery, 2026-11-15

The current runtime manifest SHA256 is `606756966b0d14004bfb3949551e9998f691da2cffe323555a6a2bff0b1cdb04`.
This technical update includes the approved runtime path migration and public funding/H1 pagination, daily derived-evidence verification, exact historical replay compatibility and regression tests. Strategy signals, economics, costs, risk, sizing, dependency versions and scheduling are unchanged. This is research code, not account execution.

## Recovery boundaries

A Git checkout is only the source layer. It does not restore the Python environment, frozen historical inputs, formal checkpoints, failed/interrupted records, resident revocation/locks or external archive/notification receipts. Retrieve those separately from the authorized private archive. Never publish these operational archives here or substitute an isolated manual checkpoint for a formal checkpoint.

1. Restore this exact source revision into an isolated location. Verify the manifest and every locked file hash.
2. Restore exact dependencies and required native-library binaries; verify versions and binary hashes against the manifest. Do not relax the guard to accommodate a different machine.
3. Restore hash-verified frozen inputs and the latest verifiable formal COMPLETE checkpoint from original evidence. Preserve original bytes and identifiers. Record any historical-state omissions explicitly.
4. Check active process/lock and resident revocation state before using the sole hourly entry. Do not run a second calculator, reset state or replay failed rounds.
5. Verify offline in isolation first. The manifest pins absolute runtime paths; a relocated drill is not proof that the production path guard passed. Do not change the approved manifest merely to pass an isolated drill.
6. After authorized activation, use `hourly_job.py` with the actual scheduled UTC and original task identity. Verify calculation, local persistence, private archive, spreadsheet and message receipt separately.

Funding requests now page until the frozen 8-hour events are complete. H1 paging retains each raw response and metadata; the derived window indexes raw-page hashes, and the daily reader independently reconstructs it. Empty, conflicting, missing or stagnant pages fail closed. The H1 endpoint's approximately 83-day retention remains a limit: this change is not perpetual incremental anchor maintenance.

The repair's recorded local regression results were 104 hourly tests and 75 passing daily tests with one existing path-fixture skip. Full upstream pytest and a full historical archive audit were not run. A successful manual technical acceptance is not proof of scheduled execution, strategy profitability or delivery. Each deployment/recovery must obtain its own evidence.
