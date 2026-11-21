from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import TransferRun, TransferCase
from src.services.twopc_engine import recover
from src.utils.serialize import record

def list_transfer_runs(db):
    return [record(x) for x in db.scalars(select(TransferRun).order_by(TransferRun.id.desc()).limit(100))]

def get_transfer_run(db, ident):
    obj = db.get(TransferRun, ident)
    if obj is None:
        raise HTTPException(404, '调拨演练记录不存在')
    return obj

def create_transfer_run(db, data):
    case = db.get(TransferCase, data.transfer_case_id)
    if case is None:
        raise HTTPException(404, '调拨场景不存在')
    if len(db.scalars(select(TransferRun.id).where(TransferRun.status.in_(['queued', 'running']))).all()) >= 20:
        raise HTTPException(429, '待处理配额20已满')
    snapshot = {'case': record(case), 'decision': case.decision,
                'decision_durable': case.decision_durable, 'participants': case.participants}
    obj = TransferRun(**data.model_dump(), status='queued', snapshot=snapshot)
    db.add(obj); db.flush()
    return obj

def run_transfer(snapshot, supplied):
    """Pure recompute of a run from its frozen snapshot plus backfilled decisions."""
    return recover(snapshot['decision'], snapshot['decision_durable'], snapshot['participants'], supplied)

def supply_decision(db, ident, data):
    """Backfill a missing decision for an in-doubt participant.

    Conflicting decisions are rejected; retrying an already applied decision
    is an idempotent no-op so it never takes effect twice.
    """
    obj = get_transfer_run(db, ident)
    if obj.status not in ('pending', 'completed'):
        raise HTTPException(409, '演练尚未进入待决，无法补入裁决')
    snapshot = obj.snapshot
    if data.decision != snapshot['decision']:
        raise HTTPException(409, '冲突裁决：与协调者已记录的裁决相反，拒绝接回')
    names = [p['name'] for p in snapshot['participants']]
    if data.participant not in names:
        raise HTTPException(404, '参与账本不存在')
    state = dict(obj.state or {})
    resolved = dict(state.get('resolved') or {})
    if resolved.get(data.participant) in ('committed', 'aborted'):
        return obj, '该参与账本裁决已生效，重试不重复执行'
    supplied = dict(state.get('supplied') or {})
    supplied[data.participant] = data.decision
    try:
        result = run_transfer(snapshot, supplied)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    state['supplied'] = supplied
    state['resolved'] = {p['name']: p['outcome'] for p in result['participants']}
    obj.state = state
    obj.result = result
    obj.status = 'completed' if result['global_status'] == 'completed' else 'pending'
    db.flush()
    return obj, '已补入裁决并接回待决任务'
