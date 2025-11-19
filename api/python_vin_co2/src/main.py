# --------nabha code-------

# import os
# import logging
# import math
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from datetime import datetime, date
# from dateutil.parser import parse as parse_dt
# from bson import ObjectId

# # Assuming these imports are correct based on your previous tracebacks
# from .db import users_coll, vehicles_coll, gps_coll, emissions_coll, ping_db
# from .services.gemini_ocr import extract_text_from_image_gemini
# from .services.vin_lookup import decode_vin_vpic
# from .services import emission
# from .utils.validators import extract_vin_from_text, normalize_fuel

# # Assuming routers are imported like this
# from src.services import gps as gps_service # Renamed to gps_service for clarity
# from src.services.gps import router as gps_router
# from src.services.mode_predictor import router as mode_router

# logger = logging.getLogger("uvicorn.error")

# # ----------------- FastAPI App Initialization -----------------

# app = FastAPI(title="Python VIN->CO2 Service")

# app.add_middleware(CORSMiddleware, allow_origins=[""], allow_methods=[""], allow_headers=["*"])

# @app.on_event("startup")
# async def startup_event():
#     ok = await ping_db()
#     if not ok:
#         print("⚠ WARNING: Could not connect to MongoDB Atlas.")
#     emission.reload_tables()

# # ----------------- Utility Function (Required Fix) -----------------

# def _to_json_safe(d: dict) -> dict:
#     """
#     Return a shallow copy of d where any ObjectId is converted to str
#     and datetime objects are isoformatted. This is conservative and
#     avoids returning raw pymongo objects to FastAPI.
#     """
#     out = {}
#     for k, v in d.items():
#         if isinstance(v, ObjectId):
#             out[k] = str(v)
#         elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
#             # datetime-like
#             try:
#                 out[k] = v.isoformat()
#             except Exception:
#                 out[k] = str(v)
#         elif isinstance(v, dict):
#             # shallow recursion for nested dicts
#             out[k] = _to_json_safe(v)
#         elif isinstance(v, list):
#             # handle lists of objects
#             out[k] = [_to_json_safe(item) if isinstance(item, dict) else item for item in v]
#         else:
#             out[k] = v
#     return out

# # ----------------- Endpoints -----------------

# @app.get("/")
# def home():
#     return {"Response" : "You are at home"}

# @app.get("/ping")
# def ping():
#     print("PING endpoint hit")
#     return {"status": "ok"}

# @app.post("/upload-vin")
# async def upload_vin(user_id: str, file: UploadFile = File(...)):
#     raw = await file.read()
#     mime = file.content_type or "image/jpeg"
#     text = extract_text_from_image_gemini(raw, mime_type=mime)
#     vin = extract_vin_from_text(text)
#     if not vin:
#         return {"vin": None, "decoded": None, "message": "VIN not detected. Send clearer/cropped VIN image."}
#     decoded = await decode_vin_vpic(vin)
    
#     # map category heuristics (simple)
#     body = (decoded.get("BodyClass") or "") if decoded else ""
#     vehicle_type = (decoded.get("VehicleType") or "") if decoded else ""
    
#     # Heuristic category mapping
#     cat = None
#     if "TRUCK" in str(body).upper() or "TRUCK" in str(vehicle_type).upper():
#         cat = "TRUCK_HEAVY"
#     elif "BUS" in str(body).upper() or "BUS" in str(vehicle_type).upper():
#         cat = "BUS"
#     elif "MOTORCYCLE" in str(body).upper() or "MOTORCYCLE" in str(vehicle_type).upper():
#         cat = "MOTORCYCLE"
#     else:
#         cat = "CAR"

#     fuel = decoded.get("FuelTypePrimary") or decoded.get("FuelType") or decoded.get("FuelTypePrimary1") or None
#     fuel_norm = normalize_fuel(fuel)
    
#     # Save to DB
#     await vehicles_coll.update_one({"user_id": user_id}, {"$set": {
#         "user_id": user_id,
#         "vin": vin,
#         "decoded": decoded,
#         "vehicle_category": cat,
#         "fuel_type": fuel_norm,
#         "stored_at": datetime.utcnow()
#     }}, upsert=True)
#     return {"vin": vin, "decoded": decoded, "vehicle_category": cat, "fuel_type": fuel_norm}

