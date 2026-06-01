from flask import Flask, send_from_directory, send_file, render_template, request, jsonify, session, abort, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os, re, sys, io, tempfile

# Make BlueprintLinker importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'BlueprintLinker'))

app = Flask(__name__)
app.secret_key = "pei-tools-secret-2024"

# ── Jobs folder (persisted via Docker volume) ────────────────
JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

ADMIN_PASSWORD = "PEI2024"

# ── User accounts ─────────────────────────────────────────────
_USERS_RAW = {
    "dennisa@pacificerectors.com":  "Andersen4460",
    "armandor@pacificerectors.com": "Rivera4460",
    "arturov@pacificerectors.com":  "Vargas4460",
    "caseyc@pacificerectors.com":   "Carlson4460",
    "davida@pacificerectors.com":   "Arias4460",
    "elim@pacificerectors.com":     "Martinez4460",
    "erica@pacificerectors.com":    "Andersen4460",
    "glenw@pacificerectors.com":    "Wheeler4460",
    "gustavoh@pacificerectors.com": "Hernandez4460",
    "javierm@pacificerectors.com":  "Arevalo4460",
    "juanc@pacificerectors.com":    "Camarena4460",
    "luism@pacificerectors.com":    "Marure4460",
    "robinp@pacificerectors.com":   "Pederson4460",
    "stevens@pacificerectors.com":  "Sousa4460",
    "thomasr@pacificerectors.com":  "Rowley4460",
    "tommyp@pacificerectors.com":   "Pearman4460",
    "miket@pacificerectors.com":    "Thomas4460",
    "jeffy@pacificerectors.com":    "Young4460",
    "jasonw@pacificerectors.com":   "Walters4460",
    "dalynb@pacificerectors.com":   "Bush4460",
    "thomasm@pacificerectors.com":  "McClelland4460",
    "fritzb@pacificerectors.com":   "Bowen4460",
    "erics@pacificerectors.com":    "Sidener4460",
    "debid@pacificerectors.com":    "Dunkin4460",
    "kellyl@pacificerectors.com":   "Lee4460",
    "kishag@pacificerectors.com":   "Gann4460",
    "jennab@pacificerectors.com":   "Bearden4460",
    "meganf@pacificerectors.com":   "Friery4460",
    "nicholaskoron@gmail.com":      "REDFredf",
}
USERS = {email: generate_password_hash(pwd) for email, pwd in _USERS_RAW.items()}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            # API routes get a JSON 401; page routes get a redirect to login
            if request.path.startswith("/api/") or request.path.startswith("/files/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

# ── Login / Logout ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        hashed = USERS.get(email)
        if hashed and check_password_hash(hashed, password):
            session["user"] = email
            return redirect(request.args.get("next") or url_for("index"))
        error = "Incorrect email or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

CATEGORIES = ["Blueprints", "Packing Lists", "Fab Sheets"]
CAD_FOLDER = "DXF CAD FILE"
ALL_FOLDERS = CATEGORIES + [CAD_FOLDER]
IMAGE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}

def safe_join(*parts):
    """Resolve a path and ensure it stays inside JOBS_DIR."""
    path = os.path.realpath(os.path.join(JOBS_DIR, *parts))
    if not path.startswith(os.path.realpath(JOBS_DIR)):
        abort(403)
    return path

# ── Landing page ─────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html")

# ── Existing tools ───────────────────────────────────────────
@app.route("/sheet_editor")
@login_required
def sheet_editor():
    return render_template("sheet_editor.html")

