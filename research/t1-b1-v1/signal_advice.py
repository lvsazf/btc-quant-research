"""Read-only advice projection. No position sizing, new signal rule or order client."""
import hashlib
import math
import json
from pathlib import Path
from datetime import datetime, timezone

H = 3600000

def ms(value):
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Non-finite timestamp')
        return int(value)
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return int(d.timestamp() * 1000)

def utc(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()

def identity(task_id, name, action, trigger):
    return hashlib.sha256(f'{task_id}|{name}|{action}|{trigger}'.encode()).hexdigest()[:24]

def quote(ticker, metadata, asof):
    if metadata.get('http_status') != 200 or ticker.get('code') != '00000' or metadata.get('code') != '00000':
        raise ValueError('Invalid ticker response evidence')
    if len(ticker.get('data', [])) != 1:
        raise ValueError('Ambiguous ticker')
    t = ticker['data'][0]
    if t.get('symbol') != 'BTCUSDT':
        raise ValueError('Wrong ticker instrument')
    p = float(t['lastPr']); stamp = ms(int(t['ts'])); checked = ms(asof)
    if not math.isfinite(p) or p <= 0:
        raise ValueError('Invalid reference price')
    if not -2000 <= checked - stamp <= 60000:
        raise ValueError('Stale or future reference quote')
    received = ms(metadata['received_utc'])
    if not -2000 <= checked - received <= 60000:
        raise ValueError('Stale or future quote receipt')
    return dict(reference_price=p, quote_time_utc=utc(stamp), quote_received_utc=utc(received),
                quote_source=metadata['url'], price_kind='OBSERVED_TICKER_REFERENCE_NOT_FILL')

def build_advice(signals, ticker, metadata, asof, task_id, previous=None, checkpoint=None):
    """Previous is the verified previous COMPLETE archive's original decision only.

    Event IDs describe signals, not deliveries. Never mark a message sent here.
    Older interval events remain historical, not invitations at the current quote.
    """
    q = quote(ticker, metadata, asof)
    output = dict(version='SIGNAL_ADVICE_V1_20261019', scope='SIGNAL_ADVICE_FOR_MANUAL_DECISION',
                  asof_utc=asof, strategies={}, orders_enabled=False,
                  notification_policy='EVERY_ROUND; repeated event IDs require original notification receipt reconciliation; unknown delivery is not retried blindly')
    prevsignals = (previous or {}).get('signals', {})
    prevadvice = (previous or {}).get('signal_advice', {}).get('strategies', {})
    for name in ('T1', 'B1', 'ST'):
        s = signals.get(name)
        if s is None:
            output['strategies'][name] = dict(status='DATA_ERROR', action='UNAVAILABLE', events=[], reason='Strategy result missing')
            continue
        try:
            st = name == 'ST'
            target = s.get('desired_state') if st else s.get('target_state')
            prior = s.get('previous_state') if st else s.get('previous_target_state')
            event = s.get('event'); cut = ms(s['signal_available_utc'])
            if cut % H or not 0 <= ms(asof) - cut < H:
                raise ValueError('Closed signal boundary not current to this sample')
            if target not in ('LONG', 'CASH'):
                raise ValueError('Unknown target state')
            old = prevsignals.get(name)
            oldcut = ms(old['signal_available_utc']) if old else None
            if oldcut is not None and oldcut > cut:
                raise ValueError('Previous observation is later than current')
            if oldcut is not None and oldcut == cut - H:
                oldtarget = old.get('desired_state') if st else old.get('target_state')
                if oldtarget != prior:
                    raise ValueError('Adjacent original observation state conflict')
            initialized = event in ('INITIALIZED', 'INITIALIZED_LONG', 'INITIALIZED_CASH')
            row = dict(status='OK', action=('INITIALIZED_' if initialized else 'MAINTAIN_') + target,
                       target_state=target, new_action=False, events=[], repeated_event_ids=[],
                       signal_boundary_utc=utc(cut), observation_gap=False,
                       reason='Initialization is not a new trade' if initialized else 'No new entry or exit; strategy target continues')
            events = []
            if st:
                orders = s.get('incremental_orders', [])
                if initialized:
                    if prior is not None or orders:
                        raise ValueError('Invalid ST initialization')
                else:
                    expected = 'WAIT' if not orders else ('ENTER' if orders[0].get('side') == 'buy' else 'EXIT') if len(orders) == 1 else 'TRANSITIONS'
                    if event != expected or prior not in ('LONG', 'CASH'):
                        raise ValueError('Inconsistent ST event')
                    state = prior; laststamp = None
                    for order in orders:
                        side = order.get('side'); ts = ms(order['ts']); why = order.get('reason')
                        if side not in ('buy', 'sell') or (side == 'buy') != (state == 'CASH'):
                            raise ValueError('Invalid ST event order/state')
                        if ts > cut or (laststamp is not None and ts < laststamp):
                            raise ValueError('Invalid ST event chronology')
                        state = 'LONG' if side == 'buy' else 'CASH'; laststamp = ts
                        intrabar = why == 'STOP_INTRABAR'
                        trigger = None if intrabar else ms(order.get('signal_time') or ts)
                        if trigger is not None and trigger > ts:
                            raise ValueError('ST signal occurs after its recorded event')
                        if why not in ('ENTRY', 'SIGNAL_EXIT', 'STOP_GAP', 'STOP_INTRABAR') or (side == 'buy') != (why == 'ENTRY'):
                            raise ValueError('Unrecognized ST event reason')
                        interval_start = ts // H * H if intrabar else None
                        current = (interval_start + H == cut) if intrabar else (ts == cut)
                        events.append(dict(action='BUY_LONG' if side == 'buy' else 'SELL_CLOSE_LONG',
                                           signal_time_utc=None if intrabar else utc(trigger),
                                           signal_interval_start_utc=utc(interval_start) if intrabar else None,
                                           signal_interval_end_utc=utc(interval_start + H) if intrabar else None,
                                           reason=why, event_id=identity(task_id, name, side, ts),
                                           current_interval=current, event_status='CURRENT' if current else 'HISTORICAL_CATCHUP'))
                    if state != target:
                        raise ValueError('ST final target/event mismatch')
            else:
                expected = 'ENTER_LONG_TRANSITION' if prior == 'CASH' and target == 'LONG' else 'EXIT_LONG_TRANSITION' if prior == 'LONG' and target == 'CASH' else 'WAIT'
                if not initialized and (prior not in ('LONG', 'CASH') or event != expected):
                    raise ValueError('Inconsistent daily event/state')
                basis = ms(s['basis_daily_close_ms'])
                if basis % (24 * H) or basis > cut:
                    raise ValueError('Invalid daily signal boundary')
                # A skipped daily boundary cannot be called proven no-change coverage.
                if oldcut is not None and oldcut < basis < cut:
                    row.update(status='OBSERVATION_GAP', action='REVIEW_MISSED_INTERVAL', observation_gap=True,
                               reason='Daily boundary was not observed here; current target is known but missed transitions are not certified')
                if not initialized and event != 'WAIT':
                    if basis != cut:
                        raise ValueError('Daily transition does not match its completed daily boundary')
                    action = 'BUY_LONG' if target == 'LONG' else 'SELL_CLOSE_LONG'
                    events.append(dict(action=action, signal_time_utc=utc(basis), reason=s.get('indicators', {}),
                                       event_id=identity(task_id, name, action, basis), current_interval=True, event_status='CURRENT'))
            # A first ST initialization never outputs its reconstructed orders. A missed
            # past event remains recorded but cannot become a fresh buy at today's quote.
            oldids = {e['event_id'] for e in prevadvice.get(name, {}).get('events', [])}
            for i, e in enumerate(events):
                if i < len(events) - 1 and e['current_interval']:
                    e['event_status'] = 'SUPERSEDED_IN_INTERVAL'
                repeated = e['event_id'] in oldids or (oldcut is not None and oldcut == cut)
                if repeated:
                    e['event_status'] = 'REPEATED_RECONCILE_ORIGINAL_NOTIFICATION'
                    row['repeated_event_ids'].append(e['event_id'])
                if e['event_status'] == 'CURRENT':
                    e.update(q)
                    e['suggested_fraction'] = fraction(name, e, s, checkpoint)
                    row.update(action=e['action'], new_action=True, reason='New strategy signal; reference quote is sampled now, not a fill')
            row['events'] = events
            if events and not row['new_action'] and not row['repeated_event_ids']:
                row.update(status='HISTORICAL_EVENTS_ONLY', reason='Only past interval events reconstructed; not a new current-price action')
            output['strategies'][name] = row
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            output['strategies'][name] = dict(status='DATA_ERROR', action='UNAVAILABLE', new_action=False, events=[], reason=str(error))
    for row in output['strategies'].values():
        row['presentation'] = presentation(row)
    return output


def fraction(name, event, signal, checkpoint):
    """Existing frozen allocation only; no account amount or new sizing rule."""
    if event['action'] == 'SELL_CLOSE_LONG':
        return dict(value=1.0, basis='EXISTING_STRATEGY_POSITION', meaning='Exit all of this strategy position, not open a short')
    if name in ('T1', 'B1'):
        return dict(value=.9, basis='STRATEGY_AVAILABLE_CASH_FEE_INCLUSIVE_CAP', meaning='Frozen research entry spending cap; rounding can make actual fraction lower; not total personal assets')
    p = ((checkpoint or {}).get('ledger') or {}).get('position')
    orders = signal.get('incremental_orders', [])
    order = orders[-1] if orders else None
    if p and order and order.get('side') == 'buy':
        pairs = [('entry_time', 'ts'), ('q', 'q'), ('entry_fill', 'fill'), ('entry_fee', 'fee')]
        if all(p.get(a) == order.get(b) and p.get(a) is not None for a, b in pairs):
            equity = float(p['initial_equity'])
            spent = float(order['q']) * float(order['fill']) + float(order['fee'])
            if math.isfinite(equity) and equity > 0 and math.isfinite(spent) and 0 < spent <= .9 * equity + 1e-8:
                return dict(value=spent/equity, basis='RESEARCH_ENTRY_PRETRADE_EQUITY_FEE_INCLUSIVE', meaning='Original new research entry spending divided by its pre-entry equity; not recalculated at ticker and not personal account allocation')
    return dict(value=None, basis='NOT_CALCULATED', meaning='Matching explicit pre-entry research equity unavailable; no inferred allocation')


def read_previous_decision(previous):
    """Use immutable archived decision, not a mutable local display or delivery flag."""
    if previous is None:
        return None
    archive = Path(previous['path']).parent.parent / 'google-evidence.json'
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != previous['archive_sha256']:
        raise ValueError('Previous advice archive hash mismatch')
    package = json.loads(raw)
    if package['round_id'] != previous['round_id']:
        raise ValueError('Previous advice round identity mismatch')
    entry = package['files']['decision.json']; content = entry['content'].encode()
    if len(content) != entry['bytes'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
        raise ValueError('Previous archived decision digest mismatch')
    return json.loads(content)


def presentation(row):
    """Display-only projection; retain source fields and never infer account holdings.

    Exceptional coverage / delivery states take precedence over terminal MAINTAIN.
    Event sequence preserves source order, including superseded and past events.
    """
    target = row.get('target_state')
    events = row.get('events', [])
    result = dict(version='ADVICE_DISPLAY_V1_20261019', account_state_known=False,
                  target_text={'LONG':'策略目标：持仓', 'CASH':'策略目标：空仓'}.get(target, '策略目标：无法确认'),
                  event_sequence=[{k:e[k] for k in ('event_id', 'action', 'event_status', 'reason',
                    'signal_time_utc', 'signal_interval_start_utc', 'signal_interval_end_utc') if k in e} for e in events])
    status = row.get('status')
    if status == 'DATA_ERROR':
        kind, text = 'DATA_ERROR', '数据异常，暂不能给出交易建议'
    elif status == 'OBSERVATION_GAP' or row.get('observation_gap') or row.get('action') == 'REVIEW_MISSED_INTERVAL':
        kind, text = 'OBSERVATION_GAP', '存在漏窗，期间交易变化待核，不能视为正常延续'
    elif row.get('repeated_event_ids') or any(e.get('event_status') == 'REPEATED_RECONCILE_ORIGINAL_NOTIFICATION' for e in events):
        kind, text = 'REPEATED_RECONCILE_ORIGINAL_NOTIFICATION', '重复信号，原通知状态待核，不重复给出买卖建议'
    elif status == 'HISTORICAL_EVENTS_ONLY':
        kind, text = 'HISTORICAL_EVENTS_ONLY', '存在历史补算交易变化，不作为当前新增买卖建议'
    elif row.get('new_action') and events and events[-1].get('event_status') == 'CURRENT':
        kind = events[-1]['action']
        text = {'BUY_LONG':'建议买入做多', 'SELL_CLOSE_LONG':'建议卖出平多'}.get(kind)
        if text is None:
            kind, text = 'DATA_ERROR', '动作异常，暂不能给出交易建议'
    elif str(row.get('action','')).startswith('INITIALIZED_') and not events:
        kind, text = 'INITIALIZED', '研究账本初始化，不是本轮新买入或卖出'
    elif status == 'OK' and not events and row.get('action') in ('MAINTAIN_LONG','MAINTAIN_CASH') and not row.get('new_action'):
        kind, text = 'NO_NEW_ACTION', '本轮无新增买卖建议'
    else:
        kind, text = 'REVIEW_EVENTS', '存在待核事件，不能仅按最终状态给出维持建议'
    result.update(kind=kind, action_text=text)
    return result