# # --------------- The Fixed Daily Calculation Endpoint ------------------

# @app.post("/calculate/daily")
# async def calculate_daily(user_id: str, country_code: str = None, subregion: str = ""):
#     # defensive sanitization: trim whitespace/newlines
#     if user_id is None:
#         raise HTTPException(status_code=400, detail="user_id is required")
#     user_id = str(user_id).strip()
#     country_code = str(country_code).strip() if country_code is not None else None
#     subregion = str(subregion).strip() if subregion is not None else ""

#     if user_id == "":
#         raise HTTPException(status_code=400, detail="user_id cannot be empty or whitespace")

#     try:
#         # Lookup vehicle (exact match by user_id)
#         vehicle = await vehicles_coll.find_one({"user_id": user_id})
#         if not vehicle:
#             alt = await users_coll.find_one({"user_id": user_id}) or await users_coll.find_one({"userid": user_id})
#             hint = "User profile exists but no vehicle linked. Upload VIN or set vehicle on profile." if alt else "No vehicle or user profile found for this user_id."
#             raise HTTPException(status_code=404, detail=f"Vehicle not found. {hint}")

#         vehicle_category = vehicle.get("vehicle_category")
#         fuel_type = vehicle.get("fuel_type")

#         if not country_code:
#             user = await users_coll.find_one({"user_id": user_id})
#             if user:
#                 country_code = user.get("country_code") or user.get("country")
#         if not country_code:
#             raise HTTPException(status_code=400, detail="country_code required (or add to user profile).")

#         # Sum today's gps distance
#         today = date.today().isoformat()
#         cursor = gps_coll.aggregate([
#             {"$match": {"user_id": user_id, "date": today}},
#             {"$group": {"_id": "$user_id", "total": {"$sum": "$distance_km"}}}
#         ])
#         r = await cursor.to_list(length=1)
#         distance = float(r[0]["total"]) if r and r[0].get("total") is not None else 0.0

#         if distance <= 0:
#             # fallback: compute haversine sum from lat/lon if needed
#             docs = await gps_coll.find({"user_id": user_id, "date": today}).sort("timestamp", 1).to_list(length=None)
#             if docs and len(docs) > 1:
#                 from math import radians, sin, cos, atan2, sqrt
#                 def haversine_km(lat1, lon1, lat2, lon2):
#                     R = 6371.0
#                     phi1 = radians(lat1); phi2 = radians(lat2)
#                     dphi = radians(lat2 - lat1); dlambda = radians(lon2 - lon1)
#                     a = sin(dphi/2)*2 + cos(phi1)*cos(phi2)*sin(dlambda/2)*2
#                     c = 2 * atan2(sqrt(a), sqrt(1-a))
#                     return R * c
#                 total = 0.0
#                 prev = None
#                 for d in docs:
#                     lat = d.get("lat"); lon = d.get("lon")
#                     if lat is None or lon is None:
#                         prev = None
#                         continue
#                     if prev:
#                         total += haversine_km(prev[0], prev[1], lat, lon)
#                     prev = (lat, lon)
#                 distance = total

#         if distance <= 0:
#             raise HTTPException(status_code=400, detail=f"No GPS distance recorded for today ({today}). Insert gps pings or ensure distance_km numeric.")

#         # compute per-km emission
#         try:
#             res = emission.compute_co2_per_km(country_code, vehicle_category, fuel_type, subregion)
#         except Exception as e:
#             logger.exception("compute_co2_per_km failed")
#             # If the calculation fails with an underlying exception (e.g., KeyError), return a 500 error
#             raise HTTPException(status_code=500, detail=f"compute_co2_per_km failed: {e}")

#         # --- NAN VALUE FIX ---
#         co2_per_km = res.get("co2_kg_per_unit")
        
#         # Check if the emission factor is a float and is NaN
#         if co2_per_km is not None and isinstance(co2_per_km, float) and math.isnan(co2_per_km):
#             # If the calculation failed to find a factor (returned NaN), set to 0.0
#             co2_per_km = 0.0 
#             total_kg = 0.0
#         else:
#             co2_per_km = float(co2_per_km) if co2_per_km is not None else 0.0
#             total_kg = co2_per_km * distance
        
