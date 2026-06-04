# PEItools.com — Project Notes

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

**`deploy.bat`** — only when requirements.txt or Dockerfile changes (full rebuild ~5 min)

---

## File Structure
```
PEItools.com/
├── app.py                         # Flask routes (main backend)
├── packing_list_engine.py         # Packing List Tracker engine (OCR + PDF annotation)
├── requirements.txt               # flask, gunicorn, pymupdf, pytesseract, pillow
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
| `/blueprints` | Blueprint viewer (jobs + files) | Login required |
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
| `/share/<token>` | Shared job folder | Public |
| `/compass/<token>` | Shared Field Compass | Public |
| `/api/jobs` | List all jobs | Public |
| `/api/jobs/<job>` | List files for a job (by category) | Public |
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
      panel_locations.json        Cached blueprint OCR panel positions (delete to force rescan)
      tracked_blueprint.pdf       Current annotated output PDF
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

### Color coding
- Each shipment gets a distinct color: green, yellow, cyan, orange, magenta, teal, purple, red
- Colors used in: blueprint highlights, table row swatches, UI shipment stat cards, file list badges
- Palette defined in `packing_list_engine.py → _SHIPMENT_COLORS` and `packing_list_tracker.html → SHIP_COLORS[]`

### Blueprint annotation (packing_list_engine.py)
- Packing lists: rendered at 300dpi, cropped into 4 quadrants (2×2 = 4 skids/page), OCR'd with tesseract `--psm 6`
- Blueprint: rendered at 300dpi with tesseract hOCR for word-level bounding boxes
- Panel label filter: height 4–9pt, y > 8% from top, x < 82% (excludes title block)
- Isolated small numbers (1–9) filtered if no panel neighbors within 200pt
- Panel locations cached to `panel_locations.json` — delete to force rescan after blueprint update
- Output table titled "DELIVERED", top-right corner, auto-sized columns, 2-column layout for large counts, legend strip at bottom

### Publish
- Copies tracked PDF to Blueprints folder as `N - <Job> Delivery Tracked.pdf`
- N = lowest unused integer prefix starting at 1

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