@app.route("/sheet_extractor", methods=["GET", "POST"])
@login_required
def sheet_extractor():
    if request.method == "GET":
        return render_template("panel_sheet_mapper.html")

    files = request.files.getlist("files")
    if not files:
        return "No files uploaded", 400

    mapping = {}

    for f in files:
        fname = f.filename
        lines = [l.decode("utf-8", errors="ignore").strip() for l in f.read().splitlines()]

        layout_handles = []
        for i in range(1, len(lines)-1):
            if lines[i] == "AcDbLayout" and lines[i-1] == "100":
                name = handle = None
                j = i + 1
                while j < min(i+160, len(lines)-1):
                    c, v = lines[j], lines[j+1] if j+1 < len(lines) else ""
                    if c == "1" and name is None: name = v
                    if c == "330": handle = v
                    if c == "0" and j > i+2: break
                    j += 2
                if name and name != "Model":
                    layout_handles.append((name, handle))

        owner_to_block = {}
        for i in range(0, len(lines)-3, 2):
            if lines[i] == "0" and lines[i+1] == "BLOCK":
                bname = owner = None
                for j in range(i+2, min(i+30, len(lines)-1), 2):
                    if lines[j] == "2": bname = lines[j+1]
                    if lines[j] == "330": owner = lines[j+1]
                    if lines[j] == "0" and j > i+2: break
                if bname and owner:
                    owner_to_block[owner] = bname

        layout_to_block = {name: owner_to_block.get(handle, "") for name, handle in layout_handles}
        block_to_layout = {v: k for k, v in layout_to_block.items() if v}

        current_block = None
        for i in range(0, len(lines)-3, 2):
            if lines[i] == "0" and lines[i+1] == "BLOCK":
                for j in range(i+2, min(i+20, len(lines)-1), 2):
                    if lines[j] == "2": current_block = lines[j+1]; break
            elif lines[i] == "0" and lines[i+1] == "ENDBLK":
                current_block = None
            elif lines[i] == "0" and lines[i+1] in ("TEXT", "MTEXT"):
                layer = text = None
                for j in range(i+2, min(i+40, len(lines)-1), 2):
                    c, v = lines[j], lines[j+1] if j+1 < len(lines) else ""
                    if c == "8": layer = v
                    if c == "1": text = v
                    if c == "0" and j > i+2: break
                if layer and "PANEL" in layer.upper() and text and text.strip().isdigit():
                    n = int(text.strip())
                    sheet = block_to_layout.get(current_block)
                    if sheet:
                        if n not in mapping:
                            mapping[n] = {"sheets": [], "file": fname}
                        if sheet not in mapping[n]["sheets"]:
                            mapping[n]["sheets"].append(sheet)

    def sort_sheets(sheets):
        def key(s):
            try: return [float(p) for p in s.split(".")]
            except: return [999]
        return sorted(sheets, key=key)

    for p in mapping:
        mapping[p]["sheets"] = sort_sheets(mapping[p]["sheets"])

    str_mapping = {str(k): v for k, v in sorted(mapping.items())}
    return jsonify({"mapping": str_mapping, "job_name": "", "count": len(str_mapping)})

# ── CAD file listing ─────────────────────────────────────────
@app.route("/api/jobs/<path:job>/dxf-files")
def api_dxf_files(job):
    cad_path = safe_join(job, CAD_FOLDER)
    if not os.path.isdir(cad_path):
        return jsonify([])
    files = sorted([f for f in os.listdir(cad_path) if f.lower().endswith(".dxf")])
    return jsonify(files)

@app.route("/cad-files/<path:filepath>")
@login_required
def serve_cad_file(filepath):
    full = safe_join(filepath)
    return send_from_directory(os.path.dirname(full), os.path.basename(full))

# ── Blueprint viewer (public) ────────────────────────────────
@app.route("/blueprints")
@login_required
def blueprints():
    return render_template("blueprints.html")

@app.route("/field-compass")
@login_required
def field_compass():
    return render_template("field_compass.html")

@app.route("/api/jobs")
def api_jobs():
    if not os.path.isdir(JOBS_DIR):
        return jsonify([])
    jobs = sorted([d for d in os.listdir(JOBS_DIR)
                   if os.path.isdir(os.path.join(JOBS_DIR, d))])
    return jsonify(jobs)

@app.route("/api/jobs/<path:job>")
def api_job_files(job):
    job_path = safe_join(job)
    if not os.path.isdir(job_path):
        return jsonify({"error": "Job not found"}), 404
    result = {}
    for cat in CATEGORIES:
        cat_path = os.path.join(job_path, cat)
        if os.path.isdir(cat_path):
            files = sorted([f for f in os.listdir(cat_path)
                            if f.lower().endswith(".pdf")])
            if files:
                result[cat] = files
    return jsonify(result)

