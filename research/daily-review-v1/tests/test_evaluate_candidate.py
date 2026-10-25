"""Engineering identity checks, not evidence of strategy profitability."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

HERE = Path(__file__).parents[1]
sys.path.insert(0, str(HERE))
import candidate_registry as registry
MODULE = HERE / 'evaluate_candidate.py'


class EvaluateCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MODULE.exists():
            spec = importlib.util.spec_from_file_location('evaluate_candidate', MODULE)
            cls.m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.m)
        else:
            cls.m = None

    def setUp(self):
        self.assertIsNotNone(self.m, 'evaluate_candidate.py must implement the frozen identity engineering runner')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        rng = random.Random(43)
        start = 1783900800000
        value = 100
        bars = []
        for i in range(240):
            opened = value
            value = max(20, value + rng.uniform(-5, 5))
            bars.append({'ts': start + i * 3600000, 'open': opened, 'high': max(opened, value) + .5,
                         'low': min(opened, value) - .5, 'close': value})
        marks = {str(b['ts']): dict(b) for b in bars}
        marks[str(start + len(bars) * 3600000)] = {'open': value}
        self.data = {'bars': bars, 'ledger_bars': bars, 'marks': marks,
                     'funding': {str(start + i * 3600000): .0001 for i in range(0, 241, 8)},
                     'states': {}, 'protocol': {}, 'diagnostic_seen_history': True}
        self.input = self.root / 'inputs.json'
        self.input.write_text(json.dumps(self.data))
        self.protocol = self.root / 'protocol.json'
        self.output = self.root / 'output'
        self.start = '2026-07-14T00:00:00Z'
        self.end = '2026-07-23T00:00:00Z'

    def freeze(self):
        return self.m.freeze_identity_protocol(self.input, self.protocol, 'ST-IDENTITY-ENGINEERING-v1', self.start, self.end)

    def run_case(self):
        return self.m.evaluate(self.protocol, self.input, registry.sha256_file(self.input), self.output)

    def test_identity_matches_parent_all_declared_stress_scenarios(self):
        frozen = self.freeze()
        report = self.run_case()
        self.assertEqual(report['status'], 'COMPLETE_ENGINEERING_IDENTITY_NOT_ECONOMIC_VALIDATION')
        self.assertTrue(report['identity_exact_all_scenarios'])
        self.assertFalse(report['economically_validated'])
        self.assertFalse(report['adopted'])
        self.assertEqual(report['scenario_count'], 4)
        self.assertEqual(report['row_count'], 16)
        self.assertEqual(report['prospective']['status'], 'PENDING_PREREGISTRATION')
        result = registry.read_json(self.output / 'comparison.json')
        self.assertEqual(set(row['name'] for row in result['rows']),
                         {'ST-IDENTITY-ENGINEERING-v1', 'ST-H1-LO-v1', 'CASH', 'HOLD'})
        self.assertEqual(frozen['comparison']['parent_baseline_name'], 'ST-H1-LO-v1')
        self.assertTrue((self.output / 'completion.json').is_file())
        self.assertTrue(any(registry.read_json(path)['orders'] for path in (self.output / 'runs').glob('*.json')))

    def test_input_hash_mismatch_blocks_before_output(self):
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'input.*hash'):
            self.m.evaluate(self.protocol, self.input, '0' * 64, self.output)
        self.assertFalse(self.output.exists())

    def test_changed_frozen_inputs_are_rejected(self):
        self.freeze()
        self.input.write_text(json.dumps(self.data) + '\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.run_case()

    def test_missing_funding_is_not_zero_filled(self):
        del self.data['funding'][str(1783987200000)]
        self.input.write_text(json.dumps(self.data))
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'funding'):
            self.run_case()
        self.assertFalse(self.output.exists())

    def test_missing_mark_is_rejected(self):
        del self.data['marks'][str(1783987200000)]
        self.input.write_text(json.dumps(self.data))
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'mark'):
            self.run_case()

    def test_declared_stress_cannot_be_removed(self):
        self.freeze()
        p = registry.read_json(self.protocol)
        p['comparison']['cells'].pop()
        self.protocol.write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError, 'four|stress'):
            self.run_case()

    def test_undeclared_risk_cost_or_parent_drift_is_rejected(self):
        self.freeze()
        original = registry.read_json(self.protocol)
        for kind in ('fee', 'risk', 'parent', 'source'):
            p = copy.deepcopy(original)
            if kind == 'fee': p['comparison']['cells'][0]['fee_each_side'] = .001
            elif kind == 'risk': p['comparison']['risk_model'] = 'new_risk'
            elif kind == 'parent': p['parent']['version'] = 'OTHER_VERSION'
            else: p['parent']['source_hashes'][0]['sha256'] = '0' * 64
            self.protocol.write_text(json.dumps(p))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_case()

    def test_existing_output_is_preserved(self):
        self.freeze()
        self.run_case()
        before = (self.output / 'completion.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.run_case()
        self.assertEqual((self.output / 'completion.json').read_bytes(), before)

    def test_current_source_cannot_self_sign_as_authorized_parent(self):
        import shutil
        from unittest.mock import patch
        runtime = self.root / 'copied_runtime'
        runtime.mkdir()
        for name in self.m.RUNTIME_FILES + ('st_protocol.json', 'runtime_manifest.json'):
            shutil.copy2(self.m.RUNTIME / name, runtime / name)
        manifest = registry.read_json(runtime / 'runtime_manifest.json')
        manifest['paths']['absolute_root'] = str(runtime)
        (runtime / 'runtime_manifest.json').write_text(json.dumps(manifest))
        with (runtime / 'st_engine.py').open('a') as stream:
            stream.write('\n# unapproved parent source change\n')
        with patch.object(self.m, 'RUNTIME', runtime):
            with self.assertRaisesRegex(ValueError, 'authorized.*hash|locked.*hash'):
                self.freeze()
        self.assertFalse(self.protocol.exists())

    def test_locked_manifest_entry_is_required_not_inferred(self):
        import shutil
        from unittest.mock import patch
        runtime = self.root / 'copied_runtime'
        runtime.mkdir()
        for name in self.m.RUNTIME_FILES + ('st_protocol.json', 'runtime_manifest.json'):
            shutil.copy2(self.m.RUNTIME / name, runtime / name)
        manifest = registry.read_json(runtime / 'runtime_manifest.json')
        manifest['paths']['absolute_root'] = str(runtime)
        del manifest['files']['st_signals.py']
        (runtime / 'runtime_manifest.json').write_text(json.dumps(manifest))
        with patch.object(self.m, 'RUNTIME', runtime):
            with self.assertRaisesRegex(ValueError, 'authorized|locked'):
                self.freeze()

    def test_cli_freeze_and_run_are_separate_and_reproducible(self):
        import subprocess
        base = [sys.executable, str(MODULE), '--protocol', str(self.protocol),
                '--inputs', str(self.input), '--inputs-sha256', registry.sha256_file(self.input)]
        freeze = subprocess.run(base + ['--freeze-identity', '--version', 'CLI-IDENTITY-v1',
                                        '--start-utc', self.start, '--end-utc', self.end],
                                text=True, capture_output=True)
        self.assertEqual(freeze.returncode, 0, freeze.stderr)
        self.assertFalse(self.output.exists())
        run = subprocess.run(base + ['--output', str(self.output)], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)['identity_exact_all_scenarios'])
        self.assertFalse((self.output / 'state.json').exists(), 'Do not leave a misleading STARTED state beside completion')

    def test_nonidentity_protocol_is_not_executed(self):
        self.freeze()
        p = registry.read_json(self.protocol)
        p['comparison']['purpose'] = 'candidate_optimization'
        self.protocol.write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.run_case()

    def test_seen_history_cannot_be_relabeled_blind(self):
        self.data['diagnostic_seen_history'] = False
        self.input.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, 'seen'):
            self.freeze()


if __name__ == '__main__':
    unittest.main()
