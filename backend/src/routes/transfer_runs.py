import json
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from src.config.database import get_db
from src.middlewares.auth import current_user, writable
from src.schemas.transfer import TransferRunInput, DecisionInput
from src.services.transfer_run_service import list_transfer_runs, get_transfer_run, create_transfer_run, supply_decision
from src.controllers.actions import audit
from src.utils.serialize import record
router = APIRouter()
@router.get('/transfer-runs')
def listing(db=Depends(get_db), user=Depends(current_user)):
    return list_transfer_runs(db)
@router.post('/transfer-runs', status_code=202)
def create(data: TransferRunInput, db=Depends(get_db), user=Depends(writable)):
    obj = create_transfer_run(db, data)
    audit(db, user, f'transfer_run:enqueue:{obj.id}')
    db.commit()
    return record(obj)
@router.get('/transfer-runs/{ident}')
def detail(ident: int, db=Depends(get_db), user=Depends(current_user)):
    return record(get_transfer_run(db, ident))
@router.post('/transfer-runs/{ident}/decision')
def decide(ident: int, data: DecisionInput, db=Depends(get_db), user=Depends(writable)):
    obj, note = supply_decision(db, ident, data)
    audit(db, user, f'transfer_run:decision:{ident}:{data.participant}:{data.decision}')
    db.commit()
    return {'run': record(obj), 'note': note}
@router.get('/transfer-runs/{ident}/export')
def export(ident: int, db=Depends(get_db), user=Depends(current_user)):
    obj = get_transfer_run(db, ident)
    return Response(json.dumps(record(obj), ensure_ascii=False, indent=2), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="transfer-run-{ident}.json"'})
