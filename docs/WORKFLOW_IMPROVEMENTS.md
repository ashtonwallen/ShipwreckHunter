# Survey workflow improvements — 12 October 2026

Implemented product improvements:

* Automatic bounded windows into large cached BAG/GeoTIFF originals, with hashes, transforms, source windows, uncertainty bands and empty-window accounting. Optional WGS84 processing bounds. Existing materialized GDAL subsets remain compatible. Resume preserves deterministic window IDs and reuses downloads.
* Cached raster inspection or remote HTTP size inspection before ingestion, adjustable per-product byte limit (250 MB default, 1 GB maximum), and separate download-success events. The same file cannot be concurrently downloaded by both workers.
* Every eligible detection retained in new runs. Candidates and their completed run are saved in one database transaction; cancellation cannot expose a partial new run. Existing capped runs and reviews are preserved and visibly identified.
* Paginated, filtered candidate API/MCP and workbench list; internal coordinates available by explicit request. Shared reason-required review action through REST and MCP. Catalogue sync now available through MCP.
* Close high-quality catalogue positions distinguished from broad uncertain associations. Neither label establishes identity. Catalogue records are loaded once per detector run.
* RGB sidescan white-background/alpha masking; RGB channels are no longer mistaken for elevation uncertainty. Masking is a documented heuristic, not proof of seabed absence.
* NOAA survey-ID registration when spatial discovery fails, without inventing footprint polygons. Registered surveys appear in the workbench product selector.
* Non-overlapping source excerpts, pagination and PDF page links in API/MCP and UI.
* Configurable startup port and same-origin mutation support on that port, while foreign origins remain blocked.

## Investigation scope

New investigation and the persistent selector apply across every page. Evidence, notes, sources, searches, map records, surveys, datasets, detections, jobs, assistant conversations and reports follow the selected investigation. Cached originals remain reusable. New investigations start empty; Mystery Collier is labelled as the example.

Backend tests use isolated databases and generated survey rasters. Browser investigation checks create synthetic fixtures on an isolated server. Personal investigations and research-specific validation helpers belong under ignored `data/private/`, never in published test fixtures.

## Remaining product gaps

- Catalogue reconciliation needs current ENC and descriptive-report features, including local inventories and uncertain positions.
- Coverage must distinguish measured sonar, sparse soundings, interpolated grids and contextual charts. Empty catalogue results do not establish absence of wrecks.
- Classifier calibration and detection deduplication across overlapping windows and repeated runs remain incomplete.
- Download caps apply per product; investigation-wide transfer accounting is still needed.
- Raster windowing reduces processing memory but downloads the complete original. Remote header inspection and raw sidescan decoding need further work.
- White-background sidescan masking is heuristic and can remove saturated returns.
- Inland source adapters, archive name disambiguation, structured service errors and coverage request history need improvement.
- Notes should distinguish observations, source claims, inferences and next steps independently of human review status.
