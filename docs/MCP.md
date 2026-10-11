# MCP connection and research tools

Shipwreck Hunter exposes its existing research and survey operations through the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). A connected assistant chooses and executes the research steps using its own model. The app does not invoke another LLM or need a provider key for MCP requests.

## Start the app

Run `python start.py` from the project directory. If an older copy is running, stop it with Ctrl+C and restart so the new dependencies and endpoint load. The normal starter installs the pinned dependencies. For an existing development environment, `.venv\Scripts\python -m pip install -r requirements.txt` also installs them.

The website remains at `http://127.0.0.1:8787`; the MCP endpoint is `http://127.0.0.1:8787/mcp`. This endpoint uses Streamable HTTP, not legacy SSE. It is available for as long as the app is running.

## Claude Desktop and other stdio clients

Generate a configuration with paths for this checkout:

```powershell
.venv\Scripts\python mcp_stdio.py --print-config
```

Merge the generated `shipwreck-hunter` entry into the `mcpServers` object in your desktop client's configuration. For Claude Desktop on Windows, that file is normally `%APPDATA%\Claude\claude_desktop_config.json`; use its developer settings to open the configuration. Keep existing server entries. Restart the desktop client after changing it. The [official SDK host guide](https://py.sdk.modelcontextprotocol.io/get-started/real-host/) documents this configuration format.

The result has this shape (the command above supplies real paths):

```json
{
  "mcpServers": {
    "shipwreck-hunter": {
      "command": "C:\\path\\to\\ShipwreckHunter\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\ShipwreckHunter\\mcp_stdio.py", "--url", "http://127.0.0.1:8787/mcp"]
    }
  }
}
```

The app must already be running. This launcher uses absolute paths and works regardless of the client's working directory. It only forwards MCP requests; it does not start another database owner or worker pool. Multiple clients therefore share the same research records and jobs. Standard output is reserved for MCP messages and connection errors go to standard error.

If you run the app on a different loopback port, add `--url http://127.0.0.1:PORT/mcp` to the configuration-generation command. On macOS/Linux use `.venv/bin/python` in place of `.venv\Scripts\python`; regenerate the configuration on that machine.

## HTTP clients and local models

In a client with Streamable HTTP support, add a server named `shipwreck-hunter` with URL `http://127.0.0.1:8787/mcp`. No authorization header is required for this local service. If the client only supports stdio, use the launcher above.

A local model needs an MCP-capable host that can discover tools, send tool calls, and feed results back into the model. Merely serving an OpenAI-compatible inference endpoint does not do this. Choose a model with tool calling, connect the MCP server in its host, and enable the research tools. The host controls its own tool approvals, context window, inference costs and research budget.

This loopback endpoint is for software running on this computer. A cloud-hosted connector cannot reach your computer's `127.0.0.1`. The app has no remote authentication; do not publish or tunnel this endpoint as-is.

## Tools

| Work | Tools |
| --- | --- |
| Investigation | `get_investigation`, `compare_vessels`, `get_report` |
| Archive discovery | `search_archive`, `archive_files`, `search_history` |
| Source evidence | `read_source`, `list_sources`, `get_saved_source`, `search_source` |
| Research notes | `save_research_note`, `list_research_notes` |
| Survey discovery | `list_surveys`, `discover_surveys`, `survey_products` |
| Survey processing | `ingest_survey`, `start_analysis`, `list_detections` |
| Jobs | `list_jobs`, `job_status`, `cancel_job`, `resume_job`, `start_evidence_audit` |

Each tool advertises a validated JSON input schema and read/write/network annotations. No provider settings, credentials, arbitrary shell commands, filesystem paths or publication operations are exposed. Read-only annotations describe research effects; successful read calls still create local audit records.

`list_sources`, `list_research_notes` and `list_jobs` accept `offset` and `limit` (default 30, maximum 100), returning `items`, `total` and `next_offset`. `get_saved_source` reads up to 18,000 characters from a saved source by offset and returns `next_offset`; this can reach text beyond the app's initial preview. `search_source` searches the full saved document. `search_history` returns metadata without large source bodies.

`read_source` preserves an allowlisted public archive URL and returns a bounded text preview. A response with `status: unavailable` means the document could not be retrieved, not that its contents are known. Existing source URL restrictions, file-size limits, hashes and provenance apply. Notes require saved source IDs and remain **AI hypothesis; unreviewed**; they do not alter established vessel records or reviewed claims.

Ingestion, analysis and evidence audits return a queued job. Poll `job_status` to inspect the actual result and saved events. Cancellation is cooperative and can wait for current network/processing work. MCP can resume unfinished ingestion, analysis and fixed audit jobs; it cannot start or resume a paid/provider-backed assistant job. `start_evidence_audit` runs the existing fixed Mystery Collier audit; it is not a second autonomous model.

All schema-valid MCP calls have a `kind: mcp` entry in **Jobs**, including failed calls, with inputs and results in the details. Long-running jobs have their own separate entries. MCP call records cannot be resumed from the app: inspect the saved result and retry through the client when appropriate. Disconnecting a client does not cancel an already queued job. An interrupted call may have completed a mutation before its reply was lost; check notes/jobs before retrying.

## Example request

> Use Shipwreck Hunter to investigate the Mystery Collier's historical leads. Read the current investigation and prior notes first. Make at most six archive searches, retrieve promising primary sources, and search their full text. Compare the findings against the saved vessel evidence. Save a source-linked note with page or character locators, contradictory evidence, and remaining questions. Report what is supported and what remains unknown. Do not start survey downloads for this task.

For surveys, the sequence is `list_surveys` / `discover_surveys` → `survey_products` → `ingest_survey` → `job_status` → `start_analysis` → `job_status` → `list_detections`. Bounding boxes use `[west, south, east, north]` in WGS84 degrees. The saved Gloucester survey demonstration and Mystery Collier investigation are different sites. Screening candidates are not confirmed wrecks, and vessel compatibility scores are not identity probabilities.

Source text is untrusted evidence, never instructions. Internal survey records may contain coordinates. The connected host receives requested records; keep sensitive coordinates out of public responses. The host's model, tool support and approval settings determine how independently it can research; MCP supplies tools, not an always-running agent.

## Troubleshooting and verification

- **Cannot communicate:** start/restart the app, check `/api/health`, confirm the URL, then reconnect the client.
- **No tools:** use the MCP endpoint rather than the website URL, select Streamable HTTP rather than SSE, or use the stdio configuration.
- **Tool error:** inspect the returned error and schema. Use a saved source/dataset/survey ID. Unknown tools and invalid fields are rejected before execution.
- **No archive results:** inspect `status` and `error`; unavailable archives and empty results have different meanings.
- **Large context:** page through saved sources and use full-text search instead of requesting every document body.

Tests use isolated databases and cover tool discovery, a source-to-note-to-report workflow, source offsets beyond preview limits, audit persistence, invalid arguments, redacted failures, job controls, HTTP host/origin checks, and a real stdio subprocess talking to the HTTP app:

```powershell
.venv\Scripts\python -m pytest tests/test_mcp.py -q
```
