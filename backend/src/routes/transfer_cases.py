from fastapi import APIRouter, Depends
from src.config.database import get_db
from src.middlewares.auth import current_user, writable
from src.schemas.transfer import TransferCaseInput
from src.services.transfer_case_service import list_transfer_cases, create_transfer_case
from src.controllers.actions import audit
router = APIRouter()
@router.get('/transfer-cases')
def listing(db=Depends(get_db), user=Depends(current_user)):
    return list_transfer_cases(db)
@router.post('/transfer-cases', status_code=201)
def create(data: TransferCaseInput, db=Depends(get_db), user=Depends(writable)):
    out = create_transfer_case(db, data)
    audit(db, user, 'transfer_case:create')
    db.commit()
    return out
