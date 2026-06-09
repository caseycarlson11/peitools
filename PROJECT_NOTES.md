# PEItools.com — Project Notes

## ⚠️ Global Collaboration Rule

**Suggest better approaches proactively.** If Casey describes what he wants to accomplish and there is a better, more reliable, or simpler way to do it, suggest it first — before building what was asked. Explain it in plain language with no assumed coding knowledge. Focus on the real-world outcome: why is it faster, why does it never fail, why is it easier to maintain. Example: Casey asked for OCR to read KPS packing lists → the right answer was to read the embedded text directly (instant, never fails) and only use OCR as a fallback for scanned documents. That kind of suggestion should always come first.

---

## ⚠️ Global Development Priority

**This system is multi-project.** All code must be written with the assumption that many different jobs will be processed — each with their own blueprints, packing lists, fab sheets, and Panel Mapper data. Prints and packing lists follow the same format across jobs, but panel counts, sheet counts, panel numbering conventions, and file names will vary per job.

**Requirements for all new code:**
- Never hardcode job names, panel counts, page counts, or file paths
- All logic must generalize across any job in `/app/jobs/`
- When iterating panels or sheets, handle variable quantities gracefully
- Panel identifiers may include numbers, letters, symbols, and duplicates (e.g. "9R", "211A", "T-1")
- Avoid assumptions about how many shipments, skids, or packing list files a job has
- File lookups should be case-insensitive and tolerant of naming variation where practical

---

## Overview
Internal web toolset for Pacific Erectors Inc. (metal panel siding installation).
URL: **https://peitools.com**

---

## Server Infrastructure

| Item | Value |
|------|-------|
| VPS | Hostinger Ubuntu 24.04 |
| IP | 93.188.160.121 |
| SSH | `ssh root@93.188.160.121` |
| App | Flask + Gunicorn in Docker, port 5000 |
| Reverse proxy | Nginx (SSL via Certbot) |
| Docker container | `panelmapper` |
| Jobs volume | `/var/www/pei-jobs` → `/app/jobs` inside container |
| Code location | `/var/www/panelmapper/` |
| GitHub repo | https://github.com/caseycarlson11/peitools.git |

### Nginx config
- Proxy timeouts set to 300s (required for Blueprint Hyperlinks OCR processing)
- Config at `/etc/nginx/sites-enabled/panelmapper`

### Key server commands
```bash
docker logs panelmapper --tail 30
docker stop panelmapper; docker rm panelmapper
docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper
```

---

## Local Development Setup

| Item | Value |
|------|-------|
| Project folder | `C:\Users\ROG\Documents\Pacific Erectors\PEItools.com` |
| Git working copy | `C:\temp\peitools` (no spaces — required for git) |
| Local server | `run_local.bat` → http://localhost:5000 |
| Editor | VS Code |
| Tesseract | v5.5.0 (required for Blueprint Hyperlinks OCR and Packing List Tracker) |

### Deploy scripts

**`deploy_quick.bat`** — use this 99% of the time
- Copies: `app.py`, `packing_list_engine.py`, `templates/`, `static/`, `BlueprintLinker/`
- Falls back to `docker restart` if container was stopped
- Takes ~15 seconds, one password prompt

**`deploy.bat`** — only when requirements.txt or Dockerfile changes (full rebuild ~5 min). Uses `git fetch + git reset --hard origin/main` on the server (not `git pull`) to cleanly overwrite server-side changes left by deploy_quick.bat. Always run from `C:\Users\ROG\Documents\Pacific Erectors\PEItools.com`, not from `C:\temp\peitools`.

---

## File Structure
```
PEItools.com/
├── app.py                         # Flask routes (main backend)
├── packing_list_engine.py         # Packing List Tracker engine (OCR + PDF annotation)
├── requirements.txt               # flask, gunicorn, pymupdf, pytesseract, pillow, ezdxf, openpyxl
├── Dockerfile                     # Includes tesseract-ocr install
├── run_local.bat
├── deploy_quick.bat               # Fast deploy — now includes packing_list_engine.py
├── deploy.bat
├── static/
│   ├── bg.jpg                     # Background image (used on all pages via base.html)
│   ├── logo.jpg                   # PEI logo (home link on all tool pages)
│   ├── favicon.png / favicon.ico
│   └── editmode.js
├── templates/
│   ├── base.html                  # BASE TEMPLATE — all new pages extend this
│   ├── index.html                 # Landing page
│   ├── login.html
│   ├── blueprints.html
│   ├── field_compass.html
│   ├── compass_share.html
│   ├── admin.html
│   ├── share_view.html
│   ├── sheet_editor.html
│   ├── panel_sheet_mapper.html
│   ├── packing_list_tracker.html  # Packing List Tracker (extends base.html)
│   ├── blueprint_hyperlinks.html
│   └── blueprint_hyperlinks_editor.html
└── BlueprintLinker/
    ├── callout_engine.py
    ├── callout_engine_v1_backup.py
    ├── build_final.py
    └── run_detection.py
```

---

## Tools / Routes

