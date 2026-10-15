"""Prepare an explicitly labelled, seven-day public-data plumbing fixture."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from freqtrade.data.history.datahandlers.jsondatahandler import JsonDataHandler
from freqtrade.enums import CandleType

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/workspace/shared/btc-quant-research-20261010/data')
PAIR = 'BTC/USDT:USDT'
LO = pd.Timestamp('2026-09-30T00:00:00Z')
HI = pd.Timestamp('2026-10-08T00:00:00Z')
sources = {
    'futures': SOURCE / 'ohlcv_1h.csv',
    'mark': SOURCE / 'btcusdt_usdt_futures_mark_1h_funding_window.csv',
    'funding_rate': SOURCE / 'btcusdt_usdt_futures_funding.csv',
}
manifest = {'purpose': 'Installation and custom-hook smoke test, NOT strategy validation or advice',
            'window': ['2026-10-01T00:00:00Z', '2026-10-08T00:00:00Z'],
            'sources': {}, 'scenarios': {
                'gross': 'Explicit no-cost ablation: fee=0 and funding cashflows intentionally zeroed; not claimed historical funding data',
                'net': 'Fee assumption 0.0006 per side + actual historical funding rates times hourly mark-open proxy; NO spread/slippage/notification delay',
            }}
frames = {}
for name, path in sources.items():
    frame = pd.read_csv(path)
    frame['date'] = pd.to_datetime(frame.pop('ts'), unit='ms', utc=True)
    frame = frame[(frame.date >= LO) & (frame.date <= HI)].copy().sort_values('date')
    assert not frame.date.duplicated().any()
    if name == 'funding_rate':
        frame = frame.rename(columns={'fundingRate': 'funding_rate'})[['date', 'funding_rate']]
        assert len(frame) == 25 and frame.date.diff().dropna().eq(pd.Timedelta(hours=8)).all()
    else:
        if 'volume' not in frame:
            frame['volume'] = 0.0  # Mark-price series does not have traded volume.
        frame = frame[['date', 'open', 'high', 'low', 'close', 'volume']]
        assert len(frame) == 193 and frame.date.diff().dropna().eq(pd.Timedelta(hours=1)).all()
        assert (frame.low <= frame[['open', 'close']].min(axis=1)).all()
        assert (frame.high >= frame[['open', 'close']].max(axis=1)).all()
    frames[name] = frame
    manifest['sources'][name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'rows_in_fixture': len(frame), 'first': str(frame.date.min()), 'last': str(frame.date.max())}
assert set(frames['funding_rate'].date).issubset(set(frames['mark'].date))
for scenario in ('gross', 'net'):
    directory = ROOT / 'user_data/data' / scenario
    directory.mkdir(parents=True, exist_ok=True)
    handler = JsonDataHandler(directory)
    for name, frame in frames.items():
        data = frame.copy()
        if scenario == 'gross' and name == 'funding_rate':
            data['funding_rate'] = 0.0
        handler.ohlcv_store(PAIR, '1h', data, CandleType(name))
    config = {
        'max_open_trades': 1, 'stake_currency': 'USDT', 'stake_amount': 200,
        'dry_run_wallet': 1000, 'tradable_balance_ratio': 0.99,
        'dry_run': True, 'trading_mode': 'futures', 'margin_mode': 'isolated',
        'timeframe': '1h', 'strategy': 'SmokeHourlyResearch',
        'user_data_dir': str(ROOT / 'user_data'), 'datadir': str(directory),
        'dataformat_ohlcv': 'json', 'fee': 0.0 if scenario == 'gross' else 0.0006,
        'entry_pricing': {'price_side': 'other', 'use_order_book': False},
        'exit_pricing': {'price_side': 'other', 'use_order_book': False},
        'unfilledtimeout': {'entry': 10, 'exit': 10, 'unit': 'minutes'},
        'exchange': {'name': 'bitget', 'key': '', 'api_key': '', 'secret': '', 'password': '',
                     'ccxt_config': {'timeout': 10000},
                     'ccxt_async_config': {'timeout': 10000, 'aiohttp_trust_env': True,
                                           'options': {'include_OS_certificates': True}},
                     'pair_whitelist': [PAIR], 'pair_blacklist': [], 'enable_ws': False},
        'pairlists': [{'method': 'StaticPairList'}],
        'telegram': {'enabled': False, 'token': '', 'chat_id': ''},
        'force_entry_enable': False,
    }
    (ROOT / f'config-{scenario}.json').write_text(json.dumps(config, indent=2) + '\n')
(ROOT / 'fixture-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
