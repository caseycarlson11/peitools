This project is PEItools.com — an internal web toolset for Pacific Erectors Inc., a metal panel siding installation company operating in the Sacramento and Bay Area.

## Working Rules

- **Suggest better approaches proactively.** If Casey describes what he wants to accomplish and there is a better, more reliable, or simpler way to do it technically, suggest it before building the original approach. Explain it in plain language — no assumed coding knowledge. Describe what the difference is in terms of real-world outcome (faster, never fails, easier to maintain, etc.), not in terms of code mechanics.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

LLMs often pick an interpretation silently and run with it. This principle forces explicit reasoning:

State assumptions explicitly — If uncertain, ask rather than guess
Present multiple interpretations — Don't pick silently when ambiguity exists
Push back when warranted — If a simpler approach exists, say so
Stop when confused — Name what's unclear and ask for clarification

2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

Combat the tendency toward overengineering:

No features beyond what was asked
No abstractions for single-use code
No "flexibility" or "configurability" that wasn't requested
No error handling for impossible scenarios
If 200 lines could be 50, rewrite it
The test: Would a senior engineer say this is overcomplicated? If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting
Don't refactor things that aren't broken
Match existing style, even if you'd do it differently
If you notice unrelated dead code, mention it — don't delete it
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused
Don't remove pre-existing dead code unless asked
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform imperative tasks into verifiable goals:

Instead of...	Transform to...
"Add validation"	"Write tests for invalid inputs, then make them pass"
"Fix the bug"	"Write a test that reproduces it, then make it pass"
"Refactor X"	"Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let the LLM loop independently. Weak criteria ("make it work") require constant clarification.

## Company & Workflow

Pacific Erectors installs metal deck and metal panel siding. The workflow:
1. Architect collaborates with the project manager and a detailer to produce blueprints in CAD (.dwg or .dxf)
2. CAD files are converted to PDF blueprints with added context for field foremen
3. Panels are ordered using Fabrication Sheets sent to KPS (panel fabricator in Canada)
4. Fab sheets can be altered in the field or by the project manager before sending
5. KPS manufactures panels, ships them to the jobsite packed in skids with packing lists
6. Packing lists tell the installer which panel is in which skid

**Key roles:** Project managers (office, computers), Field foremen (iPads), KPS (panel fabricator, Canada)

## File Types

- **CAD Files** (.dwg, .dxf): Source files from detailer/engineer showing panel layout
- **Blueprints** (PDF): Exported CAD with added field context. Used by PMs and foremen. KPS blueprints have callout circles (N/Dx format) referencing detail pages
- **Fab Sheets** (PDF): Individual panel dimension files sent to KPS for manufacturing. Can be altered before sending
- **Packing Lists** (PDF): Created by KPS at shipment. Lists panel → crate/skid mapping

## Live Site

- **URL:** https://peitools.com
- **Stack:** Flask + Gunicorn in Docker, Nginx reverse proxy, Hostinger VPS (Ubuntu 24.04)
- **Server IP:** 93.188.160.121
- **GitHub:** https://github.com/caseycarlson11/peitools.git

## Local Development

- **Project folder:** `C:\Users\ROG\Documents\Pacific Erectors\PEItools.com`
- **Start local server:** double-click `run_local.bat` → http://localhost:5000
- **Editor:** VS Code — open project folder, Ctrl+S to save, browser auto-reloads
- **Deploy to live:** run `deploy_quick.bat` in CMD (one password prompt, ~15 seconds)
- **Full rebuild deploy:** `deploy.bat` (only needed when requirements.txt or Dockerfile changes)
- **Test OCR engine locally:** `python test_engine.py "path/to/blueprint.pdf" --pages 1-5`

## Tools Built

