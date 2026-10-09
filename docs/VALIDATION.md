# Validation record

Validated locally on 2026-10-09 with Python 3.13.15, Node 22, Windows and headless Chrome.

- `python -m pytest -q`: **31 passed**, 4.62 s. One upstream Starlette/httpx deprecation warning; no test failures. Includes original BAG preservation/CRS, nodata/flat terrain, metric segmentation, 3D gaps, cancellation, source conflict preservation, entity-link explanations, credential redaction, five provider message adapters, real tool execution against test data, resume checkpoints, follow-up context, full-source search and literal OCR preservation.
- `npm run build`: TypeScript and production bundle passed. MapLibre's large vendor chunk triggers a size advisory; no compilation failure.
- `node validate.mjs`: Chrome passed the map, historical comparisons, two-point measurement, real 3D canvas, evaluation display, full registry search and empty credential-field checks. No page errors. Screenshots in `data/exports`.
- Live NOAA H11277 discovery returned **31 products**. Five original **0.5 m BAG grids**, **28 survey footprints** and **245 regional catalogue wreck/obstruction records** are saved.
- Live Library of Congress search initially timed out. Retry succeeded with **20 results**; Internet Archive returned **11 results** for the tested date-bounded query. Failures are displayed and not cached as permanent successes. Register full-text search covered **2,797,169 characters** in the 1895 OCR; original bytes and hashes remain preserved.
- Actual background analysis job `7a9b6f3f89df45b7` completed and saved **35 terrain candidates** on H11277 tile 1. A separate six-step evidence audit `0b2ca20e94ab4e64` completed and saved its source-backed report and actual search results.
- Source/raster hashes, every saved run's images and candidate references were verified by `scripts.verify_data`.
- `start.ps1` installed/checked requirements and started the production service on **127.0.0.1:8787**.

Machine-readable results: `data/exports/browser-validation.json`, `live-validation.json`, `data-validation.json`, and `detection-evaluation.json`.

No live cloud LLM call was made because no credentials were configured. Provider adapters and tool-loop behavior were exercised with fixtures; compatibility still depends on the selected model's tool support. No new wreck or named Mystery Collier identification has been validated. The limited held-out report-point evaluation shows false positives and missed known wrecks; see `SOURCES.md` and the exported investigation report.
