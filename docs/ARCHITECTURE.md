# Architecture and operating boundaries

The FastAPI process serves the compiled React app and a same-origin JSON API. SQLite in WAL mode is adequate for two local workers and avoids a database server. Records have stable kinds/IDs; claims keep their original source, locator, stance and timestamp, while events preserve research/tool/review history. A competing claim is added rather than overwriting the original. Name normalization generates explained suggestions and never merges vessels automatically.

`connectors.py` separates discovery from evidence retrieval. NOAA REST queries paginate; downloads are bounded and cached. Interrupted raster downloads use Range plus If-Range with the source ETag/Last-Modified; without a validator they restart. Documents are preserved by content hash before text extraction. Only allowlisted HTTPS archive hosts may be fetched, including every redirect. Archive date/query keys prevent duplicate identical searches. Saved full-text documents can be searched beyond the bounded UI/model preview. Current keyword/name matching is not semantic entity resolution.

`analysis.py` validates projected metric grids, nodata, size and transforms. Raw inputs are never normalized in place. Derived PNGs are displays; geometry and measurements use source cells/CRS. Nearest valid values only support background filtering; nodata is excluded from detections and 3D triangles. Grid uncertainty bands are preserved/available; no claim is made that a two-cell floor captures full positional or segmentation uncertainty. The 3D mesh samples measured elevations and contains no generated ship detail.

`jobs.py` supplies two worker threads. Jobs, events, limits and completed research steps persist. Restart recovery marks unfinished jobs interrupted and requires explicit resume. Downloads continue where safely supported; deterministic analysis restarts from the source grid. Assistant conversation/tool checkpoints persist after each completed call. A crash between an external mutation and checkpoint can repeat that mutation; exactly-once execution is not promised. There is no distributed scheduler. Limits are soft: in-flight HTTP and numerical operations can overrun wall/cancellation boundaries; LLM token totals can overshoot by one response.

`assistant.py` implements real tool calling: native Anthropic messages and OpenAI-compatible chat adapters for the remaining providers. Configuration accepts a model ID and stores keys through a native OS keyring backend; plaintext fallback fails closed. Keys are not stored in SQLite, logs, frontend responses or reports; validation errors omit raw input values. The assistant sees selected evidence and actual tool results, with instructions to treat documents as untrusted data and separate observation, estimate and hypothesis. Saved AI notes are explicitly unreviewed. No shell, arbitrary-network or publication tool is exposed. LLM factual correctness is not guaranteed by source IDs alone; human review remains necessary.

The service binds to 127.0.0.1. Host checks and a loopback-origin mutation check reduce drive-by browser requests. Only media/derived artifacts are static; raw documents and the database are not a static directory. This is not a public authenticated service. Do not put it behind a public proxy as-is. OS-account access grants access to local research and credentials. Exports do not include keys; the readable Mystery Collier report excludes coordinates, but local database/snapshots retain geographic research data and require review before sharing.

## Module guide

- `backend/db.py`: persistence and append-only source claims/events.
- `backend/connectors.py`: NOAA coverage/products, AWOIS copy, LOC, Internet Archive and content preservation.
- `backend/analysis.py`: ingestion, operators, PCA geometry, geodetic cross-reference and sampled 3D.
- `backend/research.py`: compatibility calculation, entity suggestions and sourced report generation.
- `backend/assistant.py`: BYOK configuration, provider adapters, tools and resumable model loop.
- `backend/jobs.py`: workers, resource limits, cancellation and recovery.
- `backend/main.py`: validated API and static application serving.
- `frontend/src`: map, 2D/3D raster view and investigation/archive/job workbench.

Extension priorities are independent labelled detection validation, stronger registry/alias resolution with official identifiers, broader site workspaces, contemporary ENC refresh, georeferenced historical overlays and optional established ML inference. Current source evidence and artifacts make those extensions inspectable without pretending they are already complete.