1. **Fab Sheet Editor** (`/sheet_editor`) — PDF markup tool for annotating fab sheets before sending to KPS
2. **Panel Sheet Extractor** (`/sheet_extractor`) — Reads DXF files, extracts panel/sheet mappings, exports CSV
3. **Field Compass** (`/field-compass`) — iPad/mobile tool that overlays compass on blueprint PDFs so foremen can orient blueprints to the building
4. **Blueprint Viewer** (`/blueprints`) — Browse all jobs and their files (blueprints, packing lists, fab sheets), create shareable links
5. **Blueprint Hyperlinks** (`/blueprint/hyperlinks`) — Processes KPS blueprint PDFs to add clickable orange hyperlinks on callout circles (N/Dx symbols), linking to the correct detail page. Includes a full in-browser PDF editor.
6. **Packing List Tracker** (`/packing-list-tracker`) — Parses KPS packing lists and highlights delivered panels on the blueprint by shipment color; interactive cross-reference editor.
7. **Panel Print Mapper** (`/panel-print-mapper`) — Boxes every panel on a blueprint in red with its number labeled, so you can verify panel numbers are read correctly. Page selector → optional scan or hand-placement → interactive panel editor → publishes a full merged doc + a `panels_only` doc into the Blueprint Viewer's "Panel Mapper" folder. Step one toward making prints readable by the Packing List Tracker. (See PROJECT_NOTES.md for full detail.)
8. **Admin** (`/admin`) — Upload and manage files per job
9. **Public Links** (`/public-links`) — One permanent PUBLIC (no-login) link per document slot, per job. Six slots: Marked-Up Prints + Panels-Only Prints (hand-picked PDF from Blueprints/Panel Mapper folders), All Packing Lists + All Fab Sheets (auto-merged single PDF of the whole folder, rebuilt automatically when contents change, bookmark per source file, cached in `<job>/Public Links/`), Job Spreadsheet (SheetJS viewer + Download + Open-in-Google-Sheets using the job's linked `_sheets_url.json`, copies TSV for pasting), and Job Page (public landing page listing all live docs). Publish = swap the document behind the link (the LINK NEVER CHANGES); New Link = rotate token, old link dies instantly (access kill switch); Disable = kill without replacement. Store: `<JOBS_DIR>/.public_links.json` = `{job: {slot: {token, file, published}}}`. Public routes: `/pl/<token>` (viewer) and `/pl/<token>/file` (raw, `?dl=1` = download). Templates: `public_links.html` (admin), `public_doc_view.html`, `public_sheet_view.html`, `public_job_page.html`. NOT yet wired into Panel Tracking's publish buttons (planned next).
10. **Panel Tracking** (`/panel-tracking`) — Combined job-centric tool: pick a job once, then work through tabs — Overview (delivery stats + step status), Panel Map, Deliveries, Review, Documents, Fab Sheets. Built from NEW page copies (`pt_base.html`, `panel_tracking.html`, `pt_map.html`, `pt_map_editor.html`, `pt_deliveries.html`, `pt_review.html`, `pt_documents.html`, `pt_fab.html`) that consume the SAME existing APIs and stored job data (`ship_colors.json`, `delivery_state.json`, panel locations) so shipment colors stay constant with the standalone tools. The original four tools are untouched and still work independently. `panel_tracking.html` and `pt_deliveries.html`/`pt_review.html` carry their own copy of the `SHIP_COLORS` palette — keep it identical to the others (no red).

## Jobs Folder Structure

Server: `/var/www/pei-jobs/<Job Name>/`
```
Blueprints/           <- PDF blueprints (may include linked versions)
Blueprints/Old Versions/  <- Archived originals replaced by Publish Prints
Packing Lists/        <- KPS packing list PDFs
Fab Sheets/           <- Fab sheet PDFs
DXF CAD FILE/         <- DXF and DWG CAD files
Delivery Tracking/    <- Packing List Tracker state/output (auto-created)
Panel Mapper/         <- Panel Print Mapper output: "<bp> - Panel Mapper.pdf" (full) + "<bp> - panels_only.pdf" (auto-created; shown as a Blueprint Viewer category)
Panel Map/            <- Panel Print Mapper working files: session.json, locs cache, trimmed/map/full PDFs (auto-created, internal)
```

## Current Jobs on Server
- Equinix
- Modesto Courthouse
- SFPUC Bldg 600
- SFPUC Bldg 615
- UCSF Parnassus
- Vantage Data Center NV11
- Workday

## Key Technical Notes

- KPS blueprint callout circles: bisected circles with format N/Dx (e.g., 1/D5) — top half = detail number (1–9), bottom half = D-page reference (D1–D23)
- Blueprint Hyperlinks OCR engine: detects circles geometrically, OCRs bottom half only (speed-first approach), links to D-pages detected by largest-font text scan
- Field Compass pins: placed using inverse transform math (rotation + scale + pan) so pins stay fixed to document coordinates at any zoom/rotate/pan
- TEMPLATES_AUTO_RELOAD=True: template changes show on browser refresh without Flask restart
- deploy_quick.bat uses `docker cp` to copy files directly into running container (no Docker rebuild)
- All job files live on Docker volume `/var/www/pei-jobs` — persist across deploys, NOT in git
- Panel Print Mapper engine reuses the Packing List Tracker's DXF→PDF panel locator (`scan_blueprint_panels` in `packing_list_engine.py`); `generate_panel_map_blueprint` draws the red boxes + number labels and now supports per-instance `label`/`rel` metadata for duplicate panels
- "Panel Mapper" was added to `CATEGORIES` in app.py so the Blueprint Viewer shows that folder as a tab
- `templates/panel_map_editor.html` is a standalone (non-base) PDF.js editor; it re-rasterizes pages at the zoom level for crisp detail and stores panel positions as `{key: {page, bbox, label?, rel?}}`
- Shipment (packing list) colors: a color is ASSIGNED WHEN A PACKING LIST IS FIRST PROCESSED and STORED in `Delivery Tracking/ship_colors.json` (`_pl_assign_colors()` in app.py, lowest unused index, first-seen) — it never changes and is reused identically by the tracker UI, the editor, and the baked prints (engine `generate_tracked_blueprint*` take a `shipment_colors=` arg). Do NOT hardcode a shipment→color. NEVER use red (reserved for the Panel Mapper boxes). Keep the three palettes IDENTICAL (same order/values, no red): `_SHIPMENT_COLORS` (packing_list_engine.py, exact RGB) and `SHIP_COLORS[]` in both packing_list_editor.html and packing_list_tracker.html.
- Panel highlights are drawn with NO border (fill only) everywhere — a border straddles the box edge and hides the printed panel number. Enforced in 3 places (keep it this way for all jobs, current and future): (1) `generate_tracked_blueprint` and (2) `generate_tracked_blueprint_panel_map` in `packing_list_engine.py` use `page.draw_rect(rect, color=None, fill=..., fill_opacity=0.45, width=0)` (NOT `add_rect_annot` with a stroke); (3) `packing_list_editor.html` draws delivered panels in panels_only mode as `.pbox.delivered` (border:0) with only an inline background color — never `.pbox.pending-add` (which has a 1.5px border)
