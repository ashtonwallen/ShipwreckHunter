# Shipwreck Hunting Tool

Local maritime investigation workbench. Opens directly to a map with real NOAA survey footprints, catalogue wreck records, and computed terrain candidates. Python/FastAPI, SQLite, Rasterio/SciPy, React/TypeScript, MapLibre and Three.js. No paid service is required for the map, archive search, evidence audit, survey analysis or reports.

## Start

From this directory:

```powershell
python start.py
```

Or on Windows: `.\start.ps1`. Open **http://127.0.0.1:8787**. Ctrl+C stops the server. The starter creates the virtual environment, installs pinned Python dependencies and builds the frontend when needed. It never starts a public listener.

Requires Python 3.12+ (tested with 3.13.15), Node.js 22+ and npm for a fresh frontend build. Rasterio binary wheels include GDAL; no separate database or Docker installation is needed. Initial package installation needs internet access. Subsequent startup uses saved data. The ocean basemap and new source searches need internet; the saved coastline and research data remain local.

## Try the saved investigation

1. **Explore:** inspect the 28 saved NOAA survey footprints and 245 regional wreck/obstruction records. Use the region control to select two corners, then find NOAA surveys or refresh wreck records. Catalogue position symbols explicitly distinguish uncertain positions. Mystery Collier has no invented map point.
2. **Surveys:** choose one of five ingested H11277 grids. Inspect original and residual views, adjust contrast, pan/zoom, measure two points, or rotate the measured 3D surface. Select a candidate and record a review decision with reasoning. The full provenance manifest includes source URL, SHA-256, CRS, acquisition metadata, resolution and processing versions. List NOAA products to download additional BAG/GeoTIFF products.
3. **Investigate:** read the Mystery Collier profile, compare five sourced historical leads/comparators, inspect conflicting archaeological claims, and run the evidence audit. The exported report includes contrary evidence and research limits. Use Report to print/save the HTML view, or Export for Markdown; `/api/report?format=json` returns structured records.
4. **Archives:** search Library of Congress or Internet Archive by date, list register scans/OCR, preserve a source URL, and search the full cached text. Source content is untrusted evidence; inspect page images before associating OCR numbers with a vessel.
5. **Research assistant:** open provider settings, choose OpenAI, Anthropic, Gemini, OpenRouter or a local OpenAI-compatible endpoint, and enter a tool-capable model ID. Cloud keys go only into the OS credential manager. Local endpoints must use loopback. No model/key is preselected or purchased. Chat can search archives, read sources, compare vessels, discover surveys, queue ingestion/analysis, inspect jobs and save explicitly unreviewed hypotheses. Follow-up messages reuse the preceding conversation. Each actual tool result is inspectable in Jobs.

## What the saved evidence establishes

The Mystery Collier remains unidentified. Its source-backed profile, five comparative vessel records, historical registry OCR and a ranked list of sparse leads/exclusions are saved. **There is no defensible leading named identity yet.** Actor and Active have incomplete specifications and spatial mismatches; Tay, Frank A. Palmer and Louise B. Crary are exclusions, not proposed solutions. The generated report is written locally to `data/exports/mystery-collier.md`.

Five real 0.5 m NOAA H11277 BAG tiles from Gloucester Harbor have been ingested and analyzed. This is a separate site from Mystery Collier. The classical detectors produce terrain-screening candidates, not shipwreck classifications. On nine selected report points in a held-out tile, residual screening put candidate extents within 10 m of 1/3 wreck and 2/6 rock points; top-hat screening gave 0/3 and 5/6. This deliberately visible result demonstrates missed wrecks and geological false positives. **No new wreck has been validated.** Protocol and results are written locally to `data/exports/detection-evaluation.json`.

## Reproduce and test

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m scripts.evaluate
.venv\Scripts\python -m scripts.export_snapshot
cd frontend
npm run build
node validate.mjs
```

The browser smoke test requires Chrome and the server on port 8787. Unit/integration tests isolate their database. They include a real saved BAG, geometric correctness, nodata handling, catalogue uncertainty, conflicting claims, credential redaction, provider message formats and checkpoint resumption. Provider adapters are tested with recorded-shape fixtures; no live paid model call has been made.

`python -m scripts.seed` reconstructs the initial demonstration from the saved `data/research` snapshots and five original BAG files (and fetches missing source documents). **Use a backup or a separate data directory when rebuilding**: it refreshes seeded site/vessel records, while source claims remain append-only. `scripts.evaluate` reuses matching fixed-parameter runs. All source data and demonstrations are already saved; normal startup does not rerun them.

For development, run `.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8787 --reload` and `npm run dev` inside `frontend`. The Vite proxy uses port 5173. API docs: http://127.0.0.1:8787/docs.

## Scope and limits

- Supports north-up projected metre BAG and GeoTIFF grids, up to 12 million cells, 250 MB per downloaded product; bounded document retrieval is 25 MB / first 300 PDF pages. Original files remain intact. Geographic, rotated, oversized or unreferenced rasters are rejected rather than assigned invented coordinates. Use a documented GDAL reprojection/subset first.
- Side-scan GeoTIFF supports intensity screening; raw XTF/JSF/swath decoding, sonar slant-range correction and trained hull/shadow recognition are not implemented. The tested end-to-end demonstration is multibeam bathymetry.
- No calibrated probabilities, trained ML model, exhaustive ground truth or independent-survey generalization claim. Report feature point checks are limited, and candidate extent proximity does not prove object equivalence. Grid cell size is not absolute positional accuracy.
- Archive searches retrieve real catalogue records and documents, not a complete vessel/casualty census. OCR column order can be wrong. Some historical scans returned 403 or TLS errors. The app records inaccessible sources without inventing their contents.
- Two background workers; cancellation at network/processing checkpoints; configurable soft step/token/wall budgets. A running network call can delay cancellation. Analysis restarts deterministically on resume; transfers resume only with an HTTP validator. Research resumes completed steps/tool calls. A crash during a mutating tool can replay that tool; inspect history before resuming.
- Chat requires a configured tool-capable provider. Some models have different token parameters or lack tool support and will return an explicit provider error. No price/cost ceiling can be guaranteed from tokens alone. Prompts and selected evidence are sent to the chosen provider.
- Historical overlays, raw sonar decoding, generalized multi-site investigations, BOEM/ENC ingestion and ML training are future work. See [source and methods research](docs/SOURCES.md) and [architecture](docs/ARCHITECTURE.md).

## Data and credentials

`data/raw` contains original survey products; `sources` holds content-addressed original bytes and extracted text; `derived` holds analytical artifacts; `research` holds acquisition snapshots; `exports` holds reports and evaluation results. SQLite stores records, original claims, research history, jobs and settings **without credentials**. The initial database and raw demonstration files are part of this local deliverable; keep them when moving the project. Additional downloaded probe tiles remain in `raw` for inspection but are not all ingested.

Back up `data` after stopping the server, or use SQLite's backup API. `scripts.export_snapshot` produces a credential-free portable record snapshot; do not publish it automatically because catalogue/candidate coordinates remain in local records. The human-readable investigation report withholds coordinates. No public publishing or heritage-authority messaging is performed. Seek expert archaeological review before describing an anomaly as a wreck or an identity as established. Keep the service on loopback: this version has no multi-user authentication.
