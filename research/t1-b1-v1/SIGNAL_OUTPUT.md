# Signal-only output contract

User-facing purpose: trading decision output for manual execution, not a menu of operating modes. The current candidates remain unadopted research as a factual readiness status, not a separate product mode. Historical/current CLI verbs are technical validation/input entrypoints, not choices to present to the user. Unknown capital, holdings and pending orders must not be replaced with simulated accounts.

Runtime lock V2 adds reporting, not a new economic rule. Economic version remains T1B1_RESEARCH_V1_PORT_20261016. The actual Freqtrade StrategyResolver and IStrategy advise_indicators / advise_entry / advise_exit methods supply dataframe flags and tags. The frozen strategy code is the definition of T1/B1 rules; the framework does not itself invent a strategy.

Each signal_report includes H1 opening time, signal-available close time, latest complete UTC daily basis timestamp, actual native long/short entry/exit flags and active tags, daily close, SMA50 and prior20-high/prior10-low diagnostics. Irrelevant diagnostics do not become added conditions. At an H1 close, only completed daily information is used.

Target state LONG/CASH is not the user's holding. Raw entry_long may remain 1 on multiple hourly rows because the frozen rule remains long. Event is separately classified: INSUFFICIENT_DATA, INITIALIZED_LONG/CASH (prior state unknown), ENTER_LONG_TRANSITION, EXIT_LONG_TRANSITION, or WAIT (no target-state change). Initialization is not evidence of a newly occurring market crossing. A retained raw flag must not become a new notification/order every hour. Event is local adjacent-H1 comparison, not durable notification deduplication; later task wiring must persist the signal basis + version + event identity and handle missed rounds without inventing historical delivery.

Execution quantity, entry price, structural stop, price target and entry deadline are null, with unknown account position and explicit research-only status. Frozen historical sizing (90% research equity) and one-times leverage assumptions are not actual account sizing. Placeholder native stoploss must never be reported as a frozen stop. No price target or arbitrary signal validity duration is added. Defined daily state exits are output as exit transitions, not automatic closes of a known real holding.

Official interface capabilities inspected in this checkout:
- custom_stake_amount accepts proposed/min/max stake, rate, leverage and side. It can host adopted sizing rules later, but current account-free flow must not ask wallets for actual balances or convert historical capital into executable quantity.
- custom_stoploss/custom_exit consume a Trade and current rate/profit; current frozen candidates do not define such live rules. Do not enable them or fabricate a Trade to claim an implemented stop policy.
- The safe one-shot entrypoint uses the native dataframe pipeline without FreqtradeBot, exchange account clients or order ledger. Native order confirmation remains false. Do not use freqtrade trade.

Next integration stages, not implemented here: persistent round/attempt and signal identity; source/evidence storage and Google receipts; complete original multiperiod/OI/candidate audit requirements; previous-day actual-run replay; hand-run interrupted/duplicate/notification-unknown acceptance; only then modify the existing task prompts without changing cadence. Macro context is supplementary and must never override or relabel machine signals.

Offline acceptance: 18 research tests passed; historical-signals reproduced unchanged economic metrics and native/frozen per-row parity. No new market sampling, no hourly/daily task change, no deployment or adoption is implied. Full upstream pytest remains blocked by missing pytest-xdist as previously recorded; this is not a claim of full upstream-suite success.
