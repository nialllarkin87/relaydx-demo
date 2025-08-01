# relaydx_demo/models.py

from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class LabResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str
    test_code: str
    test_name: str
    result_value: float
    units: str
    reference_range: str
    collection_date: datetime
    lab_name: str
    status: str
