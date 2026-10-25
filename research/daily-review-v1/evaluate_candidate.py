"""Minimum offline executable candidate path: unchanged ST identity engineering check.

No new signal, tuning, strategy parameters, adoption, or account access. Reuses
approved ST indicator and economic functions. This is a finite-window liquidation
engineering fixture, NOT the hourly continuous ledger and NOT an economic test.
Arbitrary external candidate code is deliberately unsupported.
"""
import argparse
import copy
import datetime as dt
import importlib.util
from pathlib import Path
import sys

import candidate_registry as registry

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 't1-b1-v1'
RUNTIME_FILES = ('st_indicators.py', 'st_signals.py', 'st_engine.py', 'st_original_protocol.json')
H = 3600000


def millis(value):
    result = registry.timestamp(value).timestamp() * 1000
    if result % H:
        raise ValueError('window timestamps must be whole UTC hours')
    return int(result)


def verify_authorized_st_sources():
    """Check the existing authorized lock, not newly self-signed current sources.

    Only ST economic/signal files are in this subset. The outer daily task owns
    full environment/dependency verification; this does not claim that broader
    verification or rewrite the runtime manifest.
    """
    manifest_path = RUNTIME / 'runtime_manifest.json'
    manifest = registry.read_json(manifest_path)
    if str(RUNTIME) != manifest['paths']['absolute_root']:
        raise ValueError('authorized runtime root mismatch')
    locked = manifest['files']
    verified = {}
    for name in RUNTIME_FILES + ('st_protocol.json',):
        if name not in locked or registry.sha256_file(RUNTIME / name) != locked[name]:
            raise ValueError('authorized ST locked hash missing or changed: ' + name)
        verified[name] = locked[name]
    parent = registry.read_json(RUNTIME / 'st_protocol.json')
    if manifest.get('st_research') != parent:
        raise ValueError('authorized manifest ST parent identity mismatch')
    return {'status': 'AUTHORIZED_ST_FILE_SUBSET_VERIFIED',
            'manifest_sha256': registry.sha256_file(manifest_path),
            'runtime_lock_version': manifest['runtime_lock_version'],
            'parent_version': parent['version'], 'verified_files': verified,
            'scope': 'ST economic/signal file lock only, not full runtime/dependency certification.'}


def identity_contract():
    verify_authorized_st_sources()
    parent = registry.read_json(RUNTIME / 'st_protocol.json')
    original = registry.read_json(RUNTIME / 'st_original_protocol.json')
    if registry.sha256_file(RUNTIME / 'st_original_protocol.json') != parent['source_protocol_sha256']:
        raise ValueError('original ST protocol hash mismatch')
    if parent['strategy'] != 'ST-H1-LO-v1' or original['version'] != 'PUBLIC_H1_FIXED_TWO_V1':
        raise ValueError('unsupported frozen ST parent')
    if set(original['scenarios']) != {'base', 'slip5bp', 'delay1h', 'both'}:
        raise ValueError('expected the original four stress scenarios')
    risk = 'ST_FROZEN_RISK:protocol-sha256:' + parent['source_protocol_sha256']
    cost = 'ST_ACTUAL_FUNDING_MARK:protocol-sha256:' + parent['source_protocol_sha256']
    return parent, original, risk, cost


def read_inputs(path):
    data = registry.read_json(path)
    required = {'bars', 'funding', 'marks', 'diagnostic_seen_history'}
    allowed = required | {'ledger_bars', 'states', 'protocol'}
    if not isinstance(data, dict) or not required <= data.keys() or data.keys() - allowed:
        raise ValueError('inputs require the known daily-review bars/funding/marks/seen contract')
    if data['diagnostic_seen_history'] is not True:
        raise ValueError('existing input history must remain explicitly seen diagnostic data')
    if not isinstance(data['bars'], list) or not data['bars']:
        raise ValueError('nonempty closed bars required')
    for i, bar in enumerate(data['bars']):
        if type(bar.get('ts')) is not int or bar['ts'] % H:
            raise ValueError('invalid hourly bar timestamp')
        if i and bar['ts'] != data['bars'][i - 1]['ts'] + H:
            raise ValueError('noncontiguous full prehistory')
        for key in ('open', 'high', 'low', 'close'):
            registry.finite_number(bar.get(key), 'bar ' + key)
            if bar[key] <= 0:
                raise ValueError('positive bar prices required')
        if bar['high'] < max(bar['open'], bar['low'], bar['close']) or bar['low'] > min(bar['open'], bar['high'], bar['close']):
            raise ValueError('invalid OHLC bounds')
    funding, marks = {}, {}
    for key, value in data['funding'].items():
        if str(int(key)) != key or int(key) % (8 * H):
            raise ValueError('funding timestamps must be canonical 8h UTC boundaries')
        registry.finite_number(value, 'funding rate')
        funding[int(key)] = value
    for key, value in data['marks'].items():
        if str(int(key)) != key or int(key) % H or not isinstance(value, dict):
            raise ValueError('invalid hourly mark timestamp or data')
        marks[int(key)] = value
    return data, funding, marks


