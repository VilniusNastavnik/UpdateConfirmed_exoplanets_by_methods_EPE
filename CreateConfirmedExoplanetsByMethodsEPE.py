"""
Exoplanet Discoveries per Year by Detection Method
===================================================
Reproduces / updates the Wikipedia Commons chart:
  File:Confirmed_exoplanets_by_methods_EPE.svg

Data source : https://exoplanet.eu/catalog/csv/
              (The Extrasolar Planets Encyclopaedia – EPE)

Filters applied:
  • status  == "Confirmed"
  • detection_type is not null / empty
  • discovered (year) is not null

Output: exoplanets_by_method.svg  (stacked-bar chart, 1350×900 px)

Usage:
  pip install requests pandas matplotlib
  python exoplanets_by_method.py

Dependencies
------------
  requests  – to fetch the CSV
  pandas    – to clean and pivot data
  matplotlib – to draw and export SVG
"""

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

# ── 1. Fetch data ────────────────────────────────────────────────────────────

URL = "http://exoplanet.eu/catalog/csv/"

print("Fetching data from exoplanet.eu …")
response = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
response.raise_for_status()
raw = response.text

# Dump raw response to file for inspection
RAW_OUT = "exoplanet_eu_raw.csv"
with open(RAW_OUT, "w", encoding="utf-8") as f:
    f.write(raw)
print(f"  Raw response dumped → {RAW_OUT}")

# EPE CSV has a plain header row (no '#') followed immediately by data rows.
# Use straightforward read_csv — no comment skipping, which was corrupting parsing.
df = pd.read_csv(
    io.StringIO(raw),
    low_memory=False,
    na_values=["", " ", "N/A"],
)
print(f"  Parsed {len(df):,} rows, {df.shape[1]} columns.")
print(f"  Columns: {list(df.columns)}")

# ── 2. Normalise column names ────────────────────────────────────────────────

COL_MAP = {
    "planet_status":  "status",    # confirmed EPE column name
    "detection_type": "method",    # confirmed EPE column name
    "discovered":     "year",      # confirmed EPE column name
}
df.rename(columns={c: v for c, v in COL_MAP.items() if c in df.columns}, inplace=True)

for col in ("status", "method", "year"):
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found. Available: {list(df.columns)}")

# ── 3. Filter ────────────────────────────────────────────────────────────────

df["status"] = df["status"].astype(str).str.strip()
df["method"] = df["method"].astype(str).str.strip()
df["year"]   = pd.to_numeric(df["year"], errors="coerce")

# Show distinct status values for verification
print(f"  Status values in CSV: {sorted(df['status'].dropna().unique())}")

# EPE uses exactly "Confirmed" (capital C, confirmed from real CSV)
mask = (
    (df["status"] == "Confirmed") &
    df["year"].notna() &
    (df["method"] != "") &
    (df["method"].str.lower() != "nan")
)
df = df[mask].copy()
df["year"] = df["year"].astype(int)

print(f"  After filtering: {len(df):,} confirmed planets with valid year+method.")
print(f"  Year range: {df['year'].min()} – {df['year'].max()}")
print(f"  Methods found:\n    {sorted(df['method'].unique())}")

# Diagnostic: raw counts for the earliest years
print("\n  RAW counts by (year, method) for the first 10 years:")
first10 = df[df["year"] <= df["year"].min() + 9]
print(first10.groupby(["year", "method"]).size().to_string())


# ── 3b. Apply EPE physical inclusion filter (<13 Mjup planets) ──────────────

