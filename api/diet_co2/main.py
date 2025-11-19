import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import asyncio
from fastapi.encoders import jsonable_encoder


from .db import db
from .models import FoodInput, ConsumptionRequest, ConsumptionResponse, ComputationResult

app = FastAPI(title="Diet CO2 Service")

FOOD_COLLECTION = "food_efs"
LOG_COLLECTION = "consumption_logs"

def normalize_name(n: str) -> str:
    return n.strip().lower()

async def lookup_ef(food_name: str):
    # search by normalized field (we no longer store normalized name as _id)
    norm = normalize_name(food_name)
    doc = await db[FOOD_COLLECTION].find_one({"food_name_normalized": norm})
    return doc


@app.post("/compute_food_co2", response_model=ConsumptionResponse)
async def compute_food_co2(req: ConsumptionRequest):
    # session id groups multiple items in one event
    session_id = str(uuid.uuid4())
    ate_at = req.ate_at or datetime.utcnow()
    user_id = req.user_id

    results: List[ComputationResult] = []
    total_co2 = 0.0

    # Validate items list
    if not req.items or len(req.items) == 0:
        raise HTTPException(status_code=400, detail="No items provided")

    for item in req.items:
        # lookup EF
        ef_doc = await lookup_ef(item.food_type)
        if not ef_doc:
            # If not found, we fallback to trying to match by substring or return error
            # Try a substring match (case-insensitive) - helpful for small differences like 'Eggs' vs 'Egg'
            cursor = db[FOOD_COLLECTION].find({"food_name_normalized": {"$regex": normalize_name(item.food_type)}}).limit(1)
            found = await cursor.to_list(length=1)
            ef_doc = found[0] if found else None

        if not ef_doc or ef_doc.get("kgco2e_per_kg") is None:
            # If EF missing, you can choose to:
            #  - raise an error (strict)
            #  - or skip with 0 and mark in log
            # Here we will raise a 404 to notify the client to add EF.
            raise HTTPException(status_code=404, detail=f"Emission factor not found for '{item.food_type}'. Please add to CSV or food_efs collection.")

        ef_val = float(ef_doc["kgco2e_per_kg"])
        qty_kg = float(item.quantity_grams) / 1000.0
        co2 = round(qty_kg * ef_val, 6)
        total_co2 += co2

        result = ComputationResult(
            food_type=item.food_type,
            quantity_grams=item.quantity_grams,
            kgco2e_per_kg=ef_val,
            co2_kg=co2
        )
        results.append(result)

    # Build log doc (immutable)
    log_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "items": [r.dict() for r in results],
        "total_co2_kg": round(total_co2, 6),
        "created_at": datetime.utcnow()
    }

    res = await db[LOG_COLLECTION].insert_one(log_doc)


    response = ConsumptionResponse(
        session_id=session_id,
        user_id=user_id,
        ate_at=ate_at,
        results=results,
        total_co2_kg=round(total_co2, 6)
    )
    return JSONResponse(status_code=200, content=jsonable_encoder(response))
