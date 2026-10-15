# Publication review

Reviewed 2026-10-15 for a public historical research archive plus complete official source snapshot.

## Research additions

The original 37 copied artifacts remain byte-for-byte preserved and are individually enumerated in `SOURCE_MANIFEST.json`. All 16 Python files passed AST syntax parsing. All four research configurations use `dry_run: true`, empty exchange credentials and disabled Telegram integration. No new backtest or runtime test is claimed by these publication checks.

Pattern scanning and inspection of selected research files found no populated credentials, private-key blocks or personal account information. No private market-data collection, virtual environment, generated project result archives or runtime logs are included.

## Official source snapshot

All 782 files tracked by official commit `1f394eaebc2f46a83d26971388628707802f8602` are included at repository root without excluding tracked files. Their modes, Git blob IDs, SHA-256 digests and sizes are in `UPSTREAM_MANIFEST.json`. The upstream tree hash is `669d5e1f6c067a36048344fc0b97256a195c4fbe`.

The upstream working tree was clean before copying. No embedded `.git`, recovered virtual environment or untracked runtime files are part of the snapshot. The tracked `ft_client/LICENSE` symbolic link targets `../LICENSE` and is preserved as a symlink. Already-tracked wheels, public test-market fixtures and documentation images are retained deliberately; they are not user credentials or recovered user runtime data. They were not executed as part of publication.

Secret-pattern inspection of textual upstream files produced five candidate locations: an explicitly truncated RSA-key example in exchange documentation, an expired 2020 JWT example in REST API documentation, and three fixed test-token values in RPC tests. These are public upstream illustrative/test content, not user secrets; they remain unchanged to preserve the official source snapshot. These checks are not a guarantee against every possible secret format, and new changes require fresh review.

## Provenance and licensing

The root source snapshot retains all official licensing and copyright notices. Original research package paths and hashes document archive provenance, not exclusive authorship of every line. Adapters depend on Freqtrade interfaces. No blanket MIT or other new project license has been added. Review custom-code provenance and derivative-work obligations before selecting a license for additions.

## Limits

The frozen research rejection remains unchanged. Old absolute paths require deliberate restoration or a separately reviewed portability change; this repository is not a turnkey backtest distribution. Full upstream Git history, private inputs and active processes are not included. Publication neither adopts a strategy nor starts a service, automatic synchronization or a trade.