#         # Ensure all fields in 'res' details are also JSON safe (convert NaN to None)
#         for key, value in res.items():
#             if isinstance(value, float) and math.isnan(value):
#                 res[key] = None
#         # --- END NAN VALUE FIX ---

#         record = {
#             "user_id": user_id,
#             "date": today,
#             "vehicle": {"vin": vehicle.get("vin"), "vehicle_category": vehicle_category, "fuel_type": fuel_type},
#             "distance_km": float(distance),
#             "co2_kg_per_unit": co2_per_km, # Use the sanitized value
#             "total_kg_co2": total_kg, # Use the sanitized value
#             "details": res,
#             "created_at": datetime.utcnow().isoformat()
#         }

#         insert_res = await emissions_coll.insert_one(record)
#         # attach stringified _id for response
#         record["_id"] = str(insert_res.inserted_id)

#         # Make sure everything returned is JSON safe (ObjectId converted to str already)
#         safe_record = _to_json_safe(record)
#         return {"ok": True, "record": safe_record}

#     except HTTPException:
#         raise
#     except Exception:
#         logger.exception("calculate_daily unexpected error")
#         raise HTTPException(status_code=500, detail="Internal server error while calculating daily emissions")





# ---------nabha code------

# -----------my code--------


import os
import logging
import math
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
from dateutil.parser import parse as parse_dt
from bson import ObjectId

# Assuming these imports are correct based on your previous tracebacks
from .db import users_coll, vehicles_coll, gps_coll, emissions_coll, ping_db
from .services.gemini_ocr import extract_text_from_image_gemini
from .services.vin_lookup import decode_vin_vpic
from .services import emission
from .utils.validators import extract_vin_from_text, normalize_fuel

# Assuming routers are imported like this
from src.services import gps as gps_service # Renamed to gps_service for clarity
from src.services.gps import router as gps_router
from src.services.mode_predictor import router as mode_router

logger = logging.getLogger("uvicorn.error")

# ----------------- FastAPI App Initialization -----------------

app = FastAPI(title="Python VIN->CO2 Service")

app.add_middleware(CORSMiddleware, allow_origins=[""], allow_methods=[""], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    ok = await ping_db()
    if not ok:
        print("⚠ WARNING: Could not connect to MongoDB Atlas.")
    emission.reload_tables()

# ----------------- Utility Function (Required Fix) -----------------

def _to_json_safe(d: dict) -> dict:
    """
    Return a shallow copy of d where any ObjectId is converted to str
    and datetime objects are isoformatted. This is conservative and
    avoids returning raw pymongo objects to FastAPI.
    """
    out = {}
    for k, v in d.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
            # datetime-like
            try:
                out[k] = v.isoformat()
            except Exception:
                out[k] = str(v)
        elif isinstance(v, dict):
            # shallow recursion for nested dicts
            out[k] = _to_json_safe(v)
        elif isinstance(v, list):
            # handle lists of objects
            out[k] = [_to_json_safe(item) if isinstance(item, dict) else item for item in v]
        else:
            out[k] = v
    return out

# ----------------- Endpoints -----------------

@app.get("/")
def home():
    return {"Response" : "You are at home"}

@app.get("/ping")
def ping():
    print("PING endpoint hit")
    return {"status": "ok"}

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
        "vehicle_category": cat,
        "fuel_type": fuel_norm,
        "stored_at": datetime.utcnow()
    }}, upsert=True)
    return {"vin": vin, "decoded": decoded, "vehicle_category": cat, "fuel_type": fuel_norm}

# --------------- The Fixed Daily Calculation Endpoint ------------------

