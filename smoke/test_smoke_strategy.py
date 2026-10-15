"""Acceptance checks for a plumbing-only strategy, not a profitability test."""
import importlib.util
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

PATH = Path(__file__).parent / "user_data/strategies/SmokeHourlyResearch.py"


def make_strategy():
    assert PATH.exists(), "The custom research strategy has not been implemented yet"
    spec = importlib.util.spec_from_file_location("smoke_strategy", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SmokeHourlyResearch({})


def test_research_only_hourly_futures_interface():
    strategy = make_strategy()
    assert strategy.INTERFACE_VERSION == 3
    assert strategy.timeframe == "1h"
    assert strategy.can_short is True
    assert strategy.position_adjustment_enable is False


def test_signal_functions_are_causal_and_support_both_directions():
    strategy = make_strategy()
    close = [100.0 + n for n in range(35)] + [134.0 - 2*n for n in range(1, 35)]
    data = pd.DataFrame({"close": close, "volume": 1.0})
    full = strategy.populate_entry_trend(strategy.populate_indicators(data.copy(), {}), {})
    assert full.enter_long.sum() > 0
    assert full.enter_short.sum() > 0
    assert not ((full.enter_long == 1) & (full.enter_short == 1)).any()
    for end in (25, 35, 45, len(data)):
        sliced = strategy.populate_entry_trend(strategy.populate_indicators(data.iloc[:end].copy(), {}), {})
        pd.testing.assert_frame_equal(full.iloc[:end], sliced)


def test_custom_stake_has_notional_and_cost_inclusive_risk_caps():
    strategy = make_strategy()
    for leverage in (1.0, 2.0):
        for max_stake in (0.0, 50.0, 1000.0):
            stake = strategy.custom_stake_amount("BTC/USDT:USDT", datetime.now(UTC), 60000.0, 990.0, 5.0, max_stake, leverage, None, "long")
            assert 0 <= stake <= max_stake
            assert stake * leverage <= 1000
            assert stake * leverage * strategy.planned_loss_fraction <= 20
    assert strategy.custom_stake_amount("BTC/USDT:USDT", datetime.now(UTC), 60000.0, 990.0, 300.0, 1000.0, 2.0, None, "long") == 0


def test_confirmation_rejects_oversized_or_invalid_orders():
    strategy = make_strategy()
    def confirm(amount, rate, pair="BTC/USDT:USDT"):
        return strategy.confirm_trade_entry(pair, "market", amount, rate, "GTC", datetime.now(UTC), None, "long")
    assert confirm(0.005, 60000)
    assert not confirm(0.02, 60000)
    assert not confirm(-1, 60000)
    assert not confirm(0.001, math.nan)
    assert not confirm(0.001, 60000, "ETH/USDT:USDT")


def test_leverage_is_capped():
    strategy = make_strategy()
    assert strategy.leverage("BTC/USDT:USDT", datetime.now(UTC), 60000, 10, 100, None, "long") == 2
    assert strategy.leverage("BTC/USDT:USDT", datetime.now(UTC), 60000, 10, 1, None, "long") == 1


def test_custom_exit_at_six_hours_only():
    strategy = make_strategy()
    opened = datetime(2026, 10, 1, tzinfo=UTC)
    trade = SimpleNamespace(open_date_utc=opened)
    assert strategy.custom_exit("BTC/USDT:USDT", trade, opened + timedelta(hours=5), 60000, -0.01) is None
    assert strategy.custom_exit("BTC/USDT:USDT", trade, opened + timedelta(hours=6), 60000, -0.01) == "smoke_time_exit_6h"
