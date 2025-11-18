# src/main.py
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from .services import gps as gps_service   # adjust import path to where you saved gps.py
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
from dateutil.parser import parse as parse_dt
from .db import users_coll, vehicles_coll, gps_coll, emissions_coll, ping_db

from .services.gemini_ocr import extract_text_from_image_gemini
from .services.vin_lookup import decode_vin_vpic
from .services import emission
from .utils.validators import extract_vin_from_text, normalize_fuel
from .db import users_coll, vehicles_coll, gps_coll, emissions_coll

app = FastAPI(title="Python VIN->CO2 Service")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    ok = await ping_db()
    if not ok:
        print("⚠ WARNING: Could not connect to MongoDB Atlas.")
    emission.reload_tables()

@app.get("/")
def home():
    return {"Response" : "You are at home"}

# -------------addn to test error-------
@app.get("/ping")
def ping():
    print("PING endpoint hit")
    return {"status": "ok"}
# -----------------

@app.post("/upload-vin")
async def upload_vin(user_id: str, file: UploadFile = File(...)):
    raw = await file.read()
    mime = file.content_type or "image/jpeg"
    text = extract_text_from_image_gemini(raw, mime_type=mime)
    vin = extract_vin_from_text(text)
    if not vin:
        return {"vin": None, "decoded": None, "message": "VIN not detected. Send clearer/cropped VIN image."}
    decoded = await decode_vin_vpic(vin)
    # map category heuristics (simple)
    body = (decoded.get("BodyClass") or "") if decoded else ""
    vehicle_type = (decoded.get("VehicleType") or "") if decoded else ""
    # Heuristic category mapping
    # Try to set category from vPIC BodyClass / VehicleType
    cat = None
    if "TRUCK" in str(body).upper() or "TRUCK" in str(vehicle_type).upper():
        cat = "TRUCK_HEAVY"
    elif "BUS" in str(body).upper() or "BUS" in str(vehicle_type).upper():
        cat = "BUS"
    elif "MOTORCYCLE" in str(body).upper() or "MOTORCYCLE" in str(vehicle_type).upper():
        cat = "MOTORCYCLE"
    else:
        cat = "CAR"

    fuel = decoded.get("FuelTypePrimary") or decoded.get("FuelType") or decoded.get("FuelTypePrimary1") or None
    fuel_norm = normalize_fuel(fuel)
    # Save to DB
    await vehicles_coll.update_one({"user_id": user_id}, {"$set": {
        "user_id": user_id,
        "vin": vin,
        "decoded": decoded,
        "category": cat,
        "fuel_type": fuel_norm,
        "stored_at": datetime.utcnow()
    }}, upsert=True)
    return {"vin": vin, "decoded": decoded, "category": cat, "fuel_type": fuel_norm}

app.include_router(gps_service.router)

# @app.post("/gps/update")
# async def gps_update(payload: dict):
#     user_id = payload.get("user_id")
#     distance_km = float(payload.get("distance_km", 0))
#     ts = datetime.utcnow()
#     if payload.get("timestamp_iso"):
#         try:
#             ts = parse_dt(payload.get("timestamp_iso"))
#         except Exception:
#             ts = datetime.utcnow()
#     doc = {"user_id": user_id, "distance_km": distance_km, "timestamp": ts, "date": ts.date().isoformat()}
#     await gps_coll.insert_one(doc)
#     return {"ok": True, "stored": doc}

@app.post("/calculate/daily")
async def calculate_daily(user_id: str, country_code: str = None, subregion: str = ""):
    vehicle = await vehicles_coll.find_one({"user_id": user_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found. Upload VIN first.")
    category = vehicle.get("category")
    fuel = vehicle.get("fuel_type")
    if not country_code:
        # attempt to infer from user profile collection
        user = await users_coll.find_one({"user_id": user_id})
        if user:
            country_code = user.get("country_code")
    if not country_code:
        raise HTTPException(status_code=400, detail="country_code required (or add to user profile).")
    # Sum today's gps distance
    today = date.today().isoformat()
    cursor = gps_coll.aggregate([
        {"$match": {"user_id": user_id, "date": today}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$distance_km"}}}
    ])
    r = await cursor.to_list(length=1)
    distance = r[0]["total"] if r else 0.0
    if distance <= 0:
        raise HTTPException(status_code=400, detail="No GPS distance recorded for today.")
    # compute per-km
    try:
        res = emission.compute_co2_per_km(country_code, category, fuel, subregion)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    total_kg = res["kg_co2_per_km"] * distance
    record = {
        "user_id": user_id,
        "date": today,
        "vehicle": {"vin": vehicle.get("vin"), "category": category, "fuel": fuel},
        "distance_km": distance,
        "kg_co2_per_km": res["kg_co2_per_km"],
        "total_kg_co2": total_kg,
        "details": res,
        "created_at": datetime.utcnow()
    }
    await emissions_coll.insert_one(record)
    return {"ok": True, "record": record}