@app.post("/calculate/daily")
async def calculate_daily(user_id: str, country_code: str = None, subregion: str = ""):
    # defensive sanitization: trim whitespace/newlines
    if user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    user_id = str(user_id).strip()
    country_code = str(country_code).strip() if country_code is not None else None
    subregion = str(subregion).strip() if subregion is not None else ""

    if user_id == "":
        raise HTTPException(status_code=400, detail="user_id cannot be empty or whitespace")

    try:
        # Lookup vehicle (exact match by user_id)
        vehicle = await vehicles_coll.find_one({"user_id": user_id})
        if not vehicle:
            alt = await users_coll.find_one({"user_id": user_id}) or await users_coll.find_one({"userid": user_id})
            hint = "User profile exists but no vehicle linked. Upload VIN or set vehicle on profile." if alt else "No vehicle or user profile found for this user_id."
            raise HTTPException(status_code=404, detail=f"Vehicle not found. {hint}")

        vehicle_category = vehicle.get("vehicle_category")
        fuel_type = vehicle.get("fuel_type")

        if not country_code:
            user = await users_coll.find_one({"user_id": user_id})
            if user:
                country_code = user.get("country_code") or user.get("country")
        if not country_code:
            raise HTTPException(status_code=400, detail="country_code required (or add to user profile).")

        # Sum today's gps distance
        today = date.today().isoformat()
        cursor = gps_coll.aggregate([
            {"$match": {"user_id": user_id, "date": today}},
            {"$group": {"_id": "$user_id", "total": {"$sum": "$distance_km"}}}
        ])
        r = await cursor.to_list(length=1)
        distance = float(r[0]["total"]) if r and r[0].get("total") is not None else 0.0

        if distance <= 0:
            # fallback: compute haversine sum from lat/lon if needed
            docs = await gps_coll.find({"user_id": user_id, "date": today}).sort("timestamp", 1).to_list(length=None)
            if docs and len(docs) > 1:
                from math import radians, sin, cos, atan2, sqrt
                def haversine_km(lat1, lon1, lat2, lon2):
                    R = 6371.0
                    phi1 = radians(lat1); phi2 = radians(lat2)
                    dphi = radians(lat2 - lat1); dlambda = radians(lon2 - lon1)
                    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
                    c = 2 * atan2(sqrt(a), sqrt(1-a))
                    return R * c
                total = 0.0
                prev = None
                for d in docs:
                    lat = d.get("lat"); lon = d.get("lon")
                    if lat is None or lon is None:
                        prev = None
                        continue
                    if prev:
                        total += haversine_km(prev[0], prev[1], lat, lon)
                    prev = (lat, lon)
                distance = total

        if distance <= 0:
            raise HTTPException(status_code=400, detail=f"No GPS distance recorded for today ({today}). Insert gps pings or ensure distance_km numeric.")

        # compute per-km emission
        try:
            res = emission.compute_co2_per_km(country_code, vehicle_category, fuel_type, subregion)
        except Exception as e:
            logger.exception("compute_co2_per_km failed")
            # If the calculation fails with an underlying exception (e.g., KeyError), return a 500 error
            raise HTTPException(status_code=500, detail=f"compute_co2_per_km failed: {e}")

        # --- Robust extraction of returned emission keys and computation ---
        # emission.compute_co2_per_km may return keys named differently depending on loader:
        # - kg_co2_per_unit (or) co2_kg_per_unit  <-- per fuel unit (kg per litre, or kg per kg)
        # - kg_co2_per_km   (or) co2_kg_per_km   <-- per km (already multiplied)
        # - consumption_per_km, consumption_unit
        #
        # We'll support all reasonable variants, compute missing values, and sanitize NaNs.

        def _safe_float(v, default=None):
            try:
                f = float(v)
                if math.isnan(f):
                    return default
                return f
            except Exception:
                return default

        # prefer canonical names but accept variants
        kg_co2_per_unit = res.get("kg_co2_per_unit") or res.get("co2_kg_per_unit") or res.get("kg_co2_per_unit")
        kg_co2_per_km   = res.get("kg_co2_per_km")   or res.get("co2_kg_per_km")   or res.get("kg_co2_per_km")

        # try to compute kg_co2_per_km if missing using consumption_per_km * kg_co2_per_unit
        if kg_co2_per_km is None:
            cons = res.get("consumption_per_km")
            if cons is not None and (kg_co2_per_unit is not None):
                try:
                    kg_co2_per_km = float(cons) * float(kg_co2_per_unit)
                except Exception:
                    kg_co2_per_km = None

        # sanitize numeric values (convert NaN to None)
        kg_co2_per_unit_f = _safe_float(kg_co2_per_unit, default=None)
        kg_co2_per_km_f   = _safe_float(kg_co2_per_km, default=None)

        # If nothing could be computed, set numeric results to 0.0 (avoid NaN JSON errors)
        if kg_co2_per_km_f is None:
            kg_co2_per_km_f = 0.0

        total_kg = float(distance) * kg_co2_per_km_f

        # Make sure details contain canonical keys (helpful for clients)
        # Avoid overwriting useful existing values, just normalize
        if "kg_co2_per_unit" not in res and kg_co2_per_unit_f is not None:
            res["kg_co2_per_unit"] = kg_co2_per_unit_f
        if "kg_co2_per_km" not in res:
            res["kg_co2_per_km"] = kg_co2_per_km_f

        # convert any NaN float entries inside res to None to avoid JSON errors
        for k, v in list(res.items()):
            if isinstance(v, float) and math.isnan(v):
                res[k] = None

        record = {
            "user_id": user_id,
            "date": today,
            "vehicle": {"vin": vehicle.get("vin"), "vehicle_category": vehicle_category, "fuel_type": fuel_type},
            "distance_km": float(distance),
            "co2_kg_per_unit": kg_co2_per_unit_f if kg_co2_per_unit_f is not None else 0.0,
            "co2_kg_per_km": kg_co2_per_km_f,
            "total_kg_co2": total_kg,
            "details": res,
            "created_at": datetime.utcnow().isoformat()
        }

        insert_res = await emissions_coll.insert_one(record)
        # attach stringified _id for response
        record["_id"] = str(insert_res.inserted_id)

        # Make sure everything returned is JSON safe (ObjectId converted to str already)
        safe_record = _to_json_safe(record)
        return {"ok": True, "record": safe_record}

    except HTTPException:
        raise
    except Exception:
        logger.exception("calculate_daily unexpected error")
        raise HTTPException(status_code=500, detail="Internal server error while calculating daily emissions")