| Route | Description | Auth |
|-------|-------------|------|
| `/` | Landing page | Login required |
| `/login` | Sign in | Public |
| `/logout` | Sign out | Public |
| `/sheet_editor` | Fab Sheet PDF markup editor | Login required |
| `/sheet_extractor` | DXF → panel/sheet mapping | Login required |
| `/blueprints` | Document Viewer (alias — redirects to `/documents`) | Login required |
| `/documents` | Document Viewer (jobs + files) | Login required |
| `/field-compass` | Field Compass with PDF viewer | Login required |
| `/admin` | Upload/manage files (password: PEI2024) | Login required |
| `/blueprint/hyperlinks` | Blueprint Hyperlinks tool | Login required |
| `/packing-list-tracker` | Packing List Tracker | Login required |
| `/api/packing-list/upload/<job>` | Upload & process a packing list PDF | Login required |
| `/api/packing-list/process-file/<job>` | Process a server-side packing list by filename | Login required |
| `/api/packing-list/status/<job>` | Poll processing status + per-shipment delivery stats | Login required |
| `/api/packing-list/download/<job>` | Download tracked blueprint PDF | Login required |
| `/api/packing-list/publish/<job>` | Copy tracked PDF to Blueprints folder (numbered prefix) | Login required |
| `/api/packing-list/reset/<job>` | Clear delivery state for a job | Login required |
| `/packing-list/editor/<job>` | Interactive split-screen cross-reference editor | Login required |
| `/api/packing-list/editor-data/<job>` | Panel locations, delivery state, shipments, page dims, PL list | Login required |
| `/api/packing-list/blueprint/<job>` | Serve base (un-annotated) blueprint PDF | Login required |
| `/api/packing-list/pl-file/<job>?file=` | Serve a packing list PDF for the right pane | Login required |
| `/api/packing-list/pl-positions/<job>?file=` | OCR panel-number positions on a packing list (cached) | Login required |
| `/api/packing-list/update-panels/<job>` | Add/remove delivered panels, regenerate tracked PDF | Login required |
| `/panel-print-mapper` | Panel Print Mapper landing (job + blueprint picker, page selector) | Login required |
| `/api/panel-map/blueprints/<job>` | List sources from Blueprints + Panel Mapper folders (+has_dxf, has_session) | Login required |
| `/api/panel-map/process/<job>` | Scan selected pages, draw panel map (body: blueprint, folder, pages, rescan) | Login required |
| `/api/panel-map/load-only/<job>` | Set up editor on selected pages with NO scan (hand-placement) | Login required |
| `/api/panel-map/status/<job>` | Poll map processing status | Login required |
| `/api/panel-map/download/<job>?blueprint=` | Marked-up pages-only map PDF | Login required |
| `/api/panel-map/download-full/<job>?blueprint=` | Full document with marked pages merged back in | Login required |
| `/panel-map/editor/<job>` | Interactive panel editor (PDF.js) — resumes saved session | Login required |
| `/api/panel-map/editor-data/<job>` | Page dims + panel_locations + blueprint name for editor | Login required |
| `/api/panel-map/base/<job>` | Serve the editor's base (scan) PDF | Login required |
| `/api/panel-map/update/<job>` | Save panels (full replace), regenerate both PDFs, publish to viewer | Login required |
| `/api/panel-map/ocr-region/<job>` | OCR a dragged rectangle → panel numbers ("Select Multiple Panels") | Login required |
| `/share/<token>` | Shared job folder | Public |
| `/compass/<token>` | Shared Field Compass | Public |
| `/api/jobs` | List all jobs | Public |
| `/api/jobs/<job>` | List files for a job (by category) | Public |
| `/api/jobs/<job>/build-spreadsheet` | Generate/update `Spreadsheets/<job>.xlsx` from delivery + panel data | Login required |
| `/api/jobs/<job>/spreadsheet-edits` | Save manual cell overrides to `<job>_overrides.json` + apply to xlsx | Login required |
| `/api/jobs/<job>/sheets-url` | GET/POST the linked Google Sheets URL for a job | Login required |
| `/files/<path>` | Serve a job file | Login required |
| `/cad-files/<path>` | Serve a DXF/CAD file | Login required |

---

## Authentication

- **Site login:** Email + password
- **Admin panel password:** `PEI2024`
- **Session:** Flask cookie-based, secret key = `"pei-tools-secret-2024"`

### User Accounts (in app.py `_USERS_RAW`)

