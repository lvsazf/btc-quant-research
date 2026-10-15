"""Plumbing-only BTC hourly research probe. NOT an adopted or recommended strategy.

Uses native Freqtrade signals, stake/leverage/entry-confirmation/time-exit hooks.
It does NOT port SR H1 v1, model real spreads, or simulate hourly notification lag.
"""
import math
from datetime import timedelta

from freqtrade.strategy import IStrategy


class SmokeHourlyResearch(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    startup_candle_count = 24
    process_only_new_candles = True
    position_adjustment_enable = False
    use_exit_signal = True
    minimal_roi = {}
    stoploss = -0.04  # 4% of stake at 2x => 2% adverse price movement.
    trailing_stop = False
    # Conservative nominal risk reserve for this probe, not a calibrated execution model.
    planned_loss_fraction = 0.04 + 0.0025
    order_types = {"entry": "market", "exit": "market", "stoploss": "market", "stoploss_on_exchange": False}

    def populate_indicators(self, dataframe, metadata):
        dataframe["sma20"] = dataframe["close"].rolling(20).mean()
        dataframe["momentum"] = dataframe["close"].diff(3)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe.loc[(dataframe.close > dataframe.sma20) & (dataframe.momentum > 0) & (dataframe.volume > 0), ["enter_long", "enter_tag"]] = (1, "smoke_long")
        dataframe.loc[(dataframe.close < dataframe.sma20) & (dataframe.momentum < 0) & (dataframe.volume > 0), ["enter_short", "enter_tag"]] = (1, "smoke_short")
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        if not math.isfinite(current_rate) or current_rate <= 0 or leverage < 1 or leverage > 2:
            return 0.0
        # Reduced notional for a smoke test; all three user limits remain upper bounds.
        notional = min(400.0, 1000.0, 20.0 / self.planned_loss_fraction)
        stake = max(0.0, min(notional / leverage, max_stake))
        return stake if min_stake is None or stake >= min_stake else 0.0

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side, **kwargs):
        if pair != "BTC/USDT:USDT" or not all(math.isfinite(x) and x > 0 for x in (amount, rate)):
            return False
        notional = amount * rate
        return notional <= 1000.0 and notional * self.planned_loss_fraction <= 20.0

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        return min(2.0, max_leverage)

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        if current_time - trade.open_date_utc >= timedelta(hours=6):
            return "smoke_time_exit_6h"
        return None
