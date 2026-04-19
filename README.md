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
  • ((mass:mjup<13 AND mass:mearth>0.05)
    OR (mass=null AND Not radius = null)
    OR (mass=null AND mass_sini:mjup < 13))
    AND Not star_name = null

Output: Confirmed_exoplanets_by_methods_EPE.svg  (stacked-bar chart, 1350×900 px)

Usage:
  pip install requests pandas matplotlib
  python CreateConfirmedExoplanetsByMethodsEPE.py

Dependencies
------------
  requests  – to fetch the CSV
  pandas    – to clean and pivot data
  matplotlib – to draw and export SVG