# include routers (so gps and mode endpoints work)
app.include_router(gps_router)
app.include_router(mode_router)



# ----------my code 10:40 pm--------























































# # src/main.py
# import os
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from .services import gps as gps_service   # adjust import path to where you saved gps.py
# from fastapi.middleware.cors import CORSMiddleware
# from datetime import datetime, date
# from dateutil.parser import parse as parse_dt
# from .db import users_coll, vehicles_coll, gps_coll, emissions_coll, ping_db

# from .services.gemini_ocr import extract_text_from_image_gemini
# from .services.vin_lookup import decode_vin_vpic
# from .services import emission
# from .utils.validators import extract_vin_from_text, normalize_fuel
# from .db import users_coll, vehicles_coll, gps_coll, emissions_coll




# from src.services.gps import router as gps_router
# from src.services.mode_predictor import router as mode_router





# app = FastAPI(title="Python VIN->CO2 Service")

# app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# @app.on_event("startup")
# async def startup_event():
#     ok = await ping_db()
#     if not ok:
#         print("⚠ WARNING: Could not connect to MongoDB Atlas.")
#     emission.reload_tables()

# @app.get("/")
# def home():
#     return {"Response" : "You are at home"}

# # -------------addn to test error-------
# @app.get("/ping")
# def ping():
#     print("PING endpoint hit")
#     return {"status": "ok"}
# # -----------------

# @app.post("/upload-vin")
# async def upload_vin(user_id: str, file: UploadFile = File(...)):
#     raw = await file.read()
#     mime = file.content_type or "image/jpeg"
#     text = extract_text_from_image_gemini(raw, mime_type=mime)
#     vin = extract_vin_from_text(text)
#     if not vin:
#         return {"vin": None, "decoded": None, "message": "VIN not detected. Send clearer/cropped VIN image."}
#     decoded = await decode_vin_vpic(vin)
#     # map category heuristics (simple)
#     body = (decoded.get("BodyClass") or "") if decoded else ""
#     vehicle_type = (decoded.get("VehicleType") or "") if decoded else ""
#     # Heuristic category mapping
#     # Try to set category from vPIC BodyClass / VehicleType
#     cat = None
#     if "TRUCK" in str(body).upper() or "TRUCK" in str(vehicle_type).upper():
#         cat = "TRUCK_HEAVY"
#     elif "BUS" in str(body).upper() or "BUS" in str(vehicle_type).upper():
#         cat = "BUS"
#     elif "MOTORCYCLE" in str(body).upper() or "MOTORCYCLE" in str(vehicle_type).upper():
#         cat = "MOTORCYCLE"
#     else:
#         cat = "CAR"

