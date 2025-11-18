# src/services/vin_lookup.py
import httpx

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/"

async def decode_vin_vpic(vin: str):
    url = f"{VPIC_BASE}{vin}?format=json"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("Results") or []
        return results[0] if results else None
