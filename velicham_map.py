"""
Velicham - map visualization
Run this after velicham_statewide_analysis.py has produced velicham_districts.geojson

pip install folium
"""

import json
import folium

with open("velicham_districts.geojson") as f:
    geo = json.load(f)

# Kerala's approximate center
m = folium.Map(location=[10.27, 76.40], zoom_start=8, tiles="CartoDB positron")

folium.Choropleth(
    geo_data=geo,
    data=[(f["properties"]["ADM2_NAME"], f["properties"]["light_per_capita"]) for f in geo["features"]],
    columns=["district", "light_per_capita"],
    key_on="feature.properties.ADM2_NAME",
    fill_color="YlOrRd_r",  # reversed: dark red = most underserved (low light/capita)
    fill_opacity=0.75,
    line_opacity=0.5,
    legend_name="Light per capita (lower = more underserved)",
).add_to(m)

# Add popups with both metrics, so the raw number is visible alongside the ratio
for feature in geo["features"]:
    props = feature["properties"]
    popup_html = (
        f"<b>{props['ADM2_NAME']}</b><br>"
        f"Rank (most underserved first): {props['rank_underserved']}<br>"
        f"Mean radiance: {props['mean_radiance']:.3f}<br>"
        f"Population: {int(props['total_population']):,}<br>"
        f"Light per capita: {props['light_per_capita']:.4f}"
    )
    folium.GeoJson(
        feature,
        style_function=lambda x: {"fillOpacity": 0, "color": "transparent"},
        tooltip=folium.Tooltip(popup_html),
    ).add_to(m)

m.save("velicham_map.html")
print("Saved velicham_map.html — open it in a browser.")
print("Hover over each district to see rank, raw radiance, population, and light-per-capita together.")
print("This is the screenshot/recording you want for the demo video.")