def freeze_identity_protocol(inputs, output_protocol, version, start_utc, end_utc):
    """Freeze one caller-selected engineering window BEFORE executing results."""
    inputs, output_protocol = Path(inputs).resolve(), Path(output_protocol).resolve()
    if output_protocol.exists():
        raise ValueError('protocol already exists; preserve previous declaration')
    data, _, _ = read_inputs(inputs)
    parent, original, risk, cost = identity_contract()
    if millis(start_utc) >= millis(end_utc):
        raise ValueError('invalid engineering window')
    if millis(start_utc) < data['bars'][0]['ts'] or millis(end_utc) > data['bars'][-1]['ts'] + H:
        raise ValueError('engineering window outside verified closed bars')
    cells = [dict(window='PREDECLARED_ENGINEERING_WINDOW', start_utc=start_utc, end_utc=end_utc,
                  scenario=name, cost_layer='actual', fee_each_side=original['fee_each_side'],
                  slippage_each_side=slip, delay_hours=delay)
             for name, (slip, delay) in original['scenarios'].items()]
    frozen = registry.now_utc()
    protocol = {'schema_version': 1, 'version': version, 'frozen_utc': frozen,
                'registration_timing': 'pre_result_declaration',
                'parent': {'version': parent['version'], 'identity': registry.file_ref(RUNTIME / 'st_protocol.json'),
                           'source_hashes': [registry.file_ref(RUNTIME / name) for name in RUNTIME_FILES]},
                'candidate_sources': [registry.file_ref(Path(__file__)), registry.file_ref(HERE / 'candidate_registry.py')],
                'inputs': [registry.file_ref(inputs)],
                'hypothesis': 'Engineering identity only: unchanged ST signal and risk must exactly reproduce the frozen ST parent under every original declared cost scenario.',
                'supporting_evidence': [registry.file_ref(RUNTIME / 'st_protocol.json')],
                'falsification': 'Any candidate/parent ledger mismatch fails this engineering identity check. Equality does not establish economic value.',
                'history': {'classification': 'seen_diagnostic',
                            'latest_seen_utc': dt.datetime.fromtimestamp((data['bars'][-1]['ts'] + H) / 1000, dt.timezone.utc).isoformat()},
                'comparison': {'purpose': 'engineering_identity', 'parent_baseline_name': parent['strategy'],
                               'risk_model': risk, 'cost_model': cost,
                               'required_baselines': [parent['strategy'], 'CASH', 'HOLD'],
                               'same_risk_baselines': [parent['strategy']], 'cells': cells},
                'validation_plan': registry.pending_plan(), 'adopted': False}
    registry.validate_protocol(protocol, output_protocol.parent, frozen)
    output_protocol.parent.mkdir(parents=True, exist_ok=True)
    registry.write_json(output_protocol, protocol)
    return protocol