| Email | Password |
|---|---|
| dennisa@pacificerectors.com | Andersen4460 |
| armandor@pacificerectors.com | Rivera4460 |
| arturov@pacificerectors.com | Vargas4460 |
| caseyc@pacificerectors.com | Carlson4460 |
| davida@pacificerectors.com | Arias4460 |
| elim@pacificerectors.com | Martinez4460 |
| erica@pacificerectors.com | Andersen4460 |
| glenw@pacificerectors.com | Wheeler4460 |
| gustavoh@pacificerectors.com | Hernandez4460 |
| javierm@pacificerectors.com | Arevalo4460 |
| juanc@pacificerectors.com | Camarena4460 |
| luism@pacificerectors.com | Marure4460 |
| robinp@pacificerectors.com | Pederson4460 |
| stevens@pacificerectors.com | Sousa4460 |
| thomasr@pacificerectors.com | Rowley4460 |
| tommyp@pacificerectors.com | Pearman4460 |
| miket@pacificerectors.com | Thomas4460 |
| jeffy@pacificerectors.com | Young4460 |
| jasonw@pacificerectors.com | Walters4460 |
| dalynb@pacificerectors.com | Bush4460 |
| thomasm@pacificerectors.com | McClelland4460 |
| fritzb@pacificerectors.com | Bowen4460 |
| erics@pacificerectors.com | Sidener4460 |
| debid@pacificerectors.com | Dunkin4460 |
| kellyl@pacificerectors.com | Lee4460 |
| kishag@pacificerectors.com | Gann4460 |
| jennab@pacificerectors.com | Bearden4460 |
| meganf@pacificerectors.com | Friery4460 |
| nicholaskoron@gmail.com | REDFredf |

---

## Jobs & File Storage

```
/var/www/pei-jobs/
  <Job Name>/
    Blueprints/
    Packing Lists/
    Fab Sheets/
    DXF CAD FILE/
    Blueprints/Old Versions/
    Delivery Tracking/        <- Auto-created by Packing List Tracker
      delivery_state.json         Cumulative panel→skid/shipment map
      panel_locations_v2.json     Cached blueprint panel positions (delete to force rescan)
      tracked_blueprint.pdf       Current annotated output PDF
    Panel Mapper/             <- Panel Print Mapper published output (shown in Blueprint Viewer)
      <bp> - Panel Mapper.pdf     Full doc with red-box annotations
      <bp> - panels_only.pdf      Only the annotated pages
    Panel Map/                <- Panel Print Mapper working files (internal, not in viewer)
      session.json                Saved editor session (blueprint, pages, panel locations)
      panel_locations_v2.json     Panel locations cache (shared with PL Tracker)
    Spreadsheets/             <- Auto-created by Document Viewer spreadsheet feature
      <Job Name>.xlsx             Panel data spreadsheet (Panel #, Sheet #, Order #, Packing List, Date Delivered)
      <Job Name>_overrides.json   Persistent manual cell edits keyed by {panel: {col_header: value}}
      <Job Name>_sheets_url.json  Linked Google Sheets URL for this job ({"url": "https://..."})
  .shares.json
  .compass_shares.json
```

### Current jobs on server
- Equinix
- Modesto Courthouse
- SFPUC Bldg 600
- SFPUC Bldg 615
- UCSF Parnassus
- Vantage Data Center NV11
- Workday

---

## Base Template (base.html)

All new tool pages must extend `base.html`:

```html
{% extends "base.html" %}
{% block title %}My Tool{% endblock %}
{% block extra_style %}/* page CSS */{% endblock %}
{% block content %}<!-- page HTML -->{% endblock %}
{% block scripts %}// page JS{% endblock %}
```

**Provided automatically:**
- bg.jpg background + dark overlay (matches home page)
- Semi-transparent sticky header — logo links home, right slot for nav buttons
- CSS variables: `--bg`, `--surface`, `--card`, `--border`, `--text`, `--text2`, `--blue`, `--green`, `--green2`, `--red`, `--accent`
- Cards, inputs, buttons (`.btn-primary`, `.btn-green`, `.btn-subtle`, `.btn-danger`), alerts, progress bar

---

## Packing List Tracker

Processes KPS packing list PDFs and annotates the job blueprint with colored highlights per shipment.

### How it works
1. Select job → packing lists from `Packing Lists/` folder appear as checkboxes
2. Select one or more (or upload a new one) → click Process
3. Each list is parsed and added cumulatively — previous shipment data is preserved
4. Download or Publish the annotated blueprint

### Color coding  (READ THIS before touching shipment colors)
**Rule:** a color is **assigned to a packing list when it is first processed, stored, and never changed.** The SAME stored color is used in the tracker UI, the editor, and the baked prints. **NEVER red** — red is reserved for the Panel Mapper's panel boxes. Do not hardcode a shipment to a specific color.

- **Persistent map:** `Delivery Tracking/ship_colors.json` = `{shipment_label: color_index}`. `_pl_assign_colors(job, delivery_state)` (app.py) loads it, gives each NEW shipment the lowest UNUSED index (first-seen order), saves, and returns the map. Once assigned, an index never changes.
- **Where it's read (all must agree):**
  - `_run_pl_job` and the update-panels route call `_pl_assign_colors(...)` and pass it as `shipment_colors=` to `generate_tracked_blueprint` / `generate_tracked_blueprint_panel_map` (engine) → baked prints.
  - `packing_list_status` builds `shipments`/`file_colors` from `_pl_assign_colors(...)` → tracker Delivery Status cards.
  - `editor-data` calls `_pl_stats(state, _pl_assign_colors(...))` → `file_colors`; the editor seeds `shipIndex` from it (`shipIdx()` only fills gaps).
  - Engine `generate_*` use the passed `shipment_colors` (fall back to first-seen only if none passed).