@app.route("/api/jobs/<path:job>/all-files")
def api_job_all_files(job):
    """Return all viewable files (PDF + images) across all categories."""
    job_path = safe_join(job)
    if not os.path.isdir(job_path):
        return jsonify({"error": "Job not found"}), 404
    files = []
    for cat in CATEGORIES:
        cat_path = os.path.join(job_path, cat)
        if os.path.isdir(cat_path):
            for f in sorted(os.listdir(cat_path)):
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    files.append({"name": f, "category": cat,
                                  "url": f"/files/{job}/{cat}/{f}",
                                  "type": "pdf" if ext == ".pdf" else "image"})
    return jsonify(files)

@app.route("/admin", methods=["GET"])
@login_required
def admin():
    return render_template("admin.html")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if data and data.get("password") == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Wrong password"}), 401

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"ok": True})

@app.route("/admin/create-job", methods=["POST"])
@login_required
def admin_create_job():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    job_name = (data or {}).get("name", "").strip()
    if not job_name or re.search(r'[\\/:*?"<>|]', job_name):
        return jsonify({"error": "Invalid job name"}), 400
    job_path = safe_join(job_name)
    for cat in ALL_FOLDERS:
        os.makedirs(os.path.join(job_path, cat), exist_ok=True)
    return jsonify({"ok": True})

@app.route("/admin/upload", methods=["POST"])
@login_required
def admin_upload():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    job      = request.form.get("job", "").strip()
    category = request.form.get("category", "").strip()
    if not job or category not in ALL_FOLDERS:
        return jsonify({"error": "Invalid job or category"}), 400
    cat_path = safe_join(job, category)
    os.makedirs(cat_path, exist_ok=True)
    ALLOWED_EXTS = IMAGE_EXTS | {".dxf", ".dwg"}
    uploaded = []
    for f in request.files.getlist("files"):
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in ALLOWED_EXTS:
            fname = re.sub(r'[\\/:*?"<>|]', "_", f.filename)
            f.save(os.path.join(cat_path, fname))
            uploaded.append(fname)
    return jsonify({"ok": True, "uploaded": uploaded})

@app.route("/admin/delete-file", methods=["POST"])
@login_required
def admin_delete_file():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data     = request.get_json()
    job      = (data or {}).get("job", "").strip()
    category = (data or {}).get("category", "").strip()
    filename = (data or {}).get("filename", "").strip()
    if not job or category not in CATEGORIES or not filename:
        return jsonify({"error": "Invalid parameters"}), 400
    filepath = safe_join(job, category, filename)
    if os.path.isfile(filepath):
        os.remove(filepath)
    return jsonify({"ok": True})

@app.route("/admin/delete-job", methods=["POST"])
@login_required
def admin_delete_job():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    job  = (data or {}).get("job", "").strip()
    if not job:
        return jsonify({"error": "Invalid job"}), 400
    import shutil
    job_path = safe_join(job)
    if os.path.isdir(job_path):
        shutil.rmtree(job_path)
    return jsonify({"ok": True})

@app.route("/admin/check-auth")
@login_required
def admin_check_auth():
    return jsonify({"authenticated": bool(session.get("admin"))})

# ── Static files ─────────────────────────────────────────────
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), filename)

@app.route("/files/<path:filepath>")
@login_required
def serve_file(filepath):
    full = safe_join(filepath)
    directory = os.path.dirname(full)
    filename  = os.path.basename(full)
    return send_from_directory(directory, filename)

# ── Share links (job-level) ───────────────────────────────────
import json, secrets
from datetime import datetime

SHARES_FILE = os.path.join(JOBS_DIR, ".shares.json")

