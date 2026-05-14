import io
import requests
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (safe on servers)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator
import warnings
warnings.filterwarnings("ignore")

# Fetch data

URL = "http://exoplanet.eu/catalog/csv/"

print("Fetching data from exoplanet.eu …")
raw = ""
try:
    response = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    raw = response.text
  
except requests.exceptions.Timeout:
    print("Error: server response timeout")

# Dump raw response to file for inspection
RAW_OUT = "exoplanet_eu_raw.csv"
with open(RAW_OUT, "w", encoding="utf-8") as f:
    f.write(raw)
print("Raw response dumped → {RAW_OUT}")

# EPE CSV has a plain header row (no '#') followed immediately by data rows.
# Use straightforward read_csv — no comment skipping, which was corrupting parsing.
df = pd.read_csv(
    io.StringIO(raw),
    low_memory=False,
    na_values=["", " ", "N/A"],
)

# Read csv

df = pd.read_csv("exoplanet.eu_catalog.csv",
                 usecols = ["star_name","mass","radius","mass_sini","planet_status", "discovered", "detection_type"])

# Apply Filters

cond_status = df["planet_status"] == "Confirmed"
cond_star = df["star_name"].notna() & (df["star_name"].astype(str).str.strip() != "")

# (mass < 13 Mjup AND mass > 0.05 Mearth)
earth_mass = 0.00315 #Mjup
cond_mass = (
    df["mass"].notna() &
    (df["mass"] < 13) &
    (df["mass"] > 0.05*earth_mass)
)

# (mass is null AND radius is not null)
cond_radius_only = (
    df["mass"].isna() &
    df["radius"].notna()
)

# (mass is null AND mass_sini < 13 Mjup)
cond_mass_sini = (
    df["mass"].isna() &
    df["mass_sini"].notna() &
    (df["mass_sini"] < 13)
)

# Combine exactly as in EPE
df = df[
    cond_star &
    (cond_mass | cond_radius_only | cond_mass_sini)
].copy()

print("After EPE filters: {len(df):,} planets.")



# Normalise method names (group minor variants)

# Maps the primary (first) EPE detection_type token to a display label.
# All distinct real values confirmed from the EPE CSV:
#   Primary Transit, Radial Velocity, Imaging, Microlensing,
#   Timing, TTV, Astrometry, Kinematic, Other
METHOD_REMAP = {
    "Primary Transit":  "Transit",
    "Radial Velocity":  "Radial Velocity",
    "Imaging":          "Direct Imaging",
    "Microlensing":     "Microlensing",
    "Timing":           "Timing",
    "TTV":              "Timing",
    "Astrometry":       "Astrometry",
    "Kinematic":        "Other",
    "Other":            "Other",
}

df["method_norm"] = df["detection_type"].apply(
    lambda m: METHOD_REMAP.get(m.split(",")[0].strip(), "Other")
)

# GroupBy Method
 
gb = df.groupby(["discovered", "method_norm"]).size().unstack(fill_value=0)

# Fill empty years with 0

first_year = int(df["discovered"].min())
last_year  = int(df["discovered"].max())
all_years  = range(first_year, last_year + 1)
gb = gb.reindex(all_years, fill_value=0)

METHOD_ORDER = ["Direct Imaging", "Microlensing", "Transit",
                "Radial Velocity", "Timing", "Astrometry", "Other"]

cols = [c for c in METHOD_ORDER if c in gb.columns]
years = list(gb.index)

# Set Colours

COLOURS = {
    "Transit":          "#1a9850",   # green
    "Radial Velocity":  "#d73027",   # red
    "Microlensing":     "#f46d43",   # orange
    "Direct Imaging":   "#4575b4",   # blue
    "Timing":           "#762a83",   # purple
    "Astrometry":       "#fdae61",   # light orange
    "Other":            "#878787",   # grey
}
bar_colours = [COLOURS.get(c, "#aaaaaa") for c in cols]

# Draw

fig, ax = plt.subplots(figsize=(1080/72, 720/72))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

bottoms = [0] * len(years)
for method, colour in zip(cols, [COLOURS.get(c, "#aaaaaa") for c in cols]):
    vals = list(gb[method])
    ax.bar(years, vals, bottom=bottoms, color=colour, label=method,
           width=0.85, linewidth=0.3, edgecolor="white")
    bottoms = [b + v for b, v in zip(bottoms, vals)]

# Labels on top
max_total = max(bottoms)
label_fs  = max(7, min(11, int(900 / len(years))))

for x, total in zip(years, bottoms):
    if total:
        ax.text(x, total + max_total * 0.005, str(int(total)),
                ha="center", va="bottom", fontsize=label_fs, color="#333333")

# Axes
ax.set(xlim=(min(years) - 0.75, max(years) + 0.75), ylim=(0, 1550))
ax.set_xticks(years)
ax.set_xticklabels([str(y) for y in years], fontsize=9,
                   rotation=45, ha="right", rotation_mode="anchor")

for which, ax_ in [("left", ax), ("right", ax.twinx())]:
    ax_.set_ylim(0, 1550)
    ax_.yaxis.set_major_locator(MultipleLocator(50))
    ax_.tick_params(axis="y", which="both", labelsize=10, length=0)
    for spine in ax_.spines.values():
        spine.set_visible(False)

ax.tick_params(axis="both", which="both", length=0)
ax.grid(axis="y", color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
ax.set_axisbelow(True)

# Save
plt.tight_layout()
plt.savefig("Confirmed_exoplanets_by_methods_EPE.svg")
plt.close()

print(f"Saved → Confirmed exoplanets by methods EPE.svg")
