"""
NightGap - statewide analysis + precompute script
Run this locally once Earth Engine access is approved.

Goal:
1. Pull VIIRS night-lights + WorldPop population for all of Kerala's districts
2. Rank districts by light-intensity-per-capita (a proxy for under-investment /
   under-electrification relative to population)
3. Export results as a static GeoJSON + CSV so the Flask app never needs to
   call Earth Engine live - it just serves this precomputed file.

pip install earthengine-api geemap pandas geopandas
"""

import ee
import pandas as pd

EE_PROJECT = "safesync-493807"  # <-- replace with your actual Cloud project ID if different

try:
    ee.Initialize(project=EE_PROJECT)
    print("Already authenticated.")
except Exception:
    print("Not authenticated yet - running ee.Authenticate()...")
    ee.Authenticate()
    ee.Initialize(project=EE_PROJECT)

# --- Step 1: Kerala district boundaries -------------------------------------
districts = (
    ee.FeatureCollection("FAO/GAUL/2015/level2")
    .filter(ee.Filter.eq("ADM1_NAME", "Kerala"))
)

n_districts = districts.size().getInfo()
print(f"Districts found for Kerala: {n_districts}")
if n_districts == 0:
    print("No districts found - check ADM1_NAME spelling/dataset availability.")
    raise SystemExit

names = districts.aggregate_array("ADM2_NAME").getInfo()
print("Districts:", names)

# --- Step 2: night-lights composite (median of 2024 monthly composites) ----
nightlights = (
    ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
    .filterDate("2024-01-01", "2024-12-31")
    .select("avg_rad")
    .median()
)

# --- Step 3: population (WorldPop, India, most recent available year) ------
population = (
    ee.ImageCollection("WorldPop/GP/100m/pop")
    .filter(ee.Filter.eq("country", "IND"))
    .sort("system:time_start", False)
    .first()
)

# --- Step 4: zonal stats per district ---------------------------------------
print("\nComputing zonal statistics (this may take 30-60 seconds)...")

radiance_stats = nightlights.reduceRegions(
    collection=districts,
    reducer=ee.Reducer.mean().setOutputs(["mean_radiance"]),
    scale=500,
)

pop_stats = population.reduceRegions(
    collection=districts,
    reducer=ee.Reducer.sum().setOutputs(["total_population"]),
    scale=100,
)

radiance_list = radiance_stats.getInfo()["features"]
pop_list = pop_stats.getInfo()["features"]

# --- Step 5: combine into a single table -------------------------------------
rad_df = pd.DataFrame([
    {"district": f["properties"]["ADM2_NAME"], "mean_radiance": f["properties"].get("mean_radiance")}
    for f in radiance_list
])
pop_df = pd.DataFrame([
    {"district": f["properties"]["ADM2_NAME"], "total_population": f["properties"].get("total_population")}
    for f in pop_list
])

df = rad_df.merge(pop_df, on="district")
df["total_population"] = df["total_population"].clip(lower=1)  # avoid div by zero
df["light_per_capita"] = df["mean_radiance"] / df["total_population"] * 1_000_000  # scaled for readability

df = df.sort_values("light_per_capita").reset_index(drop=True)
df["rank_underserved"] = df.index + 1  # rank 1 = most underserved (lowest light/capita)

print("\n--- RESULTS: districts ranked by light-per-capita (lowest = most underserved) ---")
print(df[["rank_underserved", "district", "mean_radiance", "total_population", "light_per_capita"]].to_string(index=False))

# --- Step 6: export static files for the Flask app ---------------------------
df.to_csv("nightgap_district_rankings.csv", index=False)
print("\nSaved nightgap_district_rankings.csv")

# Also export district geometries with the stats attached, for map rendering
import json
districts_geojson = districts.getInfo()
for feature in districts_geojson["features"]:
    name = feature["properties"]["ADM2_NAME"]
    row = df[df["district"] == name]
    if not row.empty:
        feature["properties"]["mean_radiance"] = float(row["mean_radiance"].iloc[0])
        feature["properties"]["total_population"] = float(row["total_population"].iloc[0])
        feature["properties"]["light_per_capita"] = float(row["light_per_capita"].iloc[0])
        feature["properties"]["rank_underserved"] = int(row["rank_underserved"].iloc[0])

with open("nightgap_districts.geojson", "w") as f:
    json.dump(districts_geojson, f)
print("Saved nightgap_districts.geojson")

print(f"\nMost underserved district (lowest light-per-capita): {df.iloc[0]['district']}")
print("This is your demo's spotlight district. If it's Wayanad, great - the story holds.")
print("If it's somewhere unexpected, that's fine too - real data, real finding, even better story.")
