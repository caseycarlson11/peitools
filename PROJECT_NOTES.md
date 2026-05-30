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
    ├── index.html            # Landing page (5 buttons)
    ├── login.html            # Login page
    ├── blueprints.html       # Blueprint viewer
    ├── field_compass.html    # Field Compass app
    ├── admin.html            # Admin upload page
    ├── share_view.html       # Public shared job view
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
| `/field-compass` | Field compass with PDF viewer | Login required |
| `/admin` | Upload/manage files (password: PEI2024) | Login required |
| `/share/<token>` | Shared job folder (public link) | Public |
| `/api/jobs` | List all jobs | Public |
| `/api/jobs/<job>` | List files for a job | Public |
| `/files/<path>` | Serve a file | Login required |

---

## Authentication

- **Site login:** Email + password (see user list below)
- **Admin panel password:** `PEI2024`
- **Session:** Flask cookie-based, secret key = `"pei-tools-secret-2024"`

### User Accounts (in app.py `_USERS_RAW`)
All emails are `@pacificerectors.com`. Passwords follow the pattern `Lastname4460`.

| Email prefix | Password |
|---|---|
| dennisa | Andersen4460 |
| armandor | Rivera4460 |
| arturov | Vargas4460 |
| caseyc | Carlson4460 |
| davida | Arias4460 |
| elim | Martinez4460 |
| erica | Andersen4460 |
| glenw | Wheeler4460 |
| gustavoh | Hernandez4460 |
| javierm | Arevalo4460 |
| juanc | Camarena4460 |
| luism | Marure4460 |
| robinp | Pederson4460 |
| stevens | Sousa4460 |
| thomasr | Rowley4460 |
| tommyp | Pearman4460 |
| miket | Thomas4460 |
| jeffy | Young4460 |
| jasonw | Walters4460 |
| dalynb | Bush4460 |
| thomasm | McClelland4460 |
| fritzb | Bowen4460 |
| erics | Sidener4460 |
| debid | Dunkin4460 |
| kellyl | Lee4460 |
| kishag | Gann4460 |
| jennab | Bearden4460 |
| meganf | Friery4460 |

---

## Jobs & File Storage

Jobs are stored on the server at `/var/www/pei-jobs/` (Docker volume). Structure:
```
/var/www/pei-jobs/
  <Job Name>/
    Blueprints/       ← PDF blueprints
    Packing Lists/    ← KPS packing list PDFs
    Fab Sheets/       ← Fab sheet PDFs
  .shares.json        ← Active share links
```

### Current jobs on server
- Equinix
- Modesto Courthouse
- SFPUC Bldg 600
- SFPUC Bldg 615
- UCSF Parnassus
- Vantage Data Center NV11
- Workday

**Files persist across code deploys** because `/var/www/pei-jobs` is a Docker volume. They are NOT in git and are NOT in the local project folder. To back them up: `scp -r root@93.188.160.121:/var/www/pei-jobs/ ./backup-jobs/`

---

## Share Links

Job-level share links are stored in `/var/www/pei-jobs/.shares.json`. One active link per job. Links are generated from the Blueprint Viewer → select a job → click "🔗 Share Job".

Shared links follow the format: `https://peitools.com/share/<token>`

---

## Known Issues / Notes

1. **File listing APIs** (`/api/jobs`, `/api/jobs/<job>`, `/api/jobs/<job>/all-files`) do NOT require login — this was intentional to avoid session/cookie issues that caused files to not display. The actual file content (`/files/`) IS login-protected.

2. **Deploy wipes container** but the volume persists. Never use `docker volume rm` on the server.

3. **The `Jobs/` folder** in the local project is excluded from git and deploy (via robocopy `/XD Jobs`). Always use the admin page to upload files.

4. **Session secret key** is hardcoded as `"pei-tools-secret-2024"` — changing this logs everyone out.

5. **Admin password** (`PEI2024`) is separate from user login passwords.

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
