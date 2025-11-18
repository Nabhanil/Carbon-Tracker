# src/services/gps.py
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, date
import math
import io
import csv

from src.db import gps_coll
router = APIRouter(prefix="/gps", tags=["gps"])

# --- helpers ---
def parse_iso(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.utcnow().replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.utcnow().replace(tzinfo=timezone.utc)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def smooth_speeds(speeds: List[float], window: int = 3) -> List[float]:
    if window <= 1 or len(speeds) < 2:
        return speeds
    smoothed = []
    n = len(speeds)
    for i in range(n):
        start = max(0, i - window//2)
        end = min(n, i + window//2 + 1)
        smoothed.append(sum(speeds[start:end]) / (end - start))
    return smoothed

def infer_mode_from_speed(speed_kmh: float) -> str:
    if speed_kmh <= 7:
        return "WALK"
    if speed_kmh <= 25:
        return "BIKE"
    if speed_kmh <= 100:
        return "CAR"
    return "OTHER"

# --- request model ---
class GpsUpdate(BaseModel):
    user_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    speed_kmh: Optional[float] = None
    distance_km: Optional[float] = None
    timestamp_iso: Optional[str] = None

# POST /gps/update - canonical single implementation
@router.post("/update")
async def gps_update(payload: GpsUpdate):
    ts = parse_iso(payload.timestamp_iso)
    doc_date = ts.date().isoformat()
    doc = {
        "user_id": payload.user_id,
        "lat": payload.lat,
        "lon": payload.lon,
        "speed_kmh": float(payload.speed_kmh) if payload.speed_kmh is not None else None,
        "distance_km": float(payload.distance_km) if payload.distance_km is not None else None,
        "timestamp": ts,
        "date": doc_date,
        "inserted_at": datetime.utcnow()
    }
    res = await gps_coll.insert_one(doc)
    doc["_id"] = res.inserted_id
    return {"ok": True, "stored": {
        "user_id": doc["user_id"],
        "lat": doc["lat"],
        "lon": doc["lon"],
        "speed_kmh": doc["speed_kmh"],
        "distance_km": doc["distance_km"],
        "timestamp": doc["timestamp"].isoformat(),
        "date": doc["date"],
        "_id": str(doc["_id"])
    }}

# GET /gps/daily-modes - summary by inferred mode
@router.get("/daily-modes")
async def gps_daily_modes(user_id: str, day: Optional[str] = None):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    if day:
        try:
            qdate = date.fromisoformat(day)
        except Exception:
            raise HTTPException(status_code=400, detail="day must be ISO date YYYY-MM-DD")
    else:
        qdate = datetime.utcnow().date()

    iso_day = qdate.isoformat()
    cursor = gps_coll.find({"user_id": user_id, "date": iso_day}).sort("timestamp", 1)
    docs = await cursor.to_list(length=None)

    if not docs:
        return {"ok": True, "date": iso_day, "user_id": user_id, "total_km": 0.0, "by_mode": {}}

    speeds = []
    distances = []
    latlons = []
    timestamps = []

    for d in docs:
        speeds.append(d.get("speed_kmh") if d.get("speed_kmh") is not None else 0.0)
        distances.append(d.get("distance_km"))
        latlons.append((d.get("lat"), d.get("lon")))
        ts = d.get("timestamp")
        timestamps.append(ts if isinstance(ts, datetime) else parse_iso(ts))

    computed_distances = []
    for i in range(len(docs)):
        if distances[i] is not None:
            computed_distances.append(float(distances[i]))
        else:
            if i == 0:
                computed_distances.append(0.0)
            else:
                a = latlons[i-1]
                b = latlons[i]
                if a[0] is not None and a[1] is not None and b[0] is not None and b[1] is not None:
                    computed_distances.append(haversine_km(a[0], a[1], b[0], b[1]))
                else:
                    computed_distances.append(0.0)

    smoothed = smooth_speeds(speeds, window=3)
    mode_for_record = [infer_mode_from_speed(s) for s in smoothed]

    by_mode: Dict[str, float] = {}
    for mode, km in zip(mode_for_record, computed_distances):
        by_mode[mode] = by_mode.get(mode, 0.0) + float(km)

    total_km = sum(computed_distances)
    ordered = {k: round(v, 4) for k, v in sorted(by_mode.items(), key=lambda kv: kv[0])}

    return {
        "ok": True,
        "user_id": user_id,
        "date": iso_day,
        "total_km": round(total_km, 4),
        "by_mode": ordered,
        "records_count": len(docs)
    }

# GET /gps/daily-modes/export - CSV streaming export
@router.get("/daily-modes/export")
async def gps_daily_modes_export(user_id: str, day: Optional[str] = None):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    if day:
        try:
            qdate = date.fromisoformat(day)
        except Exception:
            raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD")
    else:
        qdate = datetime.utcnow().date()
    iso_day = qdate.isoformat()
    cursor = gps_coll.find({"user_id": user_id, "date": iso_day}).sort("timestamp", 1)
    docs = await cursor.to_list(length=None)

    def csv_generator():
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = ["record_id", "timestamp", "date", "user_id", "lat", "lon", "speed_kmh", "distance_km", "inferred_mode"]
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)

        if not docs:
            writer.writerow([])
            writer.writerow(["SUMMARY"])
            writer.writerow(["date", "user_id", "total_km", "records_count", "exported_at"])
            writer.writerow([iso_day, user_id, 0.0, 0, datetime.utcnow().isoformat()])
            yield buf.getvalue()
            return

        speeds = []
        distances = []
        latlons = []
        timestamps = []
        ids = []

        for d in docs:
            speeds.append(d.get("speed_kmh") if d.get("speed_kmh") is not None else 0.0)
            distances.append(d.get("distance_km"))
            latlons.append((d.get("lat"), d.get("lon")))
            ts = d.get("timestamp")
            timestamps.append(ts if isinstance(ts, datetime) else parse_iso(ts))
            ids.append(str(d.get("_id") or ""))

        computed_distances = []
        for i in range(len(docs)):
            if distances[i] is not None:
                computed_distances.append(float(distances[i]))
            else:
                if i == 0:
                    computed_distances.append(0.0)
                else:
                    a = latlons[i-1]
                    b = latlons[i]
                    if a[0] is not None and a[1] is not None and b[0] is not None and b[1] is not None:
                        computed_distances.append(haversine_km(a[0], a[1], b[0], b[1]))
                    else:
                        computed_distances.append(0.0)

        smoothed = smooth_speeds(speeds, window=3)
        modes = [infer_mode_from_speed(s) for s in smoothed]

        for rec_id, ts, latlon, spd, km, mode in zip(ids, timestamps, latlons, speeds, computed_distances, modes):
            row = [
                rec_id,
                ts.isoformat() if isinstance(ts, datetime) else parse_iso(ts).isoformat(),
                iso_day,
                user_id,
                latlon[0] if latlon[0] is not None else "",
                latlon[1] if latlon[1] is not None else "",
                round(spd, 3) if spd is not None else "",
                round(km, 6),
                mode
            ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

        by_mode = {}
        for mode, km in zip(modes, computed_distances):
            by_mode[mode] = by_mode.get(mode, 0.0) + float(km)
        total_km = sum(computed_distances)

        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["date", "user_id", "total_km", "records_count", "exported_at"])
        writer.writerow([iso_day, user_id, round(total_km, 6), len(docs), datetime.utcnow().isoformat()])
        writer.writerow([])
        writer.writerow(["MODE_BREAKDOWN"])
        writer.writerow(["mode", "km"])
        for m, v in by_mode.items():
            writer.writerow([m, round(v, 6)])
        yield buf.getvalue()

    filename = f"gps_export_{user_id}_{iso_day}.csv"
    return StreamingResponse(csv_generator(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })
