# Publication review

Reviewed 2026-10-15 for publication as a historical research archive.

## Scope and checks

- 37 copied source artifacts are enumerated individually in `SOURCE_MANIFEST.json`, with original package-relative paths, byte sizes and SHA-256 digests. They are preserved byte-for-byte rather than silently modernized.
- Every selected file was inspected for credential-related fields, personal paths, external URLs, identity/contact strings and licensing indicators. Pattern scanning found no GitHub tokens, AWS access-key identifiers, private-key blocks or populated password/token/API-key assignments.
- All four configuration files have empty exchange key, secret and password fields, `dry_run: true`, and disabled Telegram integration. They are historical research configurations, not evidence of an active service or safe authorization for live trading.
- All 16 Python files parsed successfully with Python's AST parser. This is syntax validation only, not a new backtest or an end-to-end runtime test.
- No symbolic links, virtual environments, full upstream checkout, raw market datasets, trade/account databases, runtime logs, caches or credentials are included.
- Public exchange names, synthetic test fixtures, research assumptions and historical aggregate rejection evidence are included. No private account position or actual trade evidence is asserted.

These checks reduce accidental disclosure risk; they are not a guarantee against every possible secret format. New changes require fresh review.

## Provenance and licensing

The source package names and hashes record archive provenance, not a claim of exclusive authorship for every line. Freqtrade is an external upstream dependency at the commit recorded in `README.md`. Its existing GPL-3.0 license text is retained in the respective upstream-license files; its complete source tree is not vendored here.

Adapter code depends on Freqtrade interfaces. No blanket MIT or other new project license is granted by this archive. A separate provenance and derivative-work licensing review is required before choosing a project license or advertising the repository as fully licensed open source. Public visibility alone does not supply reuse rights.

## Known limitations

- Historical absolute cloud paths remain in copied sources and dependency snapshots. See `RESTORE.md`; this is not a one-command portable distribution.
- Raw input data and full runtime evidence are intentionally excluded. Data manifests describe inputs but are not those inputs.
- The rejected frozen candidate remains rejected. Historical dates, research limits and protocol assumptions are not current trading permissions or adopted strategy rules.
- Publication does not start a process, schedule synchronization, execute a strategy or place an order.
