from typing import List, Optional

from pydantic import BaseModel


class StatementRow(BaseModel):
    id: str
    date: str
    description: str = ""
    reference: str = ""
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    balance: Optional[float] = None


class StatementRows(BaseModel):
    rows: List[StatementRow]
