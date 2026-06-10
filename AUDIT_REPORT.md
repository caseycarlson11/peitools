# PEItools.com Security & Code Audit — June 9, 2026

Scope: app.py (3,084 lines), packing_list_engine.py (1,539 lines), BlueprintLinker, 28 templates, Dockerfile, deploy scripts, the public GitHub repo, and live checks against peitools.com. Every Critical finding below was verified, not assumed.

---

## CRITICAL — fix this week

### C1. Every employee password is publicly readable on GitHub right now
**Verified:** I fetched `raw.githubusercontent.com/caseycarlson11/peitools/main/app.py` with no login and got all 29 employee email/password pairs in plain text (lines 21–51).

Worse, the passwords follow the pattern `LastName4460`, so even after removing the file, anyone who saw it once can guess every account forever — including new employees.

**Real-world consequence:** anyone on the internet can log into peitools.com as any employee and view, upload, or delete job files for Equinix, SFPUC, UCSF, Workday, etc.

**Fix, in order:**
1. **Today:** make the repo private — github.com/caseycarlson11/peitools → Settings → Danger Zone → Change visibility → Private. Takes 1 minute, stops the bleeding.
2. Rotate ALL passwords to random ones (no pattern). I can generate them.
3. Move credentials out of app.py into a file on the server that is never in git (e.g. `users.json` next to the jobs volume), loaded at startup.
4. Because git history still contains the old file, delete the GitHub repo entirely and re-create it fresh after the secrets are out (simpler and more reliable than history-scrubbing tools).

### C2. The Flask `secret_key` is public — anyone can forge a login cookie, including admin
`app.secret_key = "pei-tools-secret-2024"` (line 10) is in the public repo. This key is what makes session cookies trustworthy. With it, an attacker doesn't need any password: they can mint a cookie that says `user = anyone` and `admin = True`, giving full admin (create/delete jobs, upload files, delete files).

**Fix:** generate a long random key, store it in an environment variable on the VPS (set in the Docker run command), and read it with `os.environ`. Rotating it also logs every existing session out — do it at the same time as the password rotation.

### C3. Admin password `PEI2024` is public
Line 18, same exposure. Fix together with C1/C2 — random value, loaded from the server, not from code.

### C4. Four API routes need no login and leak your client list + every filename
**Verified live:** `https://peitools.com/api/jobs` returns your full job/client list to anyone, and `/api/jobs/Workday/all-files` returns every blueprint, packing list, and panel-map filename. Affected routes (no `@login_required`):

- `/api/jobs` (line 215)
- `/api/jobs/<job>` (line 223)
- `/api/jobs/<job>/all-files` (line 260)
- `/api/jobs/<job>/dxf-files` (line 189)

The files themselves are behind login, but combined with C2 the file contents are effectively public too.

**Fix:** add `@login_required` to all four. One caution: confirm none of the public share pages (`/share/<token>`, `/compass/<token>`, `/pl/<token>`) call these APIs from the browser — from my reading they don't (they're server-rendered), but we should click through each public link type after the change.

---

## HIGH — fix soon

### H1. Crash bug: missing `import logging` in app.py
Line ~2233 (`packing_list_unlink`) calls `logging.warning(...)` but app.py never imports `logging`. If blueprint regeneration fails during an unlink, the user gets a confusing 500 error instead of the intended graceful handling. One-line fix.

### H2. Login has no rate limiting
Combined with the guessable password pattern, a script could try `Smith4460`, `Jones4460`... unhindered. After rotating to random passwords this is less urgent, but adding a simple per-IP attempt limit (e.g. Flask-Limiter, or a small in-app counter) is cheap insurance.

### H3. No upload size limit
`MAX_CONTENT_LENGTH` is unset, so any logged-in user (or cookie-forger) can upload unlimited-size files until the VPS disk fills and the site dies. Fix: one line, e.g. 500 MB cap.

### H4. Open redirect on the login page
`/login?next=https://evil.com` will bounce a successful login to any external site — a phishing aid. Fix: only follow `next` if it starts with `/`.

---

## MEDIUM — reliability bugs

### M1. Temp-file collisions can mix up panel data between jobs
The OCR engine writes temp images keyed only by page number: `/tmp/plq_{page}_{col}.png` (line 217) and `/tmp/bpscan_{page}.png` (line 1048). If two people process packing lists or run the panel mapper on **different jobs at the same time**, the files collide and panels from one job can be read into the other. Fix: include a unique ID (uuid) in the temp filenames, and delete `bpscan`/`bphocr` files after use (they currently accumulate until the container restarts).

