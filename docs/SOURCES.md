# Source and methods research

Reviewed for the first local version on 2026-10-09. Source snapshots and SHA-256 values for actual research evidence are in the application database and exported report. The following distinguishes connected resources from extension candidates.

| Resource | Use and constraints |
|---|---|
| [NOAA NOS hydrographic archive](https://www.ncei.noaa.gov/products/nos-hydrographic-survey) / [bathymetry map](https://www.ncei.noaa.gov/maps/bathymetry/) | Connected live survey-footprint discovery and per-survey download listings. Archive includes reports and gridded products; format and resolution must be assessed individually. |
| [H11277 metadata](https://www.ngdc.noaa.gov/nos/H10001-H12000/H11277.html) / [descriptive report](https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/DR/H11277.pdf) | Real 2003 Gloucester Harbor source: five 0.5 m BAG grids, original compound CRS preserved, MLLW elevation. The report contains wreck and rock observations used for limited validation. It also documents processing problems; survey cell size alone does not establish accuracy. |
| [Regional AWOIS ArcGIS copy](https://services5.arcgis.com/HDRa0B57OVrv2E1q/arcgis/rest/services/Wrecks_and_Obstructions/FeatureServer/0) | Connected spatial queries and conservative candidate cross-reference. Third-party copy of NOAA inventory, including truncated histories and uncertain positions. Not a comprehensive or independently verified wreck census. |
| [NOAA ENC downloads](https://www.charts.noaa.gov/ENCs/ENCs.shtml) | Relevant future complement to AWOIS. ENC wreck/obstruction objects are charting records with their own quality attributes. S-57/S-101 decoding and ENC refresh are not implemented in this version. |
| [Stellwagen maritime heritage](https://stellwagen.noaa.gov/maritime/) | Primary archaeological context and profiles. Mystery Collier investigation uses actual NOAA text and credited sonar/ROV illustrations. Illustrations are not treated as georeferenced rasters. |
| [Mystery Collier](https://stellwagen.noaa.gov/maritime/mystery-collier.html) | Saved structured observations, source locators, unknown fields and the profile/caption mast-count disagreement. The public profile does not supply a precise position; none is invented. |
| [Museum of Underwater Archaeology](https://mua.apps.uri.edu/in_the_field/noaa_coal.shtml) | NOAA archaeologist's coal-trade account provides additional physical context. |
| [2020 expedition account](https://kirstinmeyer.blogspot.com/2020/07/the-mystery-collier.html) | First-person ROV observations; copper-sheathing interpretation remains provisional. |
| [NPS Tay history](https://www.nps.gov/articles/000/tracking-the-schooner-tay.htm) | Sourced exclusion: apparently relevant storm damage was not its final loss. Inconsistent dimensional terminology is explicitly retained as a caution. |
| [Library of Congress](https://www.loc.gov/search/) | Connected date-bounded JSON catalogue searches; document fetching and local preservation. Search hits are not newspaper evidence until the relevant page is retrieved and checked. Tested newspaper PDF returned 403. |
| [Internet Archive](https://archive.org/advancedsearch.php) | Connected date-bounded catalogue and item-file APIs. Actual 1895 and 1903 U.S. merchant-vessel-register OCR saved. Recurring names and broken tabular OCR prevent reliable automatic record linkage; source search exposes full-text excerpts without inventing row associations. |
| [Lloyd's Register casualty returns](https://heritage.lrfoundation.org.uk/archive-library/casualty-returns) | Appropriate loss cross-check; tested hosted PDFs returned 403. Not ingested or treated as read. |
| [BOEM archaeology](https://www.boem.gov/environment/archaeology) / [geological and geophysical data](https://www.boem.gov/oil-gas-energy/resource-evaluation/geological-geophysical-gg-data) | Potential public survey/report sources; release status varies. BOEM pages can be preserved by the source fetcher. No claim of complete BOEM survey coverage or proprietary-data access. |
| [USGS data](https://cmgds.marine.usgs.gov/) | Credible bathymetry/backscatter extension source, with individual metadata and datum review required. No universal raw-survey parser is implied. |

## Detection literature and reuse

[Sethuraman et al., AI4Shipwrecks (2024)](https://arxiv.org/abs/2401.14546) describes an expert-labelled side-scan benchmark with 28 wrecks and 286 high-resolution images. It is a suitable future evaluation/training resource, not evidence that a model trained there generalizes to Massachusetts seabed, sensor types or partially buried wooden vessels. Split by wreck and survey before augmenting to avoid leakage.

[Sheppard et al., ShipwreckFinder (2025)](https://arxiv.org/abs/2509.21386) provides an open-source QGIS workflow for bathymetric preprocessing, learned segmentation and detection. The [NOAA project account](https://oceanexplorer.noaa.gov/expedition/25automated-arch/) describes the training context and recommends varied survey data and explicit treatment of gaps. Reuse and independently evaluate that pipeline before training a new architecture. This tool does not ship its weights or claim its benchmark performance.

[Unsupervised underwater shipwreck detection (Scientific Reports, 2024)](https://www.nature.com/articles/s41598-024-63501-1) investigates domain adaptation for side-scan. It motivates treating sensor/domain shift as a validation problem, rather than importing a nominal confidence score as an identification probability.

The delivered computational baseline uses Rasterio/GDAL for BAG/GeoTIFF and coordinate metadata, PyProj for geographic transformations and geodetic distances, SciPy for terrain filters and segmentation, and NumPy for PCA/geometric measurements. Two operators—Gaussian background residual and morphological white top-hat—give inspectable alternative detections. Their geometric review score is deliberately heuristic. No invented neural model or synthetic survey is used in the demonstration.

## Evaluation protocol

Parameters were fixed at 3 robust sigma and 12 m context on tile 1 before checking the held-out tile 7 labels. Nine selected point observations were transcribed from the H11277 report: PDF pages 20, 21 and 158–159; page images were visually checked. Three are labelled wreck and six rock. A hit means a point falls within 10 m of a segmented candidate bounding extent, not a verified corresponding object. The labels are neither exhaustive nor segmentation masks.

Residual screening: 95 retained candidates, proximity to 1/3 selected wreck and 2/6 rock points. Top-hat: 150 retained candidates (cap applied), proximity to 0/3 wreck and 5/6 rock points. No calibrated probability or full precision/recall is reported. This same-survey spatial holdout exposes poor discriminative performance and does not establish generalization across surveys. See `scripts/evaluate.py` and `data/exports/detection-evaluation.json` for exact feature locators, run IDs, parameters and source hash.

Priority next experiments: an archaeologist-reviewed negative/positive label set; independent survey holdouts; comparison with ShipwreckFinder; sonar intensity and acoustic-shadow evidence where original mosaics permit it; and documented false-positive review. A candidate with no loaded catalogue match remains an unexplained terrain feature until investigated.
