from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import TransferCase
from src.services.twopc_engine import validate_case
from src.utils.serialize import record

def list_transfer_cases(db):
    return [record(x) for x in db.scalars(select(TransferCase).order_by(TransferCase.id))]

def create_transfer_case(db, data):
    values = data.model_dump()
    try:
        validate_case(values['decision'], values['decision_durable'], values['participants'])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    obj = TransferCase(**values)
    db.add(obj); db.flush()
    return record(obj)