def load_shares():
    if os.path.exists(SHARES_FILE):
        try:
            with open(SHARES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_shares(shares):
    with open(SHARES_FILE, "w") as f:
        json.dump(shares, f)

@app.route("/api/share", methods=["POST"])
@login_required
def create_share():
    data = request.get_json()
    job = (data or {}).get("job", "").strip()
    if not job:
        return jsonify({"error": "Missing job"}), 400
    shares = load_shares()
    # Remove existing token for this job
    shares = {t: v for t, v in shares.items() if v.get("job") != job}
    token = secrets.token_urlsafe(16)
    shares[token] = {"job": job, "created": datetime.utcnow().isoformat()}
    save_shares(shares)
    return jsonify({"token": token, "url": f"/share/{token}"})

@app.route("/api/share/info", methods=["POST"])
@login_required
def share_info():
    data = request.get_json()
    job = (data or {}).get("job", "").strip()
    shares = load_shares()
    for token, v in shares.items():
        if v.get("job") == job:
            return jsonify({"token": token, "url": f"/share/{token}"})
    return jsonify({"token": None})

@app.route("/api/share/delete", methods=["POST"])
@login_required
def delete_share():
    data = request.get_json()
    token = (data or {}).get("token", "").strip()
    shares = load_shares()
    shares.pop(token, None)
    save_shares(shares)
    return jsonify({"ok": True})

@app.route("/share/<token>")
def view_share(token):
    shares = load_shares()
    info = shares.get(token)
    if not info:
        return "This link has expired or does not exist.", 404
    job = info["job"]
    job_path = os.path.join(JOBS_DIR, job)
    files = {}
    for cat in CATEGORIES:
        cat_path = os.path.join(job_path, cat)
        if os.path.isdir(cat_path):
            cat_files = sorted([f for f in os.listdir(cat_path) if f.lower().endswith(".pdf")])
            if cat_files:
                files[cat] = cat_files
    return render_template("share_view.html", token=token, job=job, files=files)

@app.route("/share/<token>/file/<path:filepath>")
def serve_share_file(token, filepath):
    shares = load_shares()
    info = shares.get(token)
    if not info:
        return "Link not found", 404
    full = safe_join(info["job"], filepath)
    return send_from_directory(os.path.dirname(full), os.path.basename(full))

# ── Compass Share Links ───────────────────────────────────────
COMPASS_SHARES_FILE = os.path.join(JOBS_DIR, ".compass_shares.json")

def load_compass_shares():
    if os.path.exists(COMPASS_SHARES_FILE):
        try:
            with open(COMPASS_SHARES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_compass_shares(shares):
    with open(COMPASS_SHARES_FILE, "w") as f:
        json.dump(shares, f)

@app.route("/api/compass-share", methods=["POST"])
@login_required
def create_compass_share():
    data = request.get_json()
    job = (data or {}).get("job", "").strip()
    if not job:
        return jsonify({"error": "Missing job"}), 400
    shares = load_compass_shares()
    shares = {t: v for t, v in shares.items() if v.get("job") != job}
    token = secrets.token_urlsafe(16)
    shares[token] = {"job": job, "created": datetime.utcnow().isoformat()}
    save_compass_shares(shares)
    return jsonify({"token": token, "url": f"/compass/{token}"})

@app.route("/api/compass-share/info", methods=["POST"])
@login_required
def compass_share_info():
    data = request.get_json()
    job = (data or {}).get("job", "").strip()
    shares = load_compass_shares()
    for token, v in shares.items():
        if v.get("job") == job:
            return jsonify({"token": token, "url": f"/compass/{token}"})
    return jsonify({"token": None})

@app.route("/api/compass-share/delete", methods=["POST"])
@login_required
def delete_compass_share():
    data = request.get_json()
    token = (data or {}).get("token", "").strip()
    shares = load_compass_shares()
    shares.pop(token, None)
    save_compass_shares(shares)
    return jsonify({"ok": True})

@app.route("/compass/<token>")
def view_compass_share(token):
    shares = load_compass_shares()
    info = shares.get(token)
    if not info:
        return "This link has expired or does not exist.", 404
    job = info["job"]
    bp_path = os.path.join(JOBS_DIR, job, "Blueprints")
    blueprints = sorted([f for f in os.listdir(bp_path) if f.lower().endswith(".pdf")]) if os.path.isdir(bp_path) else []
    return render_template("compass_share.html", token=token, job=job, blueprints=blueprints)

@app.route("/compass/<token>/file/<path:filepath>")
def serve_compass_share_file(token, filepath):
    shares = load_compass_shares()
    info = shares.get(token)
    if not info:
        return "Link not found", 404
    full = safe_join(info["job"], "Blueprints", filepath)
    return send_from_directory(os.path.dirname(full), os.path.basename(full))

# ── Blueprint Hyperlinks ──────────────────────────────────────
import threading, shutil, uuid as _uuid

# In-memory job store: job_id -> {status, result_path, out_name, added, error}
_hl_jobs = {}
_hl_lock = threading.Lock()


def _find_d_pages(doc):
    """
    Scan every page for D-page titles using font size as the signal.
    For each D-number (D1–D30), the page where it appears in the LARGEST
    font is the title page for that detail — works on any KPS blueprint.
    Returns dict: {dn: page_index}
    """
    import fitz
    # d_best: dn -> (page_index, max_font_size_seen)
    d_best = {}
    for pi in range(len(doc)):
        page = doc[pi]
        try:
            blocks = page.get_text("dict")["blocks"]
        except Exception:
            continue
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    sz  = span.get("size", 0)
                    for m in re.finditer(r'\bD(\d{1,2})\b', txt):
                        dn = int(m.group(1))
                        if 1 <= dn <= 30:
                            if dn not in d_best or sz > d_best[dn][1]:
                                d_best[dn] = (pi, sz)
    return {dn: pi for dn, (pi, _) in d_best.items()}


def _run_hyperlink_job(job_id, pdf_path, display_name):
    """Background thread: detect callout circles, find D-pages, insert links."""
    import fitz
    from callout_engine import detect_callouts_on_page

    out_path = pdf_path + "_out.pdf"
    try:
        doc = fitz.open(pdf_path)

        # 1. Detect callouts on every page
        all_callouts = []
        for pi in range(len(doc)):
            all_callouts.extend(detect_callouts_on_page(doc, pi))

        # 2. Find D-pages by largest font occurrence of "Dn"
        needed_dns = {c["dp"] for c in all_callouts}
        all_d_pages = _find_d_pages(doc)
        d_page_map = {dn: pi for dn, pi in all_d_pages.items() if dn in needed_dns}

        # 3. Apply orange highlights + GoTo links (link to top of D-page)
        ORANGE, BORDER = (1.0, 0.65, 0.2), (0.85, 0.45, 0.0)
        added = 0
        for c in all_callouts:
            dest_pi = d_page_map.get(c["dp"])
            if dest_pi is None:
                continue
            rect = fitz.Rect(c["r"])
            page = doc[c["pi"]]
            sh = page.new_shape()
            sh.draw_rect(rect)
            sh.finish(color=BORDER, fill=ORANGE, fill_opacity=0.35, width=1.2)
            sh.commit()
            page.insert_link({"kind": fitz.LINK_GOTO, "from": rect,
                               "page": dest_pi, "to": fitz.Point(0, 0)})
            added += 1

        doc.save(out_path, garbage=4, deflate=True, incremental=False)
        doc.close()

        out_name = re.sub(r'\.pdf$', '', display_name, flags=re.IGNORECASE) + "_linked.pdf"
        with _hl_lock:
            _hl_jobs[job_id] = {"status": "done", "result_path": out_path,
                                 "out_name": out_name, "added": added,
                                 "d_page_map": all_d_pages}
    except Exception as e:
        with _hl_lock:
            _hl_jobs[job_id] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


@app.route("/api/blueprint-hyperlinks/files")
@login_required
def api_blueprint_hyperlink_files():
    """Return all Blueprint PDFs grouped by job."""
    if not os.path.isdir(JOBS_DIR):
        return jsonify([])
    result = []
    for job in sorted(os.listdir(JOBS_DIR)):
        job_path = os.path.join(JOBS_DIR, job)
        if not os.path.isdir(job_path):
            continue
        bp_path = os.path.join(job_path, "Blueprints")
        if not os.path.isdir(bp_path):
            continue
        for f in sorted(os.listdir(bp_path)):
            if f.lower().endswith(".pdf"):
                result.append({"job": job, "filename": f})
    return jsonify(result)


@app.route("/blueprint/hyperlinks", methods=["GET", "POST"])
@login_required
def blueprint_hyperlinks():
    if request.method == "GET":
        return render_template("blueprint_hyperlinks.html")

    job_name = request.form.get("job", "").strip()
    job_file = request.form.get("filename", "").strip()
    uploaded = request.files.get("pdf")

    # Write PDF to a temp file for the background thread
    tmp_in = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        if job_name and job_file:
            server_path = safe_join(job_name, "Blueprints", job_file)
            if not os.path.isfile(server_path):
                return jsonify({"error": f"File not found: {job_file}"}), 404
            tmp_in.close()
            shutil.copy2(server_path, tmp_in.name)
            display_name = job_file
        elif uploaded and uploaded.filename.lower().endswith(".pdf"):
            uploaded.save(tmp_in)
            tmp_in.close()
            display_name = uploaded.filename
        else:
            tmp_in.close()
            os.unlink(tmp_in.name)
            return jsonify({"error": "Please select a blueprint or upload a PDF."}), 400
    except Exception as e:
        try: os.unlink(tmp_in.name)
        except: pass
        return jsonify({"error": str(e)}), 500

    job_id = str(_uuid.uuid4())
    with _hl_lock:
        _hl_jobs[job_id] = {"status": "processing"}

    t = threading.Thread(target=_run_hyperlink_job,
                         args=(job_id, tmp_in.name, display_name), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/blueprint/hyperlinks/status/<job_id>")
@login_required
def blueprint_hyperlinks_status(job_id):
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"}), 404
    return jsonify({k: v for k, v in job.items() if k != "result_path"})


@app.route("/blueprint/hyperlinks/download/<job_id>")
@login_required
def blueprint_hyperlinks_download(job_id):
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return "Not ready", 404
    return send_file(job["result_path"], mimetype="application/pdf",
                     as_attachment=True, download_name=job["out_name"])


@app.route("/blueprint/hyperlinks/editor/<job_id>")
@login_required
def blueprint_hyperlinks_editor(job_id):
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return "Job not found or not ready.", 404
    return render_template("blueprint_hyperlinks_editor.html",
                           job_id=job_id, out_name=job["out_name"])


@app.route("/blueprint/hyperlinks/view/<job_id>")
@login_required
def blueprint_hyperlinks_view(job_id):
    """Serve the processed PDF for the editor viewer."""
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return "Not ready", 404
    return send_file(job["result_path"], mimetype="application/pdf")


@app.route("/blueprint/hyperlinks/links/<job_id>")
@login_required
def blueprint_hyperlinks_links(job_id):
    """Return all GoTo links from the processed PDF as JSON."""
    import fitz as _fitz
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not ready"}), 404
    try:
        doc = _fitz.open(job["result_path"])
        pages_info = []
        links = []
        for pi in range(len(doc)):
            page = doc[pi]
            pages_info.append({"width": page.rect.width, "height": page.rect.height})
            for lk in page.get_links():
                if lk.get("kind") == _fitz.LINK_GOTO:
                    r = lk["from"]
                    links.append({
                        "page": pi,
                        "rect": [r.x0, r.y0, r.x1, r.y1],
                        "dest_page": lk.get("page", 0)
                    })
        doc.close()
        d_page_map = {str(k): v for k, v in (job.get("d_page_map") or {}).items()}
        return jsonify({"pages": pages_info, "links": links, "d_pages": d_page_map})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/blueprint/hyperlinks/save/<job_id>", methods=["POST"])
@login_required
def blueprint_hyperlinks_save(job_id):
    """Accept edited links JSON, rebuild PDF, return as download."""
    import fitz as _fitz
    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    edited_links = data.get("links", [])

    try:
        doc = _fitz.open(job["result_path"])

        # Remove all existing GoTo links
        for pi in range(len(doc)):
            page = doc[pi]
            for lk in page.get_links():
                if lk.get("kind") == _fitz.LINK_GOTO:
                    page.delete_link(lk)

        # Re-insert links from edited data (orange highlight already in PDF)
        for lk in edited_links:
            pi = lk["page"]
            if pi < 0 or pi >= len(doc):
                continue
            dest = lk["dest_page"]
            if dest < 0 or dest >= len(doc):
                continue
            rect = _fitz.Rect(lk["rect"])
            doc[pi].insert_link({
                "kind": _fitz.LINK_GOTO,
                "from": rect,
                "page": dest,
                "to": _fitz.Point(0, 0)
            })

        buf = io.BytesIO()
        doc.save(buf, garbage=4, deflate=True, incremental=False)
        doc.close()
        buf.seek(0)

        # Update stored file with saved version
        with open(job["result_path"], "wb") as f:
            f.write(buf.getvalue())
        buf.seek(0)

        return send_file(buf, mimetype="application/pdf",
                         as_attachment=True, download_name=job["out_name"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
