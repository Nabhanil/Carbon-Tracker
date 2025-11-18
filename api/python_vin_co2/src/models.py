# src/models.py
from pydantic import BaseModel
from typing import Optional

class GPSUpdate(BaseModel):
    user_id: str
    distance_km: float
    timestamp_iso: Optional[str] = None

class CalcRequest(BaseModel):
    user_id: str
    region_code: Optional[str] = None
    subregion: Optional[str] = None
