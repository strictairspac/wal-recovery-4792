"""Stdlib unittest for the blocking 2PC teaching model.

Covers: lost contact after prepare, partial commit delivery, conflicting
(opposite) decisions, commit-requires-all-prepared, atomic visibility of
final ledgers, decision backfill and idempotent retry.
Run: python -m unittest backend.tests.test_twopc_engine (from repo root with
backend on sys.path) or: cd backend && python -m unittest tests.test_twopc_engine
"""
import unittest
from src.services.twopc_engine import recover, validate_case

ALPHA = {'name': 'site_alpha', 'initial': {'sample_A': 100}, 'writes': [{'key': 'sample_A', 'value': 70}], 'crash_stage': 1}
BETA_PREPARED = {'name': 'site_beta', 'initial': {'sample_B': 50}, 'writes': [{'key': 'sample_B', 'value': 80}], 'crash_stage': 1}
BETA_DECIDED = dict(BETA_PREPARED, crash_stage=2)
BETA_LOST = dict(BETA_PREPARED, crash_stage=0)


def outcome(result, name):
    return next(p for p in result['participants'] if p['name'] == name)


class LostContactAfterPrepare(unittest.TestCase):
    def test_prepared_without_decision_stays_in_doubt_and_holds_locks(self):
        r = recover('commit', False, [ALPHA, BETA_DECIDED])
        a = outcome(r, 'site_alpha')
        self.assertEqual(a['outcome'], 'in_doubt')
        self.assertEqual(a['locks'], ['sample_A'])
        self.assertIsNone(a['final'])
        self.assertIn('不得猜为撤销或完成', a['reason'])

    def test_in_doubt_is_never_guessed(self):
        r = recover('abort', False, [ALPHA, BETA_PREPARED])
        self.assertEqual(r['global_status'], 'pending')
        self.assertEqual(outcome(r, 'site_alpha')['outcome'], 'in_doubt')
        self.assertEqual(outcome(r, 'site_beta')['outcome'], 'in_doubt')

    def test_pending_reasons_listed(self):
        r = recover('commit', False, [ALPHA, BETA_DECIDED])
        self.assertEqual(len(r['pending_reasons']), 1)
        self.assertIn('site_alpha', r['pending_reasons'][0])


class PartialCommitDelivery(unittest.TestCase):
    def test_one_received_commit_other_in_doubt(self):
        r = recover('commit', False, [ALPHA, BETA_DECIDED])
        b = outcome(r, 'site_beta')
        self.assertEqual(b['outcome'], 'committed')
        self.assertEqual(b['final'], {'sample_B': 80})
        self.assertEqual(outcome(r, 'site_alpha')['outcome'], 'in_doubt')

    def test_atomic_visibility_withheld_until_all_resolved(self):
        r = recover('commit', False, [ALPHA, BETA_DECIDED])
        self.assertIsNone(r['final_ledgers'])
        self.assertFalse(r['ledgers_visible_together'])
        r2 = recover('commit', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'commit'})
        self.assertTrue(r2['ledgers_visible_together'])
        self.assertEqual(r2['final_ledgers'], {'site_alpha': {'sample_A': 70}, 'site_beta': {'sample_B': 80}})

    def test_durable_coordinator_decision_rejoins_prepared(self):
        r = recover('commit', True, [ALPHA, BETA_PREPARED])
        self.assertEqual(r['global_status'], 'completed')
        self.assertEqual(r['final_ledgers']['site_alpha'], {'sample_A': 70})


class ConflictingDecision(unittest.TestCase):
    def test_opposite_decision_rejected(self):
        with self.assertRaises(ValueError):
            recover('commit', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'abort'})

    def test_opposite_of_abort_rejected(self):
        with self.assertRaises(ValueError):
            recover('abort', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'commit'})

    def test_unknown_participant_rejected(self):
        with self.assertRaises(ValueError):
            recover('commit', False, [ALPHA], {'ghost': 'commit'})


class CommitRequiresAllPrepared(unittest.TestCase):
    def test_commit_with_lost_prepare_invalid(self):
        with self.assertRaises(ValueError):
            validate_case('commit', True, [ALPHA, BETA_LOST])

    def test_abort_with_lost_prepare_valid(self):
        r = recover('abort', False, [ALPHA, BETA_LOST])
        self.assertEqual(outcome(r, 'site_beta')['outcome'], 'aborted')
        self.assertEqual(outcome(r, 'site_beta')['final'], {'sample_B': 50})


class BackfillAndIdempotency(unittest.TestCase):
    def test_backfill_rejoins_in_doubt(self):
        r = recover('abort', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'abort'})
        a = outcome(r, 'site_alpha')
        self.assertEqual(a['outcome'], 'aborted')
        self.assertEqual(a['locks'], [])
        self.assertEqual(r['final_ledgers']['site_alpha'], {'sample_A': 100})

    def test_retry_same_backfill_no_duplicate_effect(self):
        once = recover('commit', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'commit'})
        twice = recover('commit', False, [ALPHA, BETA_DECIDED], {'site_alpha': 'commit'})
        self.assertEqual(once['final_ledgers'], twice['final_ledgers'])
        self.assertEqual(once['result_sha256'], twice['result_sha256'])
        self.assertEqual(once['supplied_decisions'], {'site_alpha': 'commit'})


class Validation(unittest.TestCase):
    def test_stage_out_of_range(self):
        with self.assertRaises(ValueError):
            validate_case('commit', True, [dict(ALPHA, crash_stage=3)])

    def test_duplicate_participant_names(self):
        with self.assertRaises(ValueError):
            validate_case('abort', False, [ALPHA, dict(ALPHA)])

    def test_write_key_must_exist(self):
        bad = {'name': 'site_x', 'initial': {'k': 1}, 'writes': [{'key': 'nope', 'value': 2}], 'crash_stage': 1}
        with self.assertRaises(ValueError):
            validate_case('abort', False, [bad])


if __name__ == '__main__':
    unittest.main()
