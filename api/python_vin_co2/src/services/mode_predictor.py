# src/services/mode_predictor.py
from fastapi import APIRouter

router = APIRouter(prefix="/predict", tags=["vehicle-mode"])

def predict_transport_mode(speed_kmh: float) -> str:
    if speed_kmh <= 7:
        return "WALK"
    if speed_kmh <= 25:
        return "BIKE"
    if speed_kmh <= 60:
        return "CAR (city)"
    if speed_kmh <= 120:
        return "CAR (highway)"
    if speed_kmh <= 200:
        return "BUS"
    return "OTHER"

@router.get("/mode")
async def predict_mode(speed: float):
    mode = predict_transport_mode(speed)
    return {"speed_kmh": speed, "predicted_mode": mode}
