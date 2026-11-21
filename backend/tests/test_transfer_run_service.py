"""Service-layer tests for supply_decision with stubbed sqlalchemy/fastapi.

Runs without third-party deps: ORM modules are stubbed so the pure decision
state machine (backfill, conflict rejection, idempotent retry) is exercised
against the real twopc engine. Run: cd backend && python -m unittest tests.test_transfer_run_service
"""
import copy, json, sys, types, unittest

sa = types.ModuleType('sqlalchemy'); sa.select = lambda *a: None
sys.modules.setdefault('sqlalchemy', sa)
fa = types.ModuleType('fastapi')
class HTTPException(Exception):
    def __init__(self, status, detail):
        super().__init__(detail); self.status_code = status; self.detail = detail
fa.HTTPException = HTTPException
sys.modules.setdefault('fastapi', fa)
dbmod = types.ModuleType('src.config.database')
dbmod.Base, dbmod.engine, dbmod.Session, dbmod.get_db = object, None, None, None
sys.modules['src.config.database'] = dbmod
ent = types.ModuleType('src.models.entities')
class TransferRun: pass
class TransferCase: pass
ent.TransferRun, ent.TransferCase = TransferRun, TransferCase
sys.modules['src.models.entities'] = ent
ser = types.ModuleType('src.utils.serialize'); ser.record = lambda o: dict(o.__dict__)
sys.modules['src.utils.serialize'] = ser

from src.services import transfer_run_service as trs  # noqa: E402

CASE = {'id': 1, 'name': 'c', 'decision': 'commit', 'decision_durable': False,
        'participants': [
            {'name': 'site_alpha', 'initial': {'sample_A': 100}, 'writes': [{'key': 'sample_A', 'value': 70}], 'crash_stage': 1},
            {'name': 'site_beta', 'initial': {'sample_B': 50}, 'writes': [{'key': 'sample_B', 'value': 80}], 'crash_stage': 2}],
        'description': ''}

class FakeDB:
    def __init__(self, run): self.run = run
    def get(self, model, ident): return self.run if model is TransferRun and ident == self.run.id else None
    def flush(self): pass

class Data:
    def __init__(self, participant, decision): self.participant = participant; self.decision = decision

def make_run():
    run = TransferRun()
    run.id, run.status = 7, 'queued'
    run.snapshot = {'case': CASE, 'decision': CASE['decision'],
                    'decision_durable': CASE['decision_durable'], 'participants': copy.deepcopy(CASE['participants'])}
    result = trs.run_transfer(run.snapshot, {})
    run.result = result
    run.state = {'supplied': {}, 'resolved': {p['name']: p['outcome'] for p in result['participants']}}
    run.status = 'completed' if result['global_status'] == 'completed' else 'pending'
    return run

class SupplyDecision(unittest.TestCase):
    def setUp(self):
        self.run = make_run()
        self.db = FakeDB(self.run)

    def test_partial_delivery_leaves_pending(self):
        self.assertEqual(self.run.status, 'pending')
        self.assertEqual(self.run.state['resolved'], {'site_alpha': 'in_doubt', 'site_beta': 'committed'})
        self.assertIsNone(self.run.result['final_ledgers'])

    def test_conflicting_decision_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            trs.supply_decision(self.db, 7, Data('site_alpha', 'abort'))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_unknown_participant_404(self):
        with self.assertRaises(HTTPException) as ctx:
            trs.supply_decision(self.db, 7, Data('ghost', 'commit'))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_backfill_completes_and_ledgers_visible_together(self):
        run, _ = trs.supply_decision(self.db, 7, Data('site_alpha', 'commit'))
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.result['final_ledgers'], {'site_alpha': {'sample_A': 70}, 'site_beta': {'sample_B': 80}})

    def test_retry_idempotent(self):
        trs.supply_decision(self.db, 7, Data('site_alpha', 'commit'))
        before = (json.dumps(self.run.state, sort_keys=True), json.dumps(self.run.result, sort_keys=True))
        _, note = trs.supply_decision(self.db, 7, Data('site_alpha', 'commit'))
        after = (json.dumps(self.run.state, sort_keys=True), json.dumps(self.run.result, sort_keys=True))
        self.assertEqual(before, after)
        self.assertIn('不重复', note)

    def test_conflict_still_rejected_after_completion(self):
        trs.supply_decision(self.db, 7, Data('site_alpha', 'commit'))
        with self.assertRaises(HTTPException) as ctx:
            trs.supply_decision(self.db, 7, Data('site_alpha', 'abort'))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_not_pending_rejected(self):
        self.run.status = 'queued'
        with self.assertRaises(HTTPException) as ctx:
            trs.supply_decision(self.db, 7, Data('site_alpha', 'commit'))
        self.assertEqual(ctx.exception.status_code, 409)

if __name__ == '__main__':
    unittest.main()
