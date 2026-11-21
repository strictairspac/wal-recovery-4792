from typing import Literal
from pydantic import BaseModel, Field

class Participant(BaseModel):
    name: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9_-]+$')
    initial: dict[str, int] = Field(min_length=1, max_length=30)
    writes: list[dict[str, int]] = Field(min_length=1, max_length=30)
    crash_stage: Literal[0, 1, 2]

class TransferCaseInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    decision: Literal['commit', 'abort']
    decision_durable: bool = False
    participants: list[Participant] = Field(min_length=1, max_length=5)
    description: str = Field(default='', max_length=500)

class TransferRunInput(BaseModel):
    transfer_case_id: int = Field(gt=0)
    label: str = Field(min_length=2, max_length=120)

class DecisionInput(BaseModel):
    participant: str = Field(min_length=1, max_length=30)
    decision: Literal['commit', 'abort']
