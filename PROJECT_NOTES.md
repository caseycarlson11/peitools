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

### Key server commands
```bash
# View logs
docker logs panelmapper --tail 30

# Restart container (preserves volume)
docker stop panelmapper; docker rm panelmapper
docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper

# Force rebuild (no cache)
cd /var/www/panelmapper && git pull
docker build --no-cache -t panelmapper .
docker stop panelmapper; docker rm panelmapper
docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper

# Check uploaded files
find /var/www/pei-jobs -name "*.pdf" | head -20
ls /var/www/pei-jobs/
```

---

## Local Setup

| Item | Value |
|------|-------|
| Project folder | `C:\Users\ROG\Documents\Pacific Erectors\PEItools.com` |
| Git working copy | `C:\temp\peitools` (no spaces — required for git) |
| Deploy script | `C:\temp\peitools\deploy.bat` |

### Deploy command (run from CMD)
```
C:\temp\peitools\deploy.bat
```
This does: robocopy → git push → server git pull → docker rebuild.

**Important:** The `Jobs/` folder is excluded from robocopy/git. Uploaded files live only on the server volume.

---

## File Structure
```
PEItools.com/
├── app.py                    # Flask routes (main backend)
├── requirements.txt          # flask, gunicorn
├── Dockerfile
├── deploy.bat                # Deploy script (CMD)
├── deploy.ps1                # Deploy script (PowerShell)
├── static/
│   ├── bg.jpg                # Background image
│   ├── logo.jpg              # PEI logo
│   ├── favicon.png
│   └── favicon.ico
└── templates/
    ├── index.html            # Landing page
    ├── login.html            # Login page
    ├── blueprints.html       # Blueprint viewer
    ├── field_compass.html    # Field Compass app (iOS + Android)
    ├── compass_share.html    # Public shared Field Compass view
    ├── admin.html            # Admin upload page
    ├── share_view.html       # Public shared job folder view
    ├── sheet_editor.html     # Fab Sheet Editor
    └── panel_sheet_mapper.html  # Panel Sheet Extractor
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
| `/share/<token>` | Shared job folder — all file types | Public |
| `/compass/<token>` | Shared Field Compass — blueprints only | Public |
| `/api/jobs` | List all jobs | Public |
| `/api/jobs/<job>` | List files for a job (by category) | Public |
| `/api/jobs/<job>/all-files` | List all files for a job | Public |
| `/api/jobs/<job>/dxf-files` | List DXF files for a job | Public |
| `/api/share` | Create/manage job folder share links | Login required |
| `/api/compass-share` | Create/manage compass share links | Login required |
| `/files/<path>` | Serve a job file | Login required |
| `/cad-files/<path>` | Serve a DXF/CAD file | Login required |

---

## Authentication

- **Site login:** Email + password (see user list below)
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

Jobs are stored on the server at `/var/www/pei-jobs/` (Docker volume). Each new job gets these folders automatically:
```
/var/www/pei-jobs/
  <Job Name>/
    Blueprints/       ← PDF blueprints
    Packing Lists/    ← KPS packing list PDFs
    Fab Sheets/       ← Fab sheet PDFs
    DXF CAD FILE/     ← DXF and DWG CAD files
  .shares.json              ← Active job folder share links
  .compass_shares.json      ← Active Field Compass share links
```

### Current jobs on server
- Equinix
- Modesto Courthouse
- SFPUC Bldg 600
- SFPUC Bldg 615
- UCSF Parnassus
- Vantage Data Center NV11
- Workday

**Files persist across code deploys** because `/var/www/pei-jobs` is a Docker volume. They are NOT in git. To back up: `scp -r root@93.188.160.121:/var/www/pei-jobs/ ./backup-jobs/`

---

## Share Links

Two separate share systems, each with one active link per job:

**Job Folder Share** — stored in `.shares.json`
Generated from Blueprint Viewer → select job → 🔗 Share Job
Format: `https://peitools.com/share/<token>`
Shows all Blueprints, Packing Lists, and Fab Sheets. No login required.

**Field Compass Share** — stored in `.compass_shares.json`
Generated from Field Compass → select job → 🔗 Share Field Compass
Format: `https://peitools.com/compass/<token>`
Opens the full Field Compass app with that job's blueprints. No login required.

---

## Tool Notes

### Field Compass
- Works on iOS (Safari) and Android (Chrome)
- iOS requires motion permission prompt — granted on first double-tap
- Uses `deviceorientation` event for rotation tracking (relative delta from lock point)
- Orientation events throttled via `requestAnimationFrame` to prevent Android Chrome crash
- Canvas freed on exit to prevent memory leak
- Re-renders at higher resolution after pinch zoom settles (600ms debounce)
- Android: max canvas 3MP / 2048px. iOS: max canvas 6MP / 4096px

### Fab Sheet Editor
- Default label size: 22px, max 40px
- Supports save/load session (.kpssession files)
- Can load Fab Sheets directly from server job folders
- Export: marked pages only or all pages

### Panel Sheet Mapper (Sheet Extractor)
- Reads DXF files, looks for layer named exactly `PANELS`
- Can load DXF files directly from `DXF CAD FILE/` folder on server
- Export to CSV (Excel-compatible) or copy to clipboard for Google Sheets