#     fuel = decoded.get("FuelTypePrimary") or decoded.get("FuelType") or decoded.get("FuelTypePrimary1") or None
#     fuel_norm = normalize_fuel(fuel)
#     # Save to DB
#     await vehicles_coll.update_one({"user_id": user_id}, {"$set": {
#         "user_id": user_id,
#         "vin": vin,
#         "decoded": decoded,
#         "vehicle_category": cat,
#         "fuel_type": fuel_norm,
#         "stored_at": datetime.utcnow()
#     }}, upsert=True)
#     return {"vin": vin, "decoded": decoded, "vehicle_category": cat, "fuel_type": fuel_norm}

# app.include_router(gps_service.router)

# # @app.post("/gps/update")
# # async def gps_update(payload: dict):
# #     user_id = payload.get("user_id")
# #     distance_km = float(payload.get("distance_km", 0))
# #     ts = datetime.utcnow()
# #     if payload.get("timestamp_iso"):
# #         try:
# #             ts = parse_dt(payload.get("timestamp_iso"))
# #         except Exception:
# #             ts = datetime.utcnow()
# #     doc = {"user_id": user_id, "distance_km": distance_km, "timestamp": ts, "date": ts.date().isoformat()}
# #     await gps_coll.insert_one(doc)
# #     return {"ok": True, "stored": doc}




# import logging
# from fastapi import HTTPException
# from bson import ObjectId

# logger = logging.getLogger("uvicorn.error")

# def _to_json_safe(d: dict) -> dict:
#     """
#     Return a shallow copy of d where any ObjectId is converted to str
#     and datetime objects are isoformatted. This is conservative and
#     avoids returning raw pymongo objects to FastAPI.
#     """
#     out = {}
#     for k, v in d.items():
#         if isinstance(v, ObjectId):
#             out[k] = str(v)
#         elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
#             # datetime-like
#             try:
#                 out[k] = v.isoformat()
#             except Exception:
#                 out[k] = str(v)
#         elif isinstance(v, dict):
#             # shallow recursion for nested dicts
#             out[k] = _to_json_safe(v)
#         else:
#             out[k] = v
#     return out

# @app.post("/calculate/daily")
# async def calculate_daily(user_id: str, country_code: str = None, subregion: str = ""):
#     # defensive sanitization: trim whitespace/newlines
#     if user_id is None:
#         raise HTTPException(status_code=400, detail="user_id is required")
#     user_id = str(user_id).strip()
#     country_code = str(country_code).strip() if country_code is not None else None
#     subregion = str(subregion).strip() if subregion is not None else ""

#     if user_id == "":
#         raise HTTPException(status_code=400, detail="user_id cannot be empty or whitespace")

#     try:
#         # Lookup vehicle (exact match by user_id)
#         vehicle = await vehicles_coll.find_one({"user_id": user_id})
#         if not vehicle:
#             alt = await users_coll.find_one({"user_id": user_id}) or await users_coll.find_one({"userid": user_id})
#             hint = "User profile exists but no vehicle linked. Upload VIN or set vehicle on profile." if alt else "No vehicle or user profile found for this user_id."
#             raise HTTPException(status_code=404, detail=f"Vehicle not found. {hint}")

#         vehicle_category = vehicle.get("vehicle_category")
#         fuel = vehicle.get("fuel_type")

#         if not country_code:
#             user = await users_coll.find_one({"user_id": user_id})
#             if user:
#                 country_code = user.get("country_code") or user.get("country")
#         if not country_code:
#             raise HTTPException(status_code=400, detail="country_code required (or add to user profile).")

#         # Sum today's gps distance
#         today = date.today().isoformat()
#         cursor = gps_coll.aggregate([
#             {"$match": {"user_id": user_id, "date": today}},
#             {"$group": {"_id": "$user_id", "total": {"$sum": "$distance_km"}}}
#         ])
#         r = await cursor.to_list(length=1)
#         distance = float(r[0]["total"]) if r and r[0].get("total") is not None else 0.0

