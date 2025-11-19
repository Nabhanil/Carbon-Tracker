# src/services/emission.py
from ..utils.excel_loader import load_grid_factors, load_fuel_factors, load_category_consumption
from ..utils.validators import normalize_fuel
import pandas as pd

# cached dfs
_grid_df = None
_fuel_df = None
_cat_df = None

def reload_tables():
    global _grid_df, _fuel_df, _cat_df
    _grid_df = load_grid_factors()
    _fuel_df = load_fuel_factors()
    _cat_df = load_category_consumption()

def lookup_grid_factor(country_code: str, subregion: str = ""):
    if _grid_df is None:
        reload_tables()
    cc = (country_code or "").upper().strip()
    sr = (subregion or "").upper().strip()
    # exact subregion match
    df = _grid_df
    row = df[(df["country_code"] == cc) & (df["subregion"] == sr)]
    if not row.empty:
        return float(row.iloc[0]["grid_co2_kg_per_kwh"])
    # country-level
    row = df[df["country_code"] == cc]
    if not row.empty:
        return float(row.iloc[0]["grid_co2_kg_per_kwh"])
    raise LookupError(f"No grid factor for {country_code}/{subregion}")

def lookup_fuel_co2_per_unit(fuel_type: str):
    if _fuel_df is None:
        reload_tables()
    f = (fuel_type or "").upper().strip()
    row = _fuel_df[_fuel_df["fuel_type"] == f]
    if not row.empty:
        return float(row.iloc[0]["kg_co2_per_unit"])
    raise LookupError(f"No fuel emission factor for '{fuel_type}' (searched as '{f}')")








# def find_consumption(country_code: str, category: str, fuel_type: str):
#     if _cat_df is None:
#         reload_tables()
#     df = _cat_df
#     cc = (country_code or "").upper().strip()
#     cat = (category or "").upper().strip()
#     f = (fuel_type or "").upper().strip()
#     row = df[(df["country_code"] == cc) & (df["vehicle_category"] == cat) & (df["fuel_type"] == f)]
#     if not row.empty:
#         r = row.iloc[0]
#         return float(r["consumption_per_km"]), r["unit"]
#     # fallback: find by country+fuel only
#     row2 = df[(df["country_code"] == cc) & (df["fuel_type"] == f)]
#     if not row2.empty:
#         r = row2.iloc[0]
#         return float(r["consumption_per_km"]), r["unit"]
#     # fallback: find by fuel across all countries
#     row3 = df[df["fuel_type"] == f]
#     if not row3.empty:
#         r = row3.iloc[0]
#         return float(r["consumption_per_km"]), r["unit"]
#     raise LookupError(f"No consumption data for {country_code} / {vehicle_category} / {fuel_type}")

# def compute_co2_per_km(country_code: str, vehicle_category: str, fuel_type: str, subregion: str = ""):
    """
    Return dict:
    { consumption_per_km, consumption_unit, co2_kg_per_unit, method, details... }
    """
    fuel_norm = normalize_fuel(fuel_type)
    cons, unit = find_consumption(country_code, vehicle_category, fuel_norm)
    if fuel_norm != "ELECTRIC":
        co2_kg_per_unit = lookup_fuel_co2_per_unit(fuel_norm)
        co2_kg_per_unit = cons * co2_kg_per_unit
        return {
            "consumption_per_km": cons,
            "consumption_unit": unit,
            "co2_kg_per_unit": co2_kg_per_unit,
            # "co2_kg_per_unit": unit,
            "method": "fuel_chemistry"
        }
    else:
        grid = lookup_grid_factor(country_code, subregion)
        co2_kg_per_unit = cons * grid
        return {
            "consumption_per_km": cons,
            "consumption_unit": unit,
            "co2_kg_per_unit": co2_kg_per_unit,
            "grid_kg_co2_per_kwh": grid,
            "method": "electric_grid"
        }






def find_consumption(country_code: str, category: str, fuel_type: str):
    if _cat_df is None:
        reload_tables()
    df = _cat_df
    cc = (country_code or "").upper().strip()
    cat = (category or "").upper().strip()
    f = (fuel_type or "").upper().strip()

    # try exact country + category + fuel
    row = df[(df["country_code"] == cc) & (df["vehicle_category"] == cat) & (df["fuel_type"] == f)]
    if not row.empty:
        r = row.iloc[0]
        return float(r["consumption_per_km"]), r.get("unit", "")

    # fallback: country + fuel
    row2 = df[(df["country_code"] == cc) & (df["fuel_type"] == f)]
    if not row2.empty:
        r = row2.iloc[0]
        return float(r["consumption_per_km"]), r.get("unit", "")

    # fallback: any country for that fuel
    row3 = df[df["fuel_type"] == f]
    if not row3.empty:
        r = row3.iloc[0]
        return float(r["consumption_per_km"]), r.get("unit", "")

    raise LookupError(f"No consumption data for {cc} / {cat} / {f}")

def compute_co2_per_km(country_code: str, vehicle_category: str, fuel_type: str, subregion: str = ""):
    """
    Return dict:
    {
      consumption_per_km, consumption_unit,
      kg_co2_per_unit,        # kg CO2 per unit (e.g. per litre)
      kg_co2_per_km,          # kg CO2 per km (consumption_per_km * kg_co2_per_unit)
      method, details...
    }
    """
    fuel_norm = normalize_fuel(fuel_type)
    cons, unit = find_consumption(country_code, vehicle_category, fuel_norm)

    # Electric vehicles use grid
    if fuel_norm == "ELECTRIC":
        grid = lookup_grid_factor(country_code, subregion)
        kg_per_km = cons * grid
        return {
            "consumption_per_km": cons,
            "consumption_unit": unit,
            "kg_co2_per_unit": grid,    # here unit is kWh so this is kgCO2 per kWh
            "kg_co2_per_km": kg_per_km,
            "grid_kg_co2_per_kwh": grid,
            "method": "electric_grid"
        }

    # Fuel chemistry path
    co2_per_unit = lookup_fuel_co2_per_unit(fuel_norm)  # kg CO2 per litre (or per unit)
    # co2_per_unit is kg CO2 per 1 unit (e.g. 1 L)
    kg_per_km = cons * co2_per_unit

    return {
        "consumption_per_km": cons,
        "consumption_unit": unit,
        "kg_co2_per_unit": co2_per_unit,
        "kg_co2_per_km": kg_per_km,
        "method": "fuel_chemistry"
    }