# Ensure numeric columns are numeric
for col in ["mass", "mass_sini", "radius"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Star name must exist
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

print(f"  After EPE physical filter: {len(df):,} planets.")



# ── 4. Normalise method names (group minor variants) ────────────────────────

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

def normalise_method(m: str) -> str:
    # EPE lists multiple methods comma-separated; take only the primary (first) one
    primary = m.split(",")[0].strip()
    if primary in METHOD_REMAP:
        return METHOD_REMAP[primary]
    # Substring fallbacks for any future variant
    pl = primary.lower()
    if "transit" in pl:                          return "Transit"
    if "radial" in pl or "doppler" in pl:        return "Radial Velocity"
    if "microlens" in pl:                        return "Microlensing"
    if "imag" in pl:                             return "Direct Imaging"
    if "timing" in pl or "pulsar" in pl or "ttv" in pl: return "Timing"
    if "astrom" in pl:                           return "Astrometry"
    return "Other"

df["method_norm"] = df["method"].apply(normalise_method)

# ── 5. Pivot: count per (year, method) ──────────────────────────────────────

pivot = (
    df.groupby(["year", "method_norm"])
      .size()
      .unstack(fill_value=0)
)

# Only use years actually present in the data — no phantom years invented by reindex
# (gaps between real years are kept as 0-filled rows only if they fall between
#  the first and last year that genuinely have data)
first_year = int(df["year"].min())
last_year  = int(df["year"].max())
all_years  = range(first_year, last_year + 1)
pivot = pivot.reindex(all_years, fill_value=0)
print(f"  Year range in chart: {first_year} – {last_year}")

# Desired stack order — bottom to top:
#   Direct Imaging → Microlensing → Transit → Radial Velocity → Timing → others
METHOD_ORDER = [
    "Direct Imaging",
    "Microlensing",
    "Transit",
    "Radial Velocity",
    "Timing",
    "Astrometry",
    "Other",
]
# Keep only columns that exist in the pivot
cols = [c for c in METHOD_ORDER if c in pivot.columns]
# Append any leftover methods not in our list
extras = [c for c in pivot.columns if c not in cols]
cols += extras
pivot = pivot[cols]

print(f"\n  Pivot shape: {pivot.shape}  (years × methods)")
print(pivot.tail(5).to_string())

# ── 6. Colours (match Wikipedia Commons SVG palette) ────────────────────────

# Approximate colours from the original SVG
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

# ── 7. Draw ──────────────────────────────────────────────────────────────────

FIG_W_IN = 1080 / 72   # will be overridden before save; keeps aspect ratio for layout
FIG_H_IN =  720 / 72

fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

years = list(pivot.index)
bottoms = [0] * len(years)

bars_handles = []
for method, colour in zip(cols, bar_colours):
    vals = list(pivot[method])
    bars = ax.bar(
        years,
        vals,
        bottom=bottoms,
        color=colour,
        label=method,
        width=0.85,
        linewidth=0.3,
        edgecolor="white",
    )
    bars_handles.append(mpatches.Patch(color=colour, label=method))
    bottoms = [b + v for b, v in zip(bottoms, vals)]

# ── 8. Total count labels on top of each bar ─────────────────────────────────

totals = bottoms
max_total = max(totals)

label_fontsize = max(7, min(11, int(900 / len(years))))

for x, total in zip(years, totals):
    if total == 0:
        continue
    ax.text(
        x,
        total + max_total * 0.005,
        str(int(total)),
        ha="center",
        va="bottom",
        fontsize=label_fontsize,
        fontweight="normal",   # not bold
        color="#333333",
        clip_on=True,
    )

# ── 9. Axes & labels ─────────────────────────────────────────────────────────

ax.set_xlim(min(years) - 0.75, max(years) + 0.75)
ax.set_ylim(0, 1550)

ax.set_xlabel("")
ax.set_ylabel("")

# X-axis: every year, 45° below axis, no tick dashes
ax.set_xticks(years)
ax.set_xticklabels(
    [str(y) for y in years],
    fontsize=9,
    rotation=45,
    ha="right",
    va="top",
    rotation_mode="anchor",
)
ax.tick_params(axis="x", which="both", length=0, pad=4)   # length=0 → no dash

# Y-axis left: major ticks every 50 planets, no tick dashes
ax.yaxis.set_major_locator(MultipleLocator(50))
ax.tick_params(axis="y", which="both", labelsize=10, length=0,
               left=True, right=False)

# Y-axis right: mirror, no tick dashes
ax_right = ax.twinx()
ax_right.set_ylim(ax.get_ylim())
ax_right.yaxis.set_major_locator(MultipleLocator(50))
ax_right.tick_params(axis="y", which="both", labelsize=10, length=0,
                     left=False, right=True)
ax_right.set_ylabel("")
for spine in ax_right.spines.values():
    spine.set_visible(False)

# Grid every 50 planets
ax.grid(axis="y", which="major", color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
ax.set_axisbelow(True)

# Remove all spines
for spine in ax.spines.values():
    spine.set_visible(False)

ax.tick_params(axis="both", which="both", top=False)

# ── 10. Save ─────────────────────────────────────────────────────────────────

# Target: width="1080pt" height="720pt" viewBox="0 0 1080 720"
# Points == pixels at 72 dpi for SVG; matplotlib uses inches so: 1080pt / 72 = 15in
OUT = "exoplanets_by_method.svg"
fig.set_size_inches(1080 / 72, 720 / 72)
plt.tight_layout()
plt.savefig(OUT, format="svg", dpi=72, bbox_inches="tight",
            metadata={"Creator": "matplotlib"})

# Post-process: inject the exact width/height/viewBox attributes into the SVG
import re
with open(OUT, "r", encoding="utf-8") as f:
    svg_text = f.read()

# Replace whatever width/height matplotlib wrote with the required values
svg_text = re.sub(r'(<svg\b[^>]*?)width="[^"]*"',  r'\1width="1080pt"',  svg_text, count=1)
svg_text = re.sub(r'(<svg\b[^>]*?)height="[^"]*"', r'\1height="720pt"',  svg_text, count=1)
svg_text = re.sub(r'(<svg\b[^>]*?)viewBox="[^"]*"',r'\1viewBox="0 0 1080 720"', svg_text, count=1)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg_text)

print(f"\n  Saved → {OUT}")
plt.close()
