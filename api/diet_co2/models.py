from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class FoodInput(BaseModel):
    food_type: str = Field(..., description="Food name or type, e.g. 'Eggs' or 'Chicken'")
    quantity_grams: float = Field(..., description="Quantity in grams")
    location: Optional[str] = Field(None, description="Optional location string, e.g. country")

class ConsumptionRequest(BaseModel):
    # Accepts either a single item or list; FastAPI will parse automatically if you pass list
    items: List[FoodInput] = Field(..., description="List of food items consumed in this event")
    user_id: Optional[str] = None
    ate_at: Optional[datetime] = None  # timestamp for the event

class ComputationResult(BaseModel):
    food_type: str
    quantity_grams: float
    kgco2e_per_kg: float
    co2_kg: float

class ConsumptionResponse(BaseModel):
    session_id: str
    user_id: Optional[str]
    ate_at: datetime
    results: List[ComputationResult]
    total_co2_kg: float