#         if distance <= 0:
#             # fallback: compute haversine sum from lat/lon if needed
#             docs = await gps_coll.find({"user_id": user_id, "date": today}).sort("timestamp", 1).to_list(length=None)
#             if docs and len(docs) > 1:
#                 from math import radians, sin, cos, atan2, sqrt
#                 def haversine_km(lat1, lon1, lat2, lon2):
#                     R = 6371.0
#                     phi1 = radians(lat1); phi2 = radians(lat2)
#                     dphi = radians(lat2 - lat1); dlambda = radians(lon2 - lon1)
#                     a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
#                     c = 2 * atan2(sqrt(a), sqrt(1-a))
#                     return R * c
#                 total = 0.0
#                 prev = None
#                 for d in docs:
#                     lat = d.get("lat"); lon = d.get("lon")
#                     if lat is None or lon is None:
#                         prev = None
#                         continue
#                     if prev:
#                         total += haversine_km(prev[0], prev[1], lat, lon)
#                     prev = (lat, lon)
#                 distance = total

#         if distance <= 0:
#             raise HTTPException(status_code=400, detail=f"No GPS distance recorded for today ({today}). Insert gps pings or ensure distance_km numeric.")

#         # compute per-km emission
#         try:
#             res = emission.compute_co2_per_km(country_code, vehicle_category, fuel, subregion)
#         except Exception as e:
#             logger.exception("compute_co2_per_km failed")
#             raise HTTPException(status_code=500, detail=f"compute_co2_per_km failed: {e}")

#         total_kg = res["kg_co2_per_km"] * distance
#         record = {
#             "user_id": user_id,
#             "date": today,
#             "vehicle": {"vin": vehicle.get("vin"), "vehicle_category": vehicle_category, "fuel": fuel},
#             "distance_km": float(distance),
#             "kg_co2_per_km": float(res["kg_co2_per_km"]),
#             "total_kg_co2": float(total_kg),
#             "details": res,
#             "created_at": datetime.utcnow().isoformat()  # store ISO string rather than raw datetime
#         }

#         insert_res = await emissions_coll.insert_one(record)
#         # attach stringified _id for response
#         record["_id"] = str(insert_res.inserted_id)

#         # Make sure everything returned is JSON safe (ObjectId converted to str already)
#         safe_record = _to_json_safe(record)
#         return {"ok": True, "record": safe_record}

#     except HTTPException:
#         raise
#     except Exception:
#         logger.exception("calculate_daily unexpected error")
#         raise HTTPException(status_code=500, detail="Internal server error while calculating daily emissions")







# # @app.post("/calculate/daily")
# # async def calculate_daily(user_id: str, country_code: str = None, subregion: str = ""):
#     vehicle = await vehicles_coll.find_one({"user_id": user_id})
#     if not vehicle:
#         raise HTTPException(status_code=404, detail="Vehicle not found. Upload VIN first.")
#     category = vehicle.get("category")
#     fuel = vehicle.get("fuel_type")
#     if not country_code:
#         # attempt to infer from user profile collection
#         user = await users_coll.find_one({"user_id": user_id})
#         if user:
#             country_code = user.get("country_code")
#     if not country_code:
#         raise HTTPException(status_code=400, detail="country_code required (or add to user profile).")
#     # Sum today's gps distance
#     today = date.today().isoformat()
#     cursor = gps_coll.aggregate([
#         {"$match": {"user_id": user_id, "date": today}},
#         {"$group": {"_id": "$user_id", "total": {"$sum": "$distance_km"}}}
#     ])
#     r = await cursor.to_list(length=1)
#     distance = r[0]["total"] if r else 0.0
#     if distance <= 0:
#         raise HTTPException(status_code=400, detail="No GPS distance recorded for today.")
#     # compute per-km
#     try:
#         res = emission.compute_co2_per_km(country_code, category, fuel, subregion)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     total_kg = res["kg_co2_per_km"] * distance
#     record = {
#         "user_id": user_id,
#         "date": today,
#         "vehicle": {"vin": vehicle.get("vin"), "category": category, "fuel": fuel},
#         "distance_km": distance,
#         "kg_co2_per_km": res["kg_co2_per_km"],
#         "total_kg_co2": total_kg,
#         "details": res,
#         "created_at": datetime.utcnow()
#     }
#     await emissions_coll.insert_one(record)
#     return {"ok": True, "record": record}

# app.include_router(gps_router)
# app.include_router(mode_router)