### Blueprint Viewer
- Sidebar shows "Active Jobs"
- Per-job share links (folder view, no login required)
- Full-screen PDF viewer with zoom

### Admin Page
- Password: `PEI2024` (separate from user login)
- Upload categories: Blueprints, Packing Lists, Fab Sheets, DXF CAD FILE
- Accepts: PDF, images (.png/.jpg etc.), .dxf, .dwg

---

## Blueprint Callout Linker (PDF Tool)

A standalone Python tool that reads a KPS blueprint PDF, detects all section detail callout circles (the `N/Dx` symbols — circle bisected by a horizontal line), and produces a new PDF with clickable orange-highlighted links that jump to the correct detail drawing.

### How it works
1. Uses PyMuPDF `get_drawings()` to detect callout circles by shape (circular arc + bisecting line)
2. Renders each circle at high resolution and OCRs the top half (detail number 1–9) and bottom half (D-page D1–D23)
3. Handles `-90°` rotated callouts (vertical bisecting line) by rotating the crop before OCR
4. Optionally applies a manual correction list for any circles OCR can't read reliably
5. Saves a new PDF with semi-transparent orange rectangles + embedded GoTo links

### Key files (stored in Cowork session outputs folder)
| File | Purpose |
|------|---------|
| `callout_engine.py` | Reusable detection/OCR engine (works on any KPS blueprint) |
| `run_detection.py` | Batch processing script — runs engine page-by-page, saves to JSON |
| `build_final.py` | Builds the output PDF from JSON + applies manual corrections |
| `callouts_v2.json` | Cached OCR results for Modesto Courthouse (v2) |
| `Modesto_Linked3.pdf` | Final output — 267 clickable callout links, orange highlights |

### Workflow for a new blueprint
1. Copy `callout_engine.py`, `run_detection.py`, `build_final.py` to the session outputs folder
2. Update `PDF` path in both scripts to point to the new blueprint PDF
3. Run `run_detection.py` in batches (e.g. pages 0–5, 5–10, etc.) — saves to `callouts_v2.json`
4. Review results — note any missed callouts per page
5. Update `CORRECTIONS` dict in `build_final.py` with missed callouts
6. Run `build_final.py` to produce the final linked PDF

### Known OCR challenges
- Thin-stroke CAD fonts — OCR requires morphological dilation + 15× effective scale
- `D1` can appear as `D11` (top digit bleeds through midline) — fixed by blanking 10px at midline
- `D10–D23` parsed correctly by trying 2-digit match first, then 1-digit
- Digit `2` sometimes misread as `4` or `9` — two OCR config passes help
- Callouts rotated −90° detected via vertical bisecting line instead of horizontal
- Circle size range: 28–70pt. Pages with very large/small symbols may need range adjustment
- PDF must be rendered at SCALE=3 (base) × 5 (upscale) = 15× for reliable OCR

### Manual correction list (Modesto Courthouse v2 — 267 total links)
Corrections applied to pages: 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 3.5, 3.6, 3.7, 3.9, 3.10, 3.12, 3.13, 3.14, 3.15, 3.16, 3.17, 4.1, 4.2 (44 corrections added on top of 223 automated)

---

## Known Issues / Notes

1. **File listing APIs** (`/api/jobs`, `/api/jobs/<job>`, `/api/jobs/<job>/all-files`, `/api/jobs/<job>/dxf-files`) do NOT require login — intentional to avoid session issues. File content endpoints (`/files/`, `/cad-files/`) ARE login-protected.

2. **Deploy wipes container** but the volume persists. Never use `docker volume rm` on the server.

3. **The `Jobs/` folder** in the local project is excluded from git and deploy (via robocopy `/XD Jobs`). Always use the admin page to upload files.

4. **Session secret key** is hardcoded as `"pei-tools-secret-2024"` — changing this logs everyone out.

5. **Admin password** (`PEI2024`) is separate from user login passwords.

6. **Existing jobs** created before the `DXF CAD FILE` folder was added will not have that subfolder. Create it manually via admin or SSH if needed.

---

## Nginx Config

Two configs in `/etc/nginx/sites-enabled/`:
- `panelmapper` — handles `peitools.com` on HTTPS (443), proxies to `127.0.0.1:5000`
- `myapp` — handles direct IP access on port 80, proxies to `127.0.0.1:5000`

SSL certificates managed by Certbot for `peitools.com`.

---

## Restoring from Scratch

If the server is wiped:
```bash
# 1. SSH into new server
ssh root@<new-ip>

# 2. Install Docker and Nginx
apt update && apt install -y docker.io nginx certbot python3-certbot-nginx

# 3. Clone repo
git clone https://github.com/caseycarlson11/peitools.git /var/www/panelmapper

# 4. Create jobs folder
mkdir -p /var/www/pei-jobs

# 5. Build and run
cd /var/www/panelmapper
docker build -t panelmapper .
docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper

# 6. Configure nginx and SSL
# (copy panelmapper nginx config, run certbot)

# 7. Re-upload all job files via /admin
```
