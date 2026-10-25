"""Offline, append-only research evidence registry; never executes strategy code.

Registering/ingesting evidence is NOT economic validation, adoption, or a live
execution decision. Seen history remains diagnostic. The public-v1 adapter reads
existing outputs only; it does not simulate, tune, or invent forward thresholds.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = 1
CELL_FIELDS = ('window', 'start_utc', 'end_utc', 'scenario', 'cost_layer',
               'fee_each_side', 'slippage_each_side', 'delay_hours')
PLAN_FIELDS = ('forward_start_utc', 'forward_end_utc', 'minimum_duration_days',
               'minimum_natural_exits', 'acceptance_criteria', 'falsification_criteria')
PROTOCOL_FIELDS = ('schema_version', 'version', 'frozen_utc', 'registration_timing',
                   'parent', 'candidate_sources', 'inputs', 'hypothesis',
                   'supporting_evidence', 'falsification', 'history', 'comparison',
                   'validation_plan', 'adopted')
RESULT_FIELDS = ('schema_version', 'candidate_version', 'protocol_sha256', 'parent_version',
                 'parent_source_hashes', 'candidate_source_hashes', 'input_hashes',
                 'history_classification', 'source_artifacts', 'historical_screen', 'rows')
ROW_FIELDS = CELL_FIELDS + ('name', 'risk_model', 'cost_model', 'status', 'pnl',
                           'return_pct', 'max_drawdown_pct', 'completed_nonterminal_trades')


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('non-finite JSON value: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def require_fields(value, fields, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    missing, unknown = set(fields) - value.keys(), value.keys() - set(fields)
    if missing or unknown:
        raise ValueError(f'{label}: missing {sorted(missing)}, unknown {sorted(unknown)}')


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be nonempty text')


def timestamp(value):
    nonempty(value, 'timestamp')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError('timestamps must have explicit UTC timezone')
    return parsed


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def finite_number(value, label, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + ' must be finite numeric data')
    if nonnegative and value < 0:
        raise ValueError(label + ' must be nonnegative')


def verify_refs(refs, root):
    if not isinstance(refs, list) or not refs:
        raise ValueError('artifact references must be a nonempty list')
    paths = set()
    for ref in refs:
        require_fields(ref, ('path', 'sha256'), 'artifact')
        nonempty(ref['path'], 'artifact path')
        if not isinstance(ref['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', ref['sha256']):
            raise ValueError('invalid SHA256')
        path = (Path(root) / ref['path']).resolve()
        if path in paths:
            raise ValueError('duplicate artifact path')
        paths.add(path)
        if not path.is_file() or sha256_file(path) != ref['sha256']:
            raise ValueError('artifact hash mismatch: ' + str(path))


def pending_plan():
    """Deliberately no default sample, duration, performance, or adoption threshold."""
    return dict.fromkeys(PLAN_FIELDS)


def prospective_status(protocol, registered_utc):
    plan = protocol['validation_plan']
    require_fields(plan, PLAN_FIELDS, 'validation_plan')
    missing = [field for field in PLAN_FIELDS if plan[field] is None or plan[field] == '']
    start, end = plan['forward_start_utc'], plan['forward_end_utc']
    if start is not None:
        if timestamp(start) <= max(timestamp(registered_utc), timestamp(protocol['history']['latest_seen_utc'])):
            raise ValueError('forward_start must be after registration and all declared seen data')
    if end is not None:
        timestamp(end)
        if start is not None and timestamp(end) <= timestamp(start):
            raise ValueError('forward_end must follow forward_start')
    for field in ('minimum_duration_days', 'minimum_natural_exits'):
        if plan[field] is not None and (type(plan[field]) is not int or plan[field] <= 0):
            raise ValueError(field + ' must be a positive integer or null')
    for field in ('acceptance_criteria', 'falsification_criteria'):
        if plan[field] is not None:
            nonempty(plan[field], field)
    if not missing and (timestamp(end) - timestamp(start)).total_seconds() < plan['minimum_duration_days'] * 86400:
        raise ValueError('forward window is shorter than declared minimum duration')
    return {'status': 'PENDING_PREREGISTRATION' if missing else 'DECLARED_PLAN_NOT_VALIDATED',
            'missing_fields': missing, 'plan': plan,
            'note': 'No forward results collected or evaluated; no economic validation or adoption.'}


def cell_key(cell):
    return tuple(cell[field] for field in CELL_FIELDS)


def validate_cell(cell):
    require_fields(cell, CELL_FIELDS, 'comparison cell')
    for key in ('window', 'scenario', 'cost_layer'):
        nonempty(cell[key], key)
    if timestamp(cell['start_utc']) >= timestamp(cell['end_utc']):
        raise ValueError('comparison window must have positive duration')
    for key in ('fee_each_side', 'slippage_each_side'):
        finite_number(cell[key], key, nonnegative=True)
    if type(cell['delay_hours']) is not int or cell['delay_hours'] < 0:
        raise ValueError('delay_hours must be a nonnegative integer')


def validate_protocol(protocol, root, registered_utc):
    require_fields(protocol, PROTOCOL_FIELDS, 'protocol')
    if type(protocol['schema_version']) is not int or protocol['schema_version'] != SCHEMA:
        raise ValueError('unsupported schema_version')
    if not isinstance(protocol['version'], str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', protocol['version']):
        raise ValueError('unsafe candidate version')
    if protocol['adopted'] is not False:
        raise ValueError('registry never authorizes adoption')
    if timestamp(protocol['frozen_utc']) > timestamp(registered_utc):
        raise ValueError('frozen_utc cannot be in the future')
    if protocol['registration_timing'] not in ('post_result_import', 'pre_result_declaration'):
        raise ValueError('invalid registration_timing')
    parent = protocol['parent']
    require_fields(parent, ('version', 'identity', 'source_hashes'), 'parent')
    nonempty(parent['version'], 'parent version')
    verify_refs([parent['identity']], root)
    for refs in (parent['source_hashes'], protocol['candidate_sources'], protocol['inputs'], protocol['supporting_evidence']):
        verify_refs(refs, root)
    for field in ('hypothesis', 'falsification'):
        nonempty(protocol[field], field)
    history = protocol['history']
    require_fields(history, ('classification', 'latest_seen_utc'), 'history')
    if history['classification'] not in ('seen_diagnostic', 'unverified'):
        raise ValueError('history must be seen_diagnostic or unverified; blind claims are unsupported')
    if timestamp(history['latest_seen_utc']) > timestamp(registered_utc):
        raise ValueError('latest_seen_utc cannot be in the future')
    comparison = protocol['comparison']
    require_fields(comparison, ('purpose', 'parent_baseline_name', 'risk_model', 'cost_model', 'required_baselines', 'same_risk_baselines', 'cells'), 'comparison')
    for field in ('risk_model', 'cost_model'):
        nonempty(comparison[field], field)
    for field in ('required_baselines', 'same_risk_baselines'):
        values = comparison[field]
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values) or len(set(values)) != len(values):
            raise ValueError(field + ' must be unique nonempty names')
    if comparison['purpose'] not in ('candidate_optimization', 'engineering_identity', 'historical_peer_screen'):
        raise ValueError('unsupported comparison purpose')
    parent_name = comparison['parent_baseline_name']
    if comparison['purpose'] == 'historical_peer_screen':
        if parent_name is not None or protocol['registration_timing'] != 'post_result_import':
            raise ValueError('historical peer screen is post-result, not a parent optimization comparison')
    elif not isinstance(parent_name, str) or parent_name not in comparison['required_baselines'] or parent_name not in comparison['same_risk_baselines']:
        raise ValueError('parent baseline must be explicit and included in required same-risk grid')
    if protocol['version'] in comparison['required_baselines']:

        raise ValueError('candidate cannot be its own baseline')
    if not set(comparison['same_risk_baselines']) <= set(comparison['required_baselines']):
        raise ValueError('same-risk baseline missing from required baselines')
    if not isinstance(comparison['cells'], list) or not comparison['cells']:
        raise ValueError('comparison cells are required')
    keys = set()
    for cell in comparison['cells']:
        validate_cell(cell)
        key = cell_key(cell)
        if key in keys:
            raise ValueError('duplicate comparison cell')
        keys.add(key)
    return prospective_status(protocol, registered_utc)


def register_candidate(protocol_path, registry, now=None):
    path, registry = Path(protocol_path).resolve(), Path(registry).resolve()
    protocol = read_json(path)
    registered = now or now_utc()
    prospective = validate_protocol(protocol, path.parent, registered)
    entry = registry / protocol['version']
    if entry.exists():
        raise ValueError('candidate version already exists; preserve prior registration')
    entry.mkdir(parents=True)
    (entry / 'protocol.json').write_bytes(path.read_bytes())
    receipt = {'schema_version': SCHEMA, 'version': protocol['version'], 'registered_utc': registered,
               'protocol_sha256': sha256_file(entry / 'protocol.json'), 'source_root': str(path.parent),
               'parent_version': protocol['parent']['version'], 'status': 'REGISTERED_DIAGNOSTIC_NOT_VALIDATED',
               'registration_timing': protocol['registration_timing'], 'history_classification': protocol['history']['classification'],
               'economically_validated': False, 'adopted': False, 'prospective': prospective}
    write_json(entry / 'receipt.json', receipt)
    return receipt


def load_entry(entry):
    entry = Path(entry)
    receipt, protocol = read_json(entry / 'receipt.json'), read_json(entry / 'protocol.json')
    if sha256_file(entry / 'protocol.json') != receipt['protocol_sha256']:
        raise ValueError('registered protocol hash mismatch')
    if receipt['version'] != protocol['version'] or entry.name != protocol['version']:
        raise ValueError('registered candidate version mismatch')
    validate_protocol(protocol, receipt['source_root'], receipt['registered_utc'])
    return protocol, receipt


def validate_comparison(entry, result):
    protocol, receipt = load_entry(entry)
    require_fields(result, RESULT_FIELDS, 'comparison result')
    if type(result['schema_version']) is not int or result['schema_version'] != SCHEMA:
        raise ValueError('unsupported result schema_version')
    expected = {'schema_version': SCHEMA, 'candidate_version': protocol['version'],
                'protocol_sha256': receipt['protocol_sha256'], 'parent_version': protocol['parent']['version'],
                'parent_source_hashes': protocol['parent']['source_hashes'],
                'candidate_source_hashes': protocol['candidate_sources'], 'input_hashes': protocol['inputs'],
                'history_classification': protocol['history']['classification']}
    for field, value in expected.items():
        if result[field] != value:
            raise ValueError('comparison identity mismatch: ' + field)
    verify_refs(result['source_artifacts'], receipt['source_root'])
    if not isinstance(result['historical_screen'], dict):
        raise ValueError('historical_screen must be an object; registry does not infer a pass')
    spec = protocol['comparison']
    names = [protocol['version']] + spec['required_baselines']
    expected_rows = {(name, cell_key(cell)) for name in names for cell in spec['cells']}
    seen, invalid = set(), []
    if not isinstance(result['rows'], list):
        raise ValueError('rows must be a list')
    for row in result['rows']:
        require_fields(row, ROW_FIELDS, 'comparison row')
        cell = {field: row[field] for field in CELL_FIELDS}
        validate_cell(cell)
        key = (row['name'], cell_key(cell))
        if key not in expected_rows or key in seen:
            raise ValueError('unexpected or duplicate comparison row')
        seen.add(key)
        if row['cost_model'] != spec['cost_model']:
            raise ValueError('cost_model mismatch')
        nonempty(row['risk_model'], 'risk_model')
        if row['name'] in [protocol['version']] + spec['same_risk_baselines'] and row['risk_model'] != spec['risk_model']:
            raise ValueError('risk_model mismatch for required same-risk comparison')
        if row['status'] not in ('COMPLETE', 'INVALID', 'INVALID_BORROWING', 'INVALID_NO_LEVERAGE', 'INCOMPLETE'):
            raise ValueError('unsupported result status')
        if row['status'] == 'COMPLETE':
            for metric in ('pnl', 'return_pct'):
                finite_number(row[metric], metric)
        else:
            if row['pnl'] is not None or row['return_pct'] is not None:
                raise ValueError('invalid/incomplete result pnl and return_pct must remain null')
            invalid.append({'name': row['name'], 'window': row['window'], 'scenario': row['scenario'],
                            'cost_layer': row['cost_layer'], 'status': row['status']})
        finite_number(row['max_drawdown_pct'], 'max_drawdown_pct', nonnegative=True)
        count = row['completed_nonterminal_trades']
        if type(count) is not int or count < 0:
            raise ValueError('completed_nonterminal_trades must be a nonnegative integer')
    if seen != expected_rows:
        raise ValueError(f'incomplete comparison grid: missing {len(expected_rows - seen)} rows')
    return {'status': 'COMPARISON_EVIDENCE_WITH_INVALID_RESULTS' if invalid else 'COMPARISON_EVIDENCE_COMPLETE_NOT_VALIDATED',
            'candidate_version': protocol['version'], 'parent_version': protocol['parent']['version'],
            'comparison_purpose': spec['purpose'], 'parent_baseline_name': spec['parent_baseline_name'],
            'parent_optimization_comparison': spec['purpose'] == 'candidate_optimization',
            'protocol_sha256': receipt['protocol_sha256'], 'row_count': len(seen), 'cell_count': len(spec['cells']),
            'same_risk_baselines': spec['same_risk_baselines'],
            'context_only_baselines': [name for name in spec['required_baselines'] if name not in spec['same_risk_baselines']],
            'history_classification': protocol['history']['classification'], 'invalid_results': invalid,
            'historical_screen': result['historical_screen'], 'historical_screen_source': 'Imported assertion, not recomputed by registry',
            'prospective': prospective_status(protocol, receipt['registered_utc']),
            'economically_validated': False, 'adopted': False,
            'scope': 'Hash/identity/grid/declared-risk/cost checks only; not independent ledger or causal/economic certification.'}


def ingest_comparison(entry, comparison_path):
    entry, path = Path(entry), Path(comparison_path)
    report = validate_comparison(entry, read_json(path))
    digest = sha256_file(path)
    output = entry / 'comparisons' / digest
    if output.exists():
        raise ValueError('comparison already exists; preserve prior evidence')
    output.mkdir(parents=True)
    saved = output / 'comparison.json'
    saved.write_bytes(path.read_bytes())
    report.update(comparison_sha256=digest, saved_comparison=str(saved.resolve()), ingested_utc=now_utc())
    write_json(output / 'review.json', report)
    return report


def file_ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha256_file(path)}


def import_public_research(root, registry):
    """Adapter ONLY for the already-frozen PUBLIC_H1_FIXED_TWO_V1 saved grid.

    DAILY_RISK is the matched-risk peer. T1/B1/HOLD/CASH are context, not falsely
    labelled same-risk. Original outputs and failed screening decisions survive.
    The registry protocol is made after results and never called preregistration.
    """
    root, registry = Path(root).resolve(), Path(registry).resolve()
    output = root / 'outputs/run-01'
    frozen_path = root / 'protocol_frozen.json'
    frozen = read_json(frozen_path)
    if frozen['version'] != 'PUBLIC_H1_FIXED_TWO_V1':
        raise ValueError('unsupported public research version')
    if sha256_file(frozen_path) != (root / 'protocol_frozen.sha256').read_text().strip():
        raise ValueError('public protocol hash mismatch')
    verify_refs([{'path': rel, 'sha256': digest} for rel, digest in frozen['code_hashes'].items()], root)
    if sha256_file(output / 'source_snapshot/protocol_frozen.json') != sha256_file(frozen_path):
        raise ValueError('public source snapshot protocol mismatch')
    for name in ('public_candidates.py', 'inputs.py', 'run_public.py'):
        if sha256_file(output / 'source_snapshot' / name) != frozen['code_hashes'][name]:
            raise ValueError('public source snapshot code mismatch')
    manifest = read_json(output / 'input_manifest.json')
    original_manifest_path = root / 'reference/original/outputs/run-02/input_manifest.json'
    original_manifest = read_json(original_manifest_path)
    inputs = manifest['files']
    verify_refs(inputs, root)
    if [item['sha256'] for item in inputs] != [item['sha256'] for item in original_manifest['files']]:
        raise ValueError('public and baseline input mismatch')
    parent_sources = []
    for item in original_manifest['source_files']:
        ref = {'path': str(root / 'reference/original' / Path(item['path']).name), 'sha256': item['sha256']}
        parent_sources.append(ref)
    verify_refs(parent_sources, root)
    baseline_names = ['DAILY_RISK', 'T1', 'B1', 'HOLD', 'CASH']
    original_results = read_json(root / 'reference/original/outputs/run-02/results.json')
    baselines = [row for row in original_results if row['name'] in baseline_names and row['role'] != 'research_window']
    if baselines != read_json(output / 'baselines_reused.json') or len(baselines) != 380:
        raise ValueError('public baseline reuse differs from frozen original results')
    results = read_json(output / 'results.json')
    completion = read_json(output / 'completion.json')
    if completion['status'] != 'COMPLETE_FIXED_PUBLIC_GRID' or completion['run_count'] != 152 or len(results) != 152:
        raise ValueError('incomplete public candidate grid')
    if completion['results_sha256'] != sha256_file(output / 'results.json'):
        raise ValueError('public results receipt hash mismatch')
    if timestamp(completion['completed_utc']) < timestamp(frozen['frozen_utc']):
        raise ValueError('public completion precedes declared protocol freeze')
    conclusions = read_json(output / 'conclusion.json')
    risk = 'engine-sha256:' + frozen['code_hashes']['reference/original/engine.py'] + ':DAILY_RISK_0.5pct_2ATR14'
    cost = 'public-protocol-sha256:' + sha256_file(frozen_path)
    def normalize(row):
        cell = {field: row[field] for field in CELL_FIELDS if field != 'fee_each_side'}
        cell['fee_each_side'] = frozen['fee_each_side']
        slip, delay = frozen['scenarios'][row['scenario']]
        if row['slippage_each_side'] != slip or row['delay_hours'] != delay:
            raise ValueError('public scenario cost mismatch')
        return dict(cell, name=row['name'], risk_model=risk if row['name'] in list(frozen['candidates']) + ['DAILY_RISK'] else 'CONTEXT_ONLY_NOT_SAME_RISK',
                    cost_model=cost, **{key: row[key] for key in ('status', 'pnl', 'return_pct', 'max_drawdown_pct', 'completed_nonterminal_trades')})
    baseline_rows = [normalize(row) for row in baselines]
    cells = [{key: row[key] for key in CELL_FIELDS} for row in baseline_rows if row['name'] == 'DAILY_RISK']
    if len(cells) != 76 or {cell['scenario'] for cell in cells} != set(frozen['scenarios']):
        raise ValueError('public comparison grid differs from frozen baseline grid')
    # All validations above occur before creating any registry entries.
    versions = list(frozen['candidates'])
    if set(versions) != {'ST-H1-LO-v1', 'R2-H1-LO-v1'} or set(conclusions) != set(versions):
        raise ValueError('public candidate names mismatch')
    if any((registry / version).exists() for version in versions):
        raise ValueError('candidate version already exists; preserve previous import')
    artifacts = [file_ref(output / name) for name in ('results.json', 'baselines_reused.json', 'input_manifest.json', 'completion.json', 'conclusion.json')]
    artifacts.append(file_ref(frozen_path))
    source_refs = [file_ref(root / name) for name in ('public_candidates.py', 'inputs.py', 'run_public.py')]
    generated = registry / '_public_import_inputs'
    if generated.exists():
        raise ValueError('public import input directory already exists; preserve previous attempt')
    generated.mkdir(parents=True)
    reports = []
    for version in versions:
        protocol = {'schema_version': SCHEMA, 'version': version, 'frozen_utc': now_utc(),
                    'registration_timing': 'post_result_import',
                    'parent': {'version': 'protocol-sha256:' + original_manifest['protocol_sha256'],
                               'identity': file_ref(original_manifest_path), 'source_hashes': parent_sources},
                    'candidate_sources': source_refs, 'inputs': inputs,
                    'hypothesis': frozen['candidates'][version], 'supporting_evidence': artifacts,
                    'falsification': frozen['gates'],
                    'history': {'classification': 'seen_diagnostic', 'latest_seen_utc': manifest['fixed_cutoff_utc']},
                    'comparison': {'purpose': 'historical_peer_screen', 'parent_baseline_name': None,
                                   'risk_model': risk, 'cost_model': cost, 'required_baselines': baseline_names,
                                   'same_risk_baselines': ['DAILY_RISK'], 'cells': cells},
                    'validation_plan': pending_plan(), 'adopted': False}
        protocol_path = generated / (version + '.protocol.json')
        write_json(protocol_path, protocol)
        receipt = register_candidate(protocol_path, registry)
        result = {'schema_version': SCHEMA, 'candidate_version': version, 'protocol_sha256': receipt['protocol_sha256'],
                  'parent_version': protocol['parent']['version'], 'parent_source_hashes': parent_sources,
                  'candidate_source_hashes': source_refs, 'input_hashes': inputs, 'history_classification': 'seen_diagnostic',
                  'source_artifacts': artifacts, 'historical_screen': conclusions[version],
                  'rows': [normalize(row) for row in results if row['name'] == version] + baseline_rows}
        result_path = generated / (version + '.comparison.json')
        write_json(result_path, result)
        reports.append(ingest_comparison(registry / version, result_path))
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    register = subs.add_parser('register', help='Freeze a declared protocol and verify source/input hashes')
    register.add_argument('--protocol', type=Path, required=True)
    register.add_argument('--registry', type=Path, required=True)
    ingest = subs.add_parser('ingest', help='Ingest same-window/same-cost and explicitly same-risk evidence')
    ingest.add_argument('--entry', type=Path, required=True)
    ingest.add_argument('--comparison', type=Path, required=True)
    prospective = subs.add_parser('prospective', help='Read the frozen prospective plan; missing thresholds remain pending')
    prospective.add_argument('--entry', type=Path, required=True)
    public = subs.add_parser('import-public', help='Import existing PUBLIC_H1_FIXED_TWO_V1 results without rerunning economics')
    public.add_argument('--research-root', type=Path, required=True)
    public.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'register':
            result = register_candidate(args.protocol, args.registry)
        elif args.command == 'ingest':
            result = ingest_comparison(args.entry, args.comparison)
        elif args.command == 'prospective':
            protocol, receipt = load_entry(args.entry)
            result = prospective_status(protocol, receipt['registered_utc'])
        else:
            result = import_public_research(args.research_root, args.registry)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'BLOCKED_INVALID_EVIDENCE', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