- **Three palettes must stay IDENTICAL (same order, length, values, NO red):** `_SHIPMENT_COLORS` (packing_list_engine.py — exact RGB of the hex below), `SHIP_COLORS[]` in `packing_list_editor.html` AND `packing_list_tracker.html`. Order: `#18f23c green, #ffd900 yellow, #00c6ff cyan, #ff8800 orange, #e000e0 magenta, #00e8d8 teal, #b800ff purple`.
- After deploying color changes, re-process each job once to create `ship_colors.json` and regenerate the PDF.
- (Separate convention: "missing / not-in-table" packing-list markers are drawn red `#ff5050` on the PACKING LIST pane only — a not-found warning, not a shipment color, and not on the blueprint with the Panel Mapper boxes.)

### KPS Packing List / Skid Sheet Format

> **Reference images (consult before changing packing-list parsing logic):**
> - `pictures for context/PackingListLayout.png` — canonical full-page layout with
>   color-coded annotation boxes (green = skid block, blue = SKID#, red = PANEL# column,
>   yellow = special-condition skid).
> - `pictures for context/OrderNumberDetail.png` — close-up of SKID #10 showing ORDER#
>   and PANEL# column structure. Key detail: ORDER# 4 spans two rows of panel numbers
>   (18 panels total: 20,21,23,24,25,26 on row 1 and 28,27,546,17,19,16,18,22,14,10,15,
>   12,13,11,532,534,533,535 on rows 2–3). The ORDER# digit appears only once, aligned
>   with the FIRST line of its panel group. Continuation lines have NO ORDER# — the
>   parser must use "nearest preceding" logic (highest ORDER# y ≤ panel y) to assign
>   them correctly. A simple nearest-distance match fails for continuation rows.
>
> **Annotation colors on that image (what each colored box marks):**
> - 🟩 **Green box** = one **skid block** (a quadrant of the 2×2 grid). Each green box is a full skid.
> - 🟦 **Blue box** = the **SKID #** field of a block (the skid's plain-integer number).
> - 🟥 **Red box** = the **PANEL # column** — the ONLY place real panel numbers live. The scanner reads numbers only inside these red regions; everything else (ORDER #, dimensions, the "X PANELS" footer) is ignored.
> - 🟨 **Yellow box** = a PANEL # column on a **special-condition skid** (skid #29 in the example) that has a handwritten "shipping"/"not shipping" scrawl over it. Same column type as red, but flagged for review / treated as not-delivered, so its panels are excluded from the table.

KPS packing lists are PDF documents. Each page has up to **4 skid blocks arranged in a 2×2 grid** (top-left, top-right, bottom-left, bottom-right). A page may have fewer than 4 — determine how many are present by whether a SKID # appears in each quadrant. The layout matches `pictures for context/PackingListLayout.png`.

**Each skid block contains:**
- **SKID #** — plain integer (e.g. `28`). If a quadrant has no SKID #, it's empty/unused.
- **HEIGHT / WIDTH / LENGTH** — panel dimensions, ignore for tracking.
- **ORDER # column** (left) — small numbers ≤99. These are order line numbers, NOT panel numbers. Skip the first number on a line if it is ≤99 and followed by larger numbers.
- **PANEL # column** (right) — comma-separated panel numbers. Format: 1–3 digits, optional `R` suffix meaning **remake** (e.g. `242R`). Range 1–700.
- **X PANELS** footer — total panel count for that skid. Used to validate OCR extraction. If the count doesn't match what was extracted (< 70% match), flag for review.
- **ACCESSORIES** section — ignore; contains clips, tracks, etc., not panels.

**OCR quirks to handle:**
- OCR sometimes reads order number `27` as `2/7` due to a printed table line through the digit. Fix: `re.sub(r'(?<!\d)(\d)/(\d{1,2})(?!\d)', r'\1\2', text)` before parsing.
- Handwriting in a skid block (e.g. "not shipping") corrupts OCR output. Detection: if the `X PANELS` count footer is unreadable (OCR can't parse a number before "PANELS"), the block is flagged and excluded pending manual review.
- Page 1 of each packing list is a cover/shipping summary page — skip it (no SKID # present).

**Panel number rules:**
- Skid numbers: always plain integers.
- Panel numbers: 1–700, optional `R` suffix (remake).
- Leading order number on a line: skip if value ≤99 and at least one following number is >99.
- "Not shipping" handwriting = exclude the **entire skid**, not individual panels.

### Panel location on the blueprint — DXF-coordinate registration
Panel numbers are NOT selectable text in the blueprint PDF (they're baked-in
graphics), so they can't be read directly. The DXF files, however, hold every
panel number with an exact coordinate on the **paper-space PANELS layer**, and
each DXF layout (`3.1`, `2.10`, …) corresponds to a blueprint sheet.

`scan_blueprint_panels()` therefore:
1. OCRs each PDF page at low confidence to get a few panel numbers as **anchors**
   (the DXF whitelist + RANSAC reject misreads, so low confidence is fine).
2. Matches the page to its DXF layout (the layout containing those anchors).
3. Solves the DXF→PDF **affine transform** from the anchors (`_register_page_to_layout`,
   `_ransac_affine`, pure-Python `_affine_fit`/`_solve3` — no numpy dependency).
4. Transforms ALL of that layout's panel coordinates onto the page (box built from
   the 4 transformed text corners, so it survives sheet rotation/flip).
5. Panels are placed **only** through a validated transform. Raw OCR hits are
   never placed when DXF is present — that earlier "fallback" highlighted note
   numbers, dimension strings and grid bubbles that merely look like panels. With
   no DXF at all, it falls back to the classic OCR-only scan.

**Junk-page rejection (`_register_page_to_layout`):** a page only registers if it
has ≥4 matched anchors that form a real 2D fit — ≥4 RANSAC inliers, spanning ≥80pt
in both axes (rejects a collinear column/row of note or grid numbers), with median
residual <5pt and a non-degenerate transform. The DXF→PDF map is a **general
affine** (sheets may be plotted with different x/y scale), so no uniform-scale
assumption is made.

**Built for any future project:** nothing is hardcoded to Modesto. Page↔sheet
matching is by panel-number overlap (not sheet names), and the KPS conventions
(panel range, `PANELS` layer, registration tolerances) are constants at the top of
`packing_list_engine.py` (`PANEL_MIN/MAX`, `PANELS_LAYER`, `REG_*`). Any job whose
DXF puts panel-number text on the PANELS layer with one paper-space layout per
sheet works automatically. Known limit: panels stored only in DXF *model* space
(viewed through viewports) aren't placed yet — Modesto's are in paper space.

Validated on Modesto page 16: OCR-only kept 3 panels; DXF registration placed 30
(8 inliers, 0.65pt residual). Collinear note-number columns and grid-bubble rows
are correctly rejected.

**Cache:** panel positions cache is now `panel_locations_v2.json` so existing jobs
rescan with the new locator. After deploying, **re-process each job's packing lists
once** to rebuild positions.

### Blueprint annotation (packing_list_engine.py)
- Packing lists: rendered at 300dpi, cropped into 4 quadrants (2×2 = 4 skids/page), OCR'd with tesseract `--psm 6`
- Blueprint: rendered at 300dpi with tesseract hOCR for word-level bounding boxes
- **DXF validation**: if a `DXF CAD FILE/` folder exists for the job, all DXF files are scanned for the PANELS layer (paper space blocks and model space). The resulting set of valid panel numbers acts as a whitelist — OCR results not in this set are discarded. This eliminates misreads from dimension callouts, grid labels, etc.
- Panel label filter (without DXF): height 4–9pt, y > 8% from top, x < 82% (excludes title block)
- Panel locations cached to `panel_locations.json` — delete to force rescan after blueprint update or after uploading DXF files
- Output table titled "DELIVERED", top-right corner, auto-sized columns, 2-column layout for large counts, legend strip at bottom
- **Highlights have NO border — keep it that way for every job, now and in the future.** A border sits on the box edge and shows as a ring that hides the printed panel number. Enforced in three spots: (1) `generate_tracked_blueprint` and (2) `generate_tracked_blueprint_panel_map` draw the fill with `page.draw_rect(rect, color=None, fill=fill_c, fill_opacity=0.45, width=0)` — do NOT go back to `add_rect_annot` with a stroke (its border straddles the edge and `set_border(width=0)` does NOT remove it in PDF.js); (3) `packing_list_editor.html` renderPanelBoxes draws delivered panels (panels_only mode) as `.pbox.delivered` (which is `border:0`) with only an inline `background` colour — never `.pbox.pending-add` (1.5px border). Applies automatically to all future packing-list uploads since it's in shared code.

### DXF File Structure (Modesto Courthouse)
- `KeyElevations.dxf` — panels 59–519 stored in paper space blocks `*Paper_Space170` (layout 3.3 → PDF page 17) and `*Paper_Space172` (layout 3.4 → PDF page 18) on the `PANELS` layer as TEXT entities.
- `Sections.dxf` — panels 577–622 in model space on the `PANELS` layer as MTEXT entities.
- `Plans.dxf`, `KeyPlan.dxf` — no panel entities (PDF-imported background geometry only).
- DXF files must be uploaded to the job's `DXF CAD FILE/` folder via `/admin` for validation to activate.
- After uploading DXF files, delete `panel_locations.json` from `Delivery Tracking/` to force a fresh validated scan.

### Publish
- Copies tracked PDF to Blueprints folder as `N - <Job> Delivery Tracked.pdf`
- N = lowest unused integer prefix starting at 1

### Manual corrections store (captured + referenced)
Every hand-fix in the editor — delete a false positive, **renumber** a panel, add a
missing one — is recorded so it isn't lost and can inform future work:

- **Per job:** `Delivery Tracking/corrections.json` = `{deletions:[], renames:{old:new}, additions:{panel:{page,bbox,skid,shipment}}}`. On **re-processing**, after the automatic DXF/OCR scan, `_apply_corrections()` re-applies these so the user's fixes survive (renumbers carry through, deletions stay gone, manual adds come back). A renumber updates `delivery_state`, so the DELIVERED table shows the corrected number.
- **Global:** every edit is also appended to `/var/www/pei-jobs/.panel_corrections.jsonl` (one JSON event per line: type, from/to/panel, page, bbox, job, timestamp) — a growing cross-project record of how humans corrected the automatic panel-finding, available for future tuning/learning across all jobs.

Routes: edits flow through `/api/packing-list/update-panels` (now accepts a
`renames:[{from,to}]` field alongside `add`/`remove`).

### Interactive Editor (the "View" button)
The **View** button on the tracker opens `/packing-list/editor/<job>` — a split-screen
cross-reference tool. Template: `templates/packing_list_editor.html`.

- **Left pane = `panels_only.pdf`** (the Panel Mapper published file, showing only annotated pages). Falls back to `tracked_blueprint.pdf` if no panels_only exists. Rendered with PDF.js. Panel positions are invisible click targets on top. Delivered panel colors are drawn programmatically by JS since panels_only has no baked-in highlights.
- **Right pane = a packing list PDF**; selecting one lazily OCRs it for panel-number positions (`scan_packing_list_positions`, cached as `pl_pos_v2_<file>.json` in Delivery Tracking). Each mark is colored by whether that panel is in the blueprint table.
- **Cross-reference / selecting:** click a panel on either side → it flashes **yellow** on both, and the OTHER pane scrolls to center it (the pane you clicked never moves). Centering is zoom-aware.
- **Action-bar pop-up** (bottom) for ALL panel kinds (delivered, missed, and unlocated): **✎ Change #** and **📍 Place on Blueprint** (label changes to "Move highlight" for already-located panels). Delete whites-out the color immediately and drops it from the table on Save.
- **Place a missing panel:** clicking a missing panel auto-arms placement — a green banner appears on the BLUEPRINT, then a single click sets its highlight there (skid/shipment inherited from the table).
- **Skid number prompt:** whenever a panel number is entered (double-click on blueprint or clicking a blueprint marker), a second prompt also asks for a skid number (optional).
- **＋ Add missing panel** (packing-list header): no prompts → click the packing list → drops a red marker → click it to assign its value & skid.
- **⧉ Duplicate** (pop-up): click the packing list → drops a marker that is **active** (white outline + corner handle): drag the body to move, drag the corner to resize. **Click off** to set it (handles disappear). Click the set marker once to assign value + skid; after that, clicking it opens the normal pop-up.
- **Hide blank pages**, anchored zoom (buttons + Ctrl/pinch on the hovered pane only), **Print** (opens the PDF's print/save dialog), **Share** (SMS/Email/Copy link via a **public** `/p/<token>` link; "New link" rotates and revokes the old one).
- **Save Changes** POSTs pending add/remove/rename to `/update-panels`, which rewrites `delivery_state.json` + `panel_locations_v2.json`, records corrections, and regenerates `tracked_blueprint.pdf`; the viewer reloads it. **Regeneration path:** if a Panel Mapper session exists and `scan_pdf` is on disk, uses `generate_tracked_blueprint_panel_map(scan_pdf, ...)` so panel locations (which are in scan_pdf page space) align correctly. Falls back to `generate_tracked_blueprint(full_blueprint, ...)` when no session exists.

**Color key (what every colored box in the editor means):**

| Color | Where | Meaning |
|-------|-------|---------|
| Shipment color (green, yellow, cyan, orange, magenta, teal, purple, red — `SHIP_COLORS` = `_SHIPMENT_COLORS`) | blueprint + packing list | Panel is **accounted for** — in the blueprint table for that shipment. |
| **Red** (dashed/solid) | packing-list marks, new markers | Panel is **NOT in the blueprint table** (missing / unaccounted), or a freshly-placed marker with no value yet. |
| **Yellow** highlight + flash | both panes | The **currently selected** panel (same look as a matched cross-reference mark). |
| **White outline + corner square** | packing-list marker | The **active** marker being sized/moved (Duplicate / Add missing). Click off to finalize → outline + handle disappear. |
| **White-out box, dashed red border** | blueprint | A highlight you just **deleted** — color erased instantly; made permanent on Save. |
| **Green banner** | top of a pane | "Click here to place" instruction shown while a placement is armed. |

All edits are local (instant overlay/table update) until **Save** — the green Save button shows a pending count and pulses when there are unsaved changes.

### API status response shape
```json
{
  "total_panels": 78,
  "total_skids": ["7","8","9","10"],
  "shipments": [
    {"label": "Shipment #2", "count": 78, "skids": ["7","8","9","10"], "color_index": 0}
  ],
  "file_colors": {"Modesto Shipment #2 6.19.23 Shop": 0},
  "has_output": true
}
```

---

## Blueprint Hyperlinks Tool

Adds clickable hyperlinks to callout circles on KPS blueprint PDFs.

### Callout Engine (`BlueprintLinker/callout_engine.py`)
- v5 — detects bisected circles geometrically, OCRs bottom half only
- Circle size 28–70pt, requires 2+ curve items + bisecting line
- In-memory job store (`_hl_jobs`) — lost on server restart
- Polling: `/blueprint/hyperlinks/status/<job_id>` every 3s

---

## Document Viewer

`/documents` (also `/blueprints` as alias) — browse all jobs and their files organized by category tab.

### Categories
`CATEGORIES = ["Blueprints", "Packing Lists", "Fab Sheets", "Panel Mapper", "Spreadsheets"]`

- All categories show `.pdf` files except **Spreadsheets** which shows `.xlsx`/`.xls`.
- The **Spreadsheets** tab always appears even if no file exists yet (to expose the Pull Data button).
- File list shows filename + "Modified M/D/YY" date from `os.path.getmtime`.

### Spreadsheets tab
Clicking **"Pull Data into Spreadsheet"** calls `POST /api/jobs/<job>/build-spreadsheet`, which:
1. Reads `Delivery Tracking/delivery_state.json` → `{panel: {skid, shipment, order_num}}` (from Packing List Tracker)
2. Reads panel locations from `Panel Map/session.json` → `locs` JSON (preferred) or falls back to `Delivery Tracking/panel_locations_v2.json`
3. Gets packing list file mtimes from `Packing Lists/` folder for "Date Delivered"
4. Extracts drawing numbers (dep. no., e.g. "3.4") from the title block of each page in `scan_pdf` using PyMuPDF text extraction
5. Loads `Spreadsheets/<job>_overrides.json` and applies any manual edits over the generated rows
6. Writes `Spreadsheets/<job>.xlsx` with columns: **Panel Number**, **Sheet Number**, **Order Number**, **Packing List**, **Date Delivered**

**Columns:**
- **Panel Number** — from Panel Mapper `locs` JSON. Duplicate panels get their own row. Sorted numerically then alphabetically.
- **Sheet Number** — dep. no. (e.g. "3.4") extracted from the KPS title block (bottom-right of right 20% of page). Falls back to `page_index + 1`.
- **Order Number** — the ORDER# from the KPS packing list, extracted via hOCR positional matching. ORDER# appears once per row group; continuation panel rows are assigned via "nearest preceding" logic (highest ORDER# y ≤ panel y + 20px).
- **Packing List** — the shipment label (e.g. "Shipment #2"). Rendered as a hyperlink to the packing list PDF in the viewer.
- **Date Delivered** — mtime of the packing list file.

**Manual cell edits (overrides):**
- Cells in the inline viewer are `contenteditable`. Editing any cell shows a **💾 Save Edits** button.
- Saving POSTs `{edits: [{panel, col_header, value}]}` to `/api/jobs/<job>/spreadsheet-edits`.
- Edits are stored in `Spreadsheets/<job>_overrides.json` keyed by `{panel_display_name: {col_header: value}}`.
- On every **Pull Data**, overrides are re-applied after rows are generated — edits survive re-pulls.
- Limitation: duplicate panel display names (same label on multiple sheets) share one override entry.

**Google Sheets integration:**
- **📊 Google Sheets** button: builds TSV from the rendered table, copies to clipboard, opens the linked sheet (or `sheets.new` if none linked). Toast: "Data copied — press Ctrl+V to paste."
- **🔗 Link Sheet** button (to the right): paste a Google Sheets URL to link it to the job. Saved to `Spreadsheets/<job>_sheets_url.json`. Button turns green and shows "🔗 Linked" when active. Clear the URL to unlink.

Clicking an xlsx file shows a popup with three options:
- **View** — renders the spreadsheet inline using SheetJS (no download)
- **Download / Open in Excel** — standard download; Excel opens via OS file association
- **Open in Google Sheets** — copies data to clipboard and opens the linked sheet (or `sheets.new`)

### Dependencies
- `openpyxl` in `requirements.txt` (needs `deploy.bat` / Docker rebuild if not yet installed)
- SheetJS loaded from CDN on first View click: `https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js`

---

## Known Issues / Notes

1. **deploy_quick.bat** falls back to `docker restart` if container is stopped — prevents silent deploy failures.
2. **Packing List Tracker panel scan** is cached — delete `panel_locations.json` in Delivery Tracking to rescan after blueprint changes.
3. **File listing APIs** (`/api/jobs`, `/api/jobs/<job>`) do NOT require login — intentional.
4. **Blueprint Hyperlinks job store** is in-memory — jobs lost on server restart.
5. **Session secret key** hardcoded as `"pei-tools-secret-2024"` — changing it logs everyone out.
6. **TEMPLATES_AUTO_RELOAD = True** — template changes show on refresh without Flask restart.
7. **Jobs folder** excluded from git — always upload files via /admin.

---

## Nginx Config

```nginx
server {
    server_name peitools.com www.peitools.com;
    client_max_body_size 100M;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
    listen 443 ssl; # managed by Certbot
}
```

---

## Restoring from Scratch

```bash
ssh root@<new-ip>
apt update && apt install -y docker.io nginx certbot python3-certbot-nginx tesseract-ocr
git clone https://github.com/caseycarlson11/peitools.git /var/www/panelmapper
mkdir -p /var/www/pei-jobs
cd /var/www/panelmapper
docker build -t panelmapper .
docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper
# Configure nginx, run certbot, re-upload job files via /admin
```

---

## Panel Print Mapper

A tool to verify and hand-correct which panel numbers sit where on a blueprint, producing
clean prints. **Goal:** "dial in" the prints so the Packing List Tracker can read them
later. Files: route logic + helpers in `app.py` (search `_pm_`/`panel_map_`), drawing +
OCR in `packing_list_engine.py`, UIs `templates/panel_print_mapper.html` (picker/selector)
and `templates/panel_map_editor.html` (standalone PDF.js editor).

### Flow
1. **Pick job → blueprint.** The blueprint list pulls from the **Blueprints** folder AND
   the job's **Panel Mapper** folder (prior saved work), each tagged. No Panel Mapper
   folder → only originals.
2. **Page selector** (modal, lifted to `document.body` so it sits above the site header):
   left thumbnail column (resizable divider, scroll-synced to the document), click pages
   to **include** (green), Shift-click for ranges. Then:
   - **Select Pages & Map** → OCR/DXF scan of the chosen pages, draws the red boxes.
   - **Load Prints Without Mapping** → opens the editor with a clean sheet (place panels by hand).
   - **Continue Mapping** (enabled when a saved session exists) → jumps straight into the editor, resuming the last session.
3. **Editor** (`/panel-map/editor/<job>`) — see below.
4. **Save** regenerates two PDFs and copies them into the job's **Panel Mapper** folder
   (stable names, overwritten each save → cumulative progress): `<bp> - Panel Mapper.pdf`
   (full doc, edited pages merged back at their original positions) and
   `<bp> - panels_only.pdf` (just the marked pages).

### Data model
- `panel_locations` is `{ key: {page, bbox, label?, rel?} }`. Normal panel: key = number.
  Duplicate instances stored under unique keys (e.g. `211#2`) with `label` = real number and
  `rel` = `"sheet"` (same panel on multiple sheets) or `"dup"` (different panel, same number).
  This duplicate metadata is saved for the Packing List Tracker to use later.
- `generate_panel_map_blueprint(..., keep_only_panel_pages=False)` draws a red box + the
  number (white chip) using `loc.label or key`. **Chip position:** left edge of chip aligns with right edge of highlight box, bottom of chip aligns with top of highlight box — chip sits above and to the right of the printed panel number. Same geometry applies to `generate_tracked_blueprint_panel_map`.
- Per-job `Panel Map/session.json` = `{bp_name, folder, src_pdf, scan_pdf, locs, pages}` so the
  editor can reload. Output/cache/full paths are keyed by a canonical base name (`_pm_base`
  strips a trailing " - Panel Mapper"); `panels_only` stays its own set so editing it can't
  overwrite the full doc. Human edits also appended to global `.panel_corrections.jsonl`.

### Editor capabilities (`panel_map_editor.html`)
- Crisp zoom: **Ctrl+scroll** re-rasterizes pages at the zoom level, centered on the cursor
  (no page jump); also a Size slider and ✋ **Hand** tool (H) to pan.
- Click a panel → small popup beside it: **Change #**, **Move**, **Resize**, **Delete**,
  and **Find Other** (cycles to other instances of the number, centers + flashes yellow border).
- **Add Missing Panel** (A), **Add Panel Series** (S) with a live ▲▼ number counter under the
  button (hold to fast-scroll, ↑/↓ arrows, click number to type), **Select Multiple Panels**
  (M) = drag a box → OCR (`ocr_region`) lists the numbers found and drops them.
- **Undo** (Ctrl+Z) — snapshots include the series counter, so undo rewinds the next number too.
- **Duplicate handling:** any time a panel number already exists — whether placing via Add Panel,
  Add Series, or **renaming** an existing panel with Change # — the same NON-blocking top-right
  dialog appears (document stays usable) with a dashed-yellow "N?" ghost marker at the placement
  spot. Buttons (hotkeys 1–4): **1** Show other instance (toggles back/forth to the ghost),
  **2** same panel another sheet, **3** different panel same number, **4** cancel. The original
  is never deleted or overwritten.
- **Save Changes** shows a spinner + elapsed timer and a change summary toast.

### Gotchas
- Editor is a standalone template (own `<head>`, not `base.html`). PDF.js 3.11.174 from cdnjs.
- "Panel Mapper" added to `CATEGORIES` in app.py so the Blueprint Viewer lists it; files served
  via `/files/<job>/Panel Mapper/<file>`.
- Map page indices line up with the source because the full-merge merges the marked pages back
  into the *source document the user loaded* (original, or a prior Panel Mapper full doc).
