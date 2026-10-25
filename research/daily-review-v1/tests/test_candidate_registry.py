"""Offline registry contracts. No strategy code is imported or executed."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / 'candidate_registry.py'


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MODULE.exists():
            spec = importlib.util.spec_from_file_location('candidate_registry', MODULE)
            cls.m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.m)
        else:
            cls.m = None

    def setUp(self):
        self.assertIsNotNone(self.m, 'candidate_registry.py must implement the offline registry')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root / 'registry'
        self.now = '2026-10-19T07:00:00+00:00'
        def artifact(name, content):
            path = self.root / name
            path.write_text(content)
            return {'path': str(path), 'sha256': self.m.sha256_file(path)}
        self.source = artifact('candidate.py', "raise AssertionError('NEVER EXECUTE CANDIDATE')\n")
        self.parent_source = artifact('parent.py', '# frozen parent\n')
        self.input = artifact('inputs.json', '[1,2,3]')
        self.identity = artifact('parent_manifest.json', '{"version":"PARENT_V1"}')
        self.evidence = artifact('evidence.json', '{"seen":true}')
        self.cell = {'window': 'actual', 'start_utc': '2026-07-13T00:00:00Z',
                     'end_utc': '2026-10-18T08:00:00Z', 'scenario': 'base',
                     'cost_layer': 'actual', 'fee_each_side': .0006,
                     'slippage_each_side': .0002, 'delay_hours': 0}
        self.protocol = {'schema_version': 1, 'version': 'CANDIDATE_V1',
                         'frozen_utc': '2026-10-19T06:00:00Z',
                         'registration_timing': 'post_result_import',
                         'parent': {'version': 'PARENT_V1', 'identity': self.identity,
                                    'source_hashes': [self.parent_source]},
                         'candidate_sources': [self.source], 'inputs': [self.input],
                         'hypothesis': 'Document an unchanged, isolated research candidate.',
                         'supporting_evidence': [self.evidence],
                         'falsification': 'Use the existing frozen screen; preserve failures.',
                         'history': {'classification': 'seen_diagnostic',
                                     'latest_seen_utc': '2026-10-18T08:00:00Z'},
                         'comparison': {'purpose': 'candidate_optimization', 'parent_baseline_name': 'DAILY_RISK',
                                        'risk_model': 'frozen_risk_v1', 'cost_model': 'frozen_cost_v1',
                                        'required_baselines': ['DAILY_RISK', 'CASH'],
                                        'same_risk_baselines': ['DAILY_RISK'], 'cells': [self.cell]},
                         'validation_plan': self.m.pending_plan(), 'adopted': False}

    def register(self):
        path = self.root / 'protocol.json'
        path.write_text(json.dumps(self.protocol))
        return self.m.register_candidate(path, self.registry, now=self.now)

    def result(self, entry):
        rows = []
        for name in ['CANDIDATE_V1', 'DAILY_RISK', 'CASH']:
            rows.append(dict(self.cell, name=name, risk_model='frozen_risk_v1' if name != 'CASH' else 'context_only',
                             cost_model='frozen_cost_v1', status='COMPLETE', pnl=0.0,
                             return_pct=0.0, max_drawdown_pct=0.0, completed_nonterminal_trades=0))
        return {'schema_version': 1, 'candidate_version': 'CANDIDATE_V1',
                'protocol_sha256': entry['protocol_sha256'], 'parent_version': 'PARENT_V1',
                'parent_source_hashes': [self.parent_source], 'candidate_source_hashes': [self.source],
                'input_hashes': [self.input], 'history_classification': 'seen_diagnostic',
                'source_artifacts': [self.evidence], 'historical_screen': {'performance_screen_pass': False},
                'rows': rows}

    def test_register_freezes_bytes_and_never_executes_source(self):
        entry = self.register()
        self.assertEqual(entry['status'], 'REGISTERED_DIAGNOSTIC_NOT_VALIDATED')
        self.assertFalse(entry['economically_validated'])
        self.assertFalse(entry['adopted'])
        self.assertEqual((self.registry / 'CANDIDATE_V1' / 'protocol.json').read_bytes(),
                         (self.root / 'protocol.json').read_bytes())
        self.assertEqual(entry['prospective']['status'], 'PENDING_PREREGISTRATION')

    def test_existing_version_is_never_overwritten(self):
        self.register()
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.register()

    def test_rejects_missing_required_fields(self):
        del self.protocol['parent']
        with self.assertRaisesRegex(ValueError, 'parent'):
            self.register()

    def test_rejects_unknown_protocol_fields(self):
        self.protocol['auto_adopt'] = True
        with self.assertRaisesRegex(ValueError, 'unknown'):
            self.register()

    def test_rejects_source_drift(self):
        Path(self.source['path']).write_text('# changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.register()

    def test_rejects_blind_seen_history_claim(self):
        self.protocol['history']['classification'] = 'blind'
        with self.assertRaisesRegex(ValueError, 'history'):
            self.register()

    def test_rejects_adoption_and_path_traversal(self):
        for key, value in [('adopted', True), ('version', '../escape')]:
            original = self.protocol[key]
            self.protocol[key] = value
            with self.assertRaises(ValueError):
                self.register()
            self.protocol[key] = original

    def test_plan_with_missing_thresholds_stays_pending(self):
        self.protocol['validation_plan']['forward_start_utc'] = '2026-10-20T00:00:00Z'
        result = self.register()
        self.assertEqual(result['prospective']['status'], 'PENDING_PREREGISTRATION')
        self.assertIn('minimum_natural_exits', result['prospective']['missing_fields'])

    def test_complete_plan_is_declaration_not_economic_validation(self):
        self.protocol['validation_plan'] = {'forward_start_utc': '2026-10-20T00:00:00Z',
            'forward_end_utc': '2026-11-20T00:00:00Z', 'minimum_duration_days': 30,
            'minimum_natural_exits': 5, 'acceptance_criteria': 'User supplied frozen criterion.',
            'falsification_criteria': 'User supplied frozen failure criterion.'}
        self.assertEqual(self.register()['prospective']['status'], 'DECLARED_PLAN_NOT_VALIDATED')

    def test_rejects_retrospective_forward_start(self):
        self.protocol['validation_plan']['forward_start_utc'] = '2026-10-18T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'forward_start'):
            self.register()

    def test_complete_comparison_is_only_evidence_ingestion(self):
        entry = self.register()
        report = self.m.validate_comparison(self.registry / 'CANDIDATE_V1', self.result(entry))
        self.assertEqual(report['status'], 'COMPARISON_EVIDENCE_COMPLETE_NOT_VALIDATED')
        self.assertFalse(report['economically_validated'])
        self.assertEqual(report['historical_screen'], {'performance_screen_pass': False})
        self.assertEqual(report['same_risk_baselines'], ['DAILY_RISK'])
        self.assertEqual(report['context_only_baselines'], ['CASH'])

    def test_optimization_requires_explicit_parent_in_same_risk_grid(self):
        for change in ('missing_name', 'missing_peer', 'context_parent'):
            original = copy.deepcopy(self.protocol['comparison'])
            if change == 'missing_name':
                self.protocol['comparison']['parent_baseline_name'] = None
            elif change == 'missing_peer':
                self.protocol['comparison']['parent_baseline_name'] = 'ST-PARENT'
            else:
                self.protocol['comparison']['same_risk_baselines'] = ['CASH']
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'parent'):
                self.register()
            self.protocol['comparison'] = original

    def test_historical_peer_screen_is_not_parent_optimization(self):
        self.protocol['comparison'].update(purpose='historical_peer_screen', parent_baseline_name=None)
        entry = self.register()
        report = self.m.validate_comparison(self.registry / 'CANDIDATE_V1', self.result(entry))
        self.assertEqual(report['comparison_purpose'], 'historical_peer_screen')
        self.assertIsNone(report['parent_baseline_name'])
        self.assertFalse(report['parent_optimization_comparison'])

    def test_missing_and_duplicate_rows_are_rejected(self):
        entry = self.register()
        for mode in ('missing', 'duplicate'):
            result = self.result(entry)
            if mode == 'missing': result['rows'].pop()
            else: result['rows'].append(copy.deepcopy(result['rows'][0]))
            with self.assertRaises(ValueError):
                self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)

    def test_changed_windows_risk_cost_inputs_or_versions_are_rejected(self):
        entry = self.register()
        for target, key, value in [('row', 'end_utc', '2026-10-17T08:00:00Z'),
                                   ('row', 'risk_model', 'other_risk'),
                                   ('row', 'fee_each_side', .001),
                                   ('row', 'cost_model', 'other_cost'),
                                   ('envelope', 'parent_version', 'PARENT_V2'),
                                   ('envelope', 'history_classification', 'blind'),
                                   ('envelope', 'input_hashes', [])]:
            result = self.result(entry)
            (result['rows'][0] if target == 'row' else result)[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)

    def test_invalid_baseline_is_preserved_not_zero_filled(self):
        entry = self.register()
        result = self.result(entry)
        result['rows'][1].update(status='INVALID_BORROWING', pnl=None, return_pct=None)
        report = self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)
        self.assertEqual(report['status'], 'COMPARISON_EVIDENCE_WITH_INVALID_RESULTS')
        self.assertEqual(report['invalid_results'][0]['name'], 'DAILY_RISK')
        result['rows'][1]['pnl'] = 0
        with self.assertRaisesRegex(ValueError, 'null'):
            self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)

    def test_boolean_schema_version_is_rejected(self):
        entry = self.register()
        result = self.result(entry)
        result['schema_version'] = True
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)

    def test_nan_and_boolean_metrics_are_rejected(self):
        entry = self.register()
        for bad in (float('nan'), float('inf'), True):
            result = self.result(entry)
            result['rows'][0]['pnl'] = bad
            with self.assertRaises(ValueError):
                self.m.validate_comparison(self.registry / 'CANDIDATE_V1', result)

    def test_ingest_preserves_artifact_and_refuses_duplicate(self):
        entry = self.register()
        path = self.root / 'comparison.json'
        path.write_text(json.dumps(self.result(entry)))
        report = self.m.ingest_comparison(self.registry / 'CANDIDATE_V1', path)
        self.assertTrue(Path(report['saved_comparison']).is_file())
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.m.ingest_comparison(self.registry / 'CANDIDATE_V1', path)

    def test_source_drift_after_registration_blocks_ingestion(self):
        entry = self.register()
        Path(self.parent_source['path']).write_text('# drift')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.m.validate_comparison(self.registry / 'CANDIDATE_V1', self.result(entry))

    def test_cli_register_and_ingest(self):
        self.register()
        entry = json.loads((self.registry / 'CANDIDATE_V1' / 'receipt.json').read_text())
        result = self.root / 'result.json'
        result.write_text(json.dumps(self.result(entry)))
        process = subprocess.run([sys.executable, str(MODULE), 'ingest', '--entry',
                                  str(self.registry / 'CANDIDATE_V1'), '--comparison', str(result)],
                                 text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertFalse(json.loads(process.stdout)['economically_validated'])

    @unittest.skipUnless(Path('/workspace/shared/btc-public-strategies-20261019/outputs/run-01/completion.json').is_file(),
                         'Saved public research package not available')
    def test_real_public_import_preserves_failed_seen_results(self):
        reports = self.m.import_public_research(Path('/workspace/shared/btc-public-strategies-20261019'), self.registry)
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertFalse(report['economically_validated'])
            self.assertFalse(report['historical_screen']['performance_screen_pass'])
            self.assertEqual(report['history_classification'], 'seen_diagnostic')
            self.assertEqual(report['row_count'], 456)
            self.assertEqual(report['same_risk_baselines'], ['DAILY_RISK'])
            self.assertEqual(report['prospective']['status'], 'PENDING_PREREGISTRATION')


if __name__ == '__main__':
    unittest.main()
