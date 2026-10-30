# Shipwreck Hunting Tool

A local workbench for shipwreck research. It maps NOAA seafloor surveys and
wreck records, screens bathymetry for wreck-like terrain, searches historical
archives, and keeps every claim tied to its source. No paid service is needed.

![Mystery Collier wreck profile with NOAA side-scan sonar imagery and sonar-derived dimensions](docs/screenshots/investigate.png)

![Survey workbench comparing measured NOAA multibeam bathymetry with the terrain-residual detector output](docs/screenshots/survey.png)

## Start

Needs Python 3.12+ and Node.js 22+.

```powershell
python start.py     # or .\start.ps1; --port 8788 if 8787 is taken
```

Open <http://127.0.0.1:8787>. The first run sets up the virtual environment
and builds the frontend. The server only listens on localhost.

## What you can do

- **Explore** NOAA survey footprints, wreck catalogue records and detected
  terrain candidates on a map.
- **Ingest surveys** (BAG or GeoTIFF bathymetry) and run terrain detectors on
  them.
- **Search archives** and save sources, then build an evidence board of claims
  that cite them.
- **Compare vessels** against a wreck's measured profile.
- **Ask the assistant** using your own model, or connect any MCP client.

Each investigation keeps its own sources, surveys, notes and report. The
**Mystery Collier** sample shows a full worked example. Your research stays in
the git-ignored `data/` folder.

## MCP

The app serves MCP at `http://127.0.0.1:8787/mcp`. For stdio clients like
Claude Desktop:

```powershell
.venv\Scripts\python mcp_stdio.py --print-config
```

Every tool call is logged in **Jobs**. See [docs/MCP.md](docs/MCP.md).

## Results so far

- The Mystery Collier is still unidentified. Leading candidates have been
  ruled out, but there's no defensible identity yet.
- On real NOAA multibeam data, the detectors find terrain candidates, not
  confirmed wrecks. They miss some wrecks and flag some rocks. No new wreck has
  been validated.

## Tests

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m scripts.evaluate
```

## Limits

- Handles projected, north-up BAG and GeoTIFF grids. It doesn't decode raw
  sonar formats or use trained ML models.
- Archive search finds real records, but it isn't a complete census.
- It's single-user, with no authentication, so keep it on localhost.
- Get expert archaeological review before calling an anomaly a wreck.

More: [architecture](docs/ARCHITECTURE.md) · [sources and methods](docs/SOURCES.md)
· [validation](docs/VALIDATION.md)

MIT License.
