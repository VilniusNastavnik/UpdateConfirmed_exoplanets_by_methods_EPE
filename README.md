# UpdateConfirmed_exoplanets_by_methods_EPE
Generate an updated version of Confirmed_exoplanets_by_methods_EPE.svg taking data from exoplanets.eu

Filter applied:
((mass:mjup<13 AND mass:mearth>0.05)
OR (mass=null AND Not radius = null)
OR (mass=null AND mass_sini:mjup < 13))
AND Not star_name = null