def load_audited_runtime():
    """Freshly load ONLY fixed audited files, with no arbitrary candidate import."""
    verify_authorized_st_sources()
    saved = {name: sys.modules.get(name) for name in ('st_indicators', 'st_signals', 'st_engine')}
    loaded = {}
    try:
        for name in saved:
            spec = importlib.util.spec_from_file_location(name, RUNTIME / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
        return loaded['st_engine'], loaded['st_signals']
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def evaluate(protocol_path, inputs_path, inputs_sha256, output):
    protocol_path, inputs_path, output = Path(protocol_path).resolve(), Path(inputs_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('output already exists; preserve prior attempts')
    if registry.sha256_file(inputs_path) != inputs_sha256:
        raise ValueError('input argument hash mismatch')
    protocol = registry.read_json(protocol_path)
    registry.validate_protocol(protocol, protocol_path.parent, registry.now_utc())
    parent, original, risk, cost = identity_contract()
    spec = protocol['comparison']
    if spec['purpose'] != 'engineering_identity':
        raise ValueError('only unchanged ST identity engineering evaluation is supported')
    expected_sources = [registry.file_ref(RUNTIME / name) for name in RUNTIME_FILES]
    expected_candidate = [registry.file_ref(Path(__file__)), registry.file_ref(HERE / 'candidate_registry.py')]
    if protocol['parent'] != {'version': parent['version'], 'identity': registry.file_ref(RUNTIME / 'st_protocol.json'), 'source_hashes': expected_sources}:
        raise ValueError('exact frozen parent version/source/identity mismatch')
    if protocol['candidate_sources'] != expected_candidate or protocol['inputs'] != [registry.file_ref(inputs_path)]:
        raise ValueError('exact evaluator source/input identity mismatch')
    if spec['parent_baseline_name'] != parent['strategy'] or spec['required_baselines'] != [parent['strategy'], 'CASH', 'HOLD'] or spec['same_risk_baselines'] != [parent['strategy']]:
        raise ValueError('identity comparison requires frozen ST parent plus CASH/HOLD')
    if spec['risk_model'] != risk or spec['cost_model'] != cost:
        raise ValueError('undeclared risk or cost model change')
    cells = spec['cells']
    if len(cells) != 4 or {cell['scenario'] for cell in cells} != set(original['scenarios']):
        raise ValueError('all four original predeclared stress scenarios are required')
    windows = {(cell['window'], cell['start_utc'], cell['end_utc']) for cell in cells}
    if len(windows) != 1:
        raise ValueError('one exact same-window engineering fixture is required')
    for cell in cells:
        slip, delay = original['scenarios'][cell['scenario']]
        if cell['cost_layer'] != 'actual' or cell['fee_each_side'] != original['fee_each_side'] or cell['slippage_each_side'] != slip or cell['delay_hours'] != delay:
            raise ValueError('original frozen costs and stresses cannot change')
    data, funding, marks = read_inputs(inputs_path)
    start, end = millis(cells[0]['start_utc']), millis(cells[0]['end_utc'])
    # Whole supplied prehistory up to this window; never use bars after its end.
    prehistory = [bar for bar in data['bars'] if bar['ts'] < end]
    bars = [bar for bar in prehistory if bar['ts'] >= start]
    if not bars or bars[0]['ts'] != start or bars[-1]['ts'] + H != end:
        raise ValueError('incomplete engineering window')
    for t in range(start, end + 1, H):
        if t % (8 * H) == 0 and t not in funding:
            raise ValueError('missing required actual funding; never zero-fill')
        if t < end:
            for key in ('open', 'close'):
                if t not in marks or key not in marks[t]:
                    raise ValueError('missing required actual hourly mark')
                registry.finite_number(marks[t][key], 'mark ' + key)
                if marks[t][key] <= 0:
                    raise ValueError('positive marks required')
        elif t in funding:
            if t not in marks or 'open' not in marks[t]:
                raise ValueError('missing terminal settlement mark open')
            registry.finite_number(marks[t]['open'], 'terminal mark open')
            if marks[t]['open'] <= 0:
                raise ValueError('positive terminal mark required')
    authority = verify_authorized_st_sources()
    engine, signals = load_audited_runtime()
    if engine.FEE != original['fee_each_side']:
        raise ValueError('engine fee differs from original protocol')
    features = signals.features(prehistory)
    candidate_features = copy.deepcopy(features)  # The sole supported candidate adapter is identity.
    output.mkdir(parents=True)
    (output / 'runs').mkdir()
    receipt = registry.register_candidate(protocol_path, output / 'registry')
    registry.write_json(output / 'runtime_authority.json', authority)
    registry.write_json(output / 'started.json', {'status': 'STARTED_ENGINEERING_IDENTITY', 'adopted': False})
    rows, comparisons = [], []
    try:
        for cell in cells:
            runs = {}
            for name, strategy, signal in ((protocol['version'], 'A', candidate_features),
                                           (parent['strategy'], 'A', features), ('CASH', 'CASH', features), ('HOLD', 'HOLD', features)):
                result = engine.simulate(bars, signal, strategy, funding, marks,
                                         slip=cell['slippage_each_side'], delay=cell['delay_hours'])
                summary, curve, orders, funding_log, trades = result
                runs[name] = result
                path = output / 'runs' / (cell['scenario'] + '__' + name + '.json')
                registry.write_json(path, {'summary': summary, 'curve': curve, 'orders': orders,
                                          'funding': funding_log, 'trades': trades,
                                          'terminal_liquidation': True, 'engineering_only': True})
                rows.append(dict(cell, name=name,
                                 risk_model=risk if name in (protocol['version'], parent['strategy']) else 'CONTEXT_ONLY_NOT_SAME_RISK',
                                 cost_model=cost, **{key: summary[key] for key in ('status', 'pnl', 'return_pct', 'max_drawdown_pct', 'completed_nonterminal_trades')}))
            equal = runs[protocol['version']] == runs[parent['strategy']]
            comparisons.append({'scenario': cell['scenario'], 'all_summary_and_ledger_fields_equal': equal})
            if not equal:
                raise ValueError('identity candidate differs from exact parent ledger')
        result = {'schema_version': 1, 'candidate_version': protocol['version'], 'protocol_sha256': receipt['protocol_sha256'],
                  'parent_version': protocol['parent']['version'], 'parent_source_hashes': protocol['parent']['source_hashes'],
                  'candidate_source_hashes': protocol['candidate_sources'], 'input_hashes': protocol['inputs'],
                  'history_classification': 'seen_diagnostic', 'source_artifacts': [registry.file_ref(output / 'runtime_authority.json')] + [registry.file_ref(path) for path in sorted((output / 'runs').glob('*.json'))],
                  'historical_screen': {'status': 'NOT_RUN_ENGINEERING_IDENTITY_ONLY', 'performance_screen_pass': None}, 'rows': rows}
        registry.write_json(output / 'comparison.json', result)
        ingestion = registry.ingest_comparison(output / 'registry' / protocol['version'], output / 'comparison.json')
        report = dict(ingestion, status='COMPLETE_ENGINEERING_IDENTITY_NOT_ECONOMIC_VALIDATION',
                      identity_exact_all_scenarios=all(item['all_summary_and_ledger_fields_equal'] for item in comparisons),
                      scenario_count=len(cells), identity_checks=comparisons,
                      terminal_liquidation=True, hourly_continuous_ledger=False, runtime_authority=authority,
                      economic_interpretation='No optimization, no economic threshold test, no unseen holdout, no adoption; identical behavior is only an engineering control.')
        registry.write_json(output / 'report.json', report)
        registry.write_json(output / 'completion.json', {'status': report['status'], 'completed_utc': registry.now_utc(),
                                                       'report_sha256': registry.sha256_file(output / 'report.json'),
                                                       'comparison_sha256': registry.sha256_file(output / 'comparison.json'),
                                                       'economically_validated': False, 'adopted': False})
        return report
    except Exception as error:
        registry.write_json(output / 'failure.json', {'status': 'FAILED_ENGINEERING_IDENTITY', 'error': str(error), 'adopted': False})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--freeze-identity', action='store_true', help='Write protocol only; does not evaluate results')
    parser.add_argument('--version')
    parser.add_argument('--start-utc')
    parser.add_argument('--end-utc')
    args = parser.parse_args(argv)
    try:
        if registry.sha256_file(args.inputs) != args.inputs_sha256:
            raise ValueError('input argument hash mismatch')
        if args.freeze_identity:
            if not all((args.version, args.start_utc, args.end_utc)) or args.output is not None:
                raise ValueError('freeze requires version/start-utc/end-utc and no output directory')
            result = freeze_identity_protocol(args.inputs, args.protocol, args.version, args.start_utc, args.end_utc)
        else:
            if args.output is None:
                raise ValueError('evaluation requires --output NEW_DIRECTORY')
            result = evaluate(args.protocol, args.inputs, args.inputs_sha256, args.output)
        import json
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        import json
        print(json.dumps({'status': 'BLOCKED_OR_FAILED_ENGINEERING_EVALUATION', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
