# src/utils/validators.py
import re

VIN_REGEX = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b", re.IGNORECASE)

def extract_vin_from_text(text: str):
    if not text:
        return None
    m = VIN_REGEX.search(text.upper())
    return m.group(1) if m else None

def normalize_fuel(fuel: str):
    if not fuel:
        return None
    s = str(fuel).upper()
    if "PETROL" in s or "GASOLINE" in s:
        return "PETROL"
    if "DIESEL" in s:
        return "DIESEL"
    if "CNG" in s:
        return "CNG"
    if "ELECT" in s or "EV" in s or "BATTERY" in s:
        return "ELECTRIC"
    return s