### M2. Blueprint Hyperlinks sessions never get cleaned up
Every hyperlink/editor session leaves a PDF in `/tmp` and an entry in memory forever (until container restart). On a long-running server this slowly eats disk and RAM. Fix: expire jobs older than a few hours.

### M3. State files aren't written crash-safely
`delivery_state.json`, `ship_colors.json`, etc. are written with a plain overwrite. If the process dies mid-write (deploy restart, crash), the file is left half-written and the job's tracking data is corrupted. Fix: write to a temp file then rename (atomic on Linux) — a small helper used everywhere.

### M4. Some routes skip the per-job lock
`_run_pl_job` correctly uses a per-job lock for delivery_state, but `manual-panels`, `unlink`, and `update-panels` read-modify-write the same files without it. Two simultaneous edits can silently drop one person's changes. Fix: wrap those in the same `_pl_get_file_lock(job_name)`.

### M5. Gunicorn runs one synchronous worker
The Dockerfile starts gunicorn with defaults: 1 worker, 1 thread. Any slow request (big PDF download on a slow connection) makes the whole site unresponsive for everyone until it finishes. **Important:** do NOT fix this with `--workers N` — your job-progress tracking (`_pl_jobs`, `_hl_jobs`) lives in process memory and multiple workers would each have their own copy (progress bars would randomly say "not found"). The right fix is `--threads 8` (one process, shared memory).

### M6. `safe_join` has a theoretical edge case
It checks `path.startswith(JOBS_DIR)`, so a folder named `jobsXYZ` next to `jobs` would pass. No such folder exists, so it's not exploitable today. Fix: compare against `JOBS_DIR + os.sep`.

---

## LOW — cleanup & housekeeping

### L1. ~55 MB of junk is being committed and deployed
`deploy_quick.bat` copies the whole folder to git, so the public repo (and every clone) includes: `tesseract-ocr-w64-setup...exe` (21 MB), four `Modesto_Linked*.pdf` test files (44 MB), `preview.html`, `SheetEditor.html` + `SheetEditor_v2.html` (superseded by templates/sheet_editor.html), `1447-7274_edit2-1.jpg`, `pictures for context/`, `__pycache__`, an empty `Tools/` folder, and `BlueprintLinker/callout_engine_v1_backup.py` + `callouts_v2.json`. Fix: delete or move out of the project folder, and extend `.gitignore`. (This happens naturally when the repo is re-created for C1.)

### L2. requirements.txt has no version pins
`flask`, `pymupdf`, etc. are unpinned — a full rebuild (`deploy.bat`) could pull a new major version and break the site with no code change. Fix: pin versions (`pip freeze` inside the container gives the current known-good set).

### L3. Nginx checklist (on the VPS — I can't see it from here)
Verify: HTTP→HTTPS redirect; HSTS header; `client_max_body_size` set (pairs with H3); certificate auto-renewal working. I can write the exact config lines if you paste your current nginx config.

### L4. No backups of job data
Everything lives in the Docker volume `/var/www/pei-jobs`. A disk failure or a bad `delete-job` click loses it all. Recommend a nightly tar of that volume to a second location (even a `scp` to your office PC). Happy to set this up.

---

## What checked out fine

- Path traversal protection (`safe_join`) is used consistently on every file route.
- Public link tokens use `secrets.token_urlsafe(16)` — cryptographically strong, properly rotatable.
- Passwords are at least hashed in memory (but that's moot while the plaintext is in the repo).
- Jinja auto-escaping intact everywhere (no `|safe` misuse) — no template XSS found.
- The `SHIP_COLORS` palettes are identical across all 5 templates and the engine, no red — the rule in CLAUDE.md is being honored.
- "No border" delivered-panel rule verified in the engine.
- Admin delete-file is restricted to known categories; filenames are sanitized on upload.

---

## Suggested fix order

1. **Now (you, 1 min):** make the GitHub repo private.
2. **Batch 1 (me, ~1 session):** secrets out of code + new secret key + random passwords + `@login_required` on the four APIs + `import logging` + upload cap + `next` redirect fix. Deploy, everyone logs in once with new passwords.
3. **You:** delete and re-create the GitHub repo (clean history), after Batch 1 is committed.
4. **Batch 2:** temp-file collisions, atomic writes, per-job locks, hyperlink cleanup, `--threads`.
5. **Batch 3:** repo cleanup, version pins, nginx checklist, backups.
