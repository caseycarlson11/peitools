from flask import Flask, send_from_directory, send_file, render_template, request, jsonify, session, abort, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os, re, sys, io, tempfile

# Make BlueprintLinker importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'BlueprintLinker'))

app = Flask(__name__)
app.secret_key = "pei-tools-secret-2024"
app.config['TEMPLATES_AUTO_RELOAD'] = True


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
            is_json = (request.content_type or '').startswith('application/json')
            if request.path.startswith("/api/") or request.path.startswith("/files/") or is_json:
                return jsonify({"error": "Unauthorized — please log in again"}), 401
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
    # Include DXF CAD FILE so admin can verify uploads
    cad_path = os.path.join(job_path, CAD_FOLDER)
    if os.path.isdir(cad_path):
        cad_files = sorted([f for f in os.listdir(cad_path)
                            if os.path.splitext(f)[1].lower() in {".dxf", ".dwg"}])
        if cad_files:
            result[CAD_FOLDER] = cad_files
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
        LINK_SIZE = 49  # match manual stamp size (px in PDF points)
        added = 0
        for c in all_callouts:
            dest_pi = d_page_map.get(c["dp"])
            if dest_pi is None:
                continue
            # Centre the fixed-size rect on the detected callout centre
            cx, cy = c["cx"], c["cy"]
            half = LINK_SIZE / 2
            rect = fitz.Rect(cx - half, cy - half, cx + half, cy + half)
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
        _hl_jobs[job_id] = {
            "status": "processing",
            "source_job": job_name if job_name else None,
            "source_filename": job_file if job_file else None,
        }

    t = threading.Thread(target=_run_hyperlink_job,
                         args=(job_id, tmp_in.name, display_name), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/blueprint/hyperlinks/open", methods=["POST"])
@login_required
def blueprint_hyperlinks_open():
    """Open a PDF directly in the editor without running OCR processing."""
    job_name = request.form.get("job", "").strip()
    job_file = request.form.get("filename", "").strip()
    uploaded = request.files.get("pdf")

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

    # Find D-pages so the editor knows about D-labels
    try:
        import fitz as _fitz
        doc = _fitz.open(tmp_in.name)
        d_page_map = _find_d_pages(doc)
        doc.close()
    except Exception:
        d_page_map = {}

    out_name = re.sub(r'\.pdf$', '', display_name, flags=re.IGNORECASE) + "_edited.pdf"
    job_id = str(_uuid.uuid4())
    with _hl_lock:
        _hl_jobs[job_id] = {
            "status": "done",
            "result_path": tmp_in.name,
            "out_name": out_name,
            "added": 0,
            "d_page_map": d_page_map,
            "source_job": job_name if job_name else None,
            "source_filename": job_file if job_file else None,
        }
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
                           job_id=job_id,
                           out_name=job["out_name"],
                           source_job=job.get("source_job") or "",
                           source_filename=job.get("source_filename") or "")


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


@app.route("/blueprint/hyperlinks/publish/<job_id>", methods=["POST"])
@login_required
def blueprint_hyperlinks_publish(job_id):
    """Replace the original blueprint on the server with the linked version.
    Archives the old file in Old Versions/ and deletes archives older than 30 days."""
    import fitz as _fitz
    from datetime import datetime, timedelta

    with _hl_lock:
        job = _hl_jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Job not found"}), 404

    source_job      = job.get("source_job")
    source_filename = job.get("source_filename")
    if not source_job or not source_filename:
        return jsonify({"error": "No source file to publish to — this PDF was uploaded, not selected from a job."}), 400

    # Paths
    bp_dir      = safe_join(source_job, "Blueprints")
    target_path = os.path.join(bp_dir, source_filename)
    old_dir     = os.path.join(bp_dir, "Old Versions")
    os.makedirs(old_dir, exist_ok=True)

    # Save current editor state to the result file first
    data = request.get_json(silent=True) or {}
    edited_links = data.get("links")
    if edited_links is not None:
        try:
            doc = _fitz.open(job["result_path"])
            for pi in range(len(doc)):
                for lk in doc[pi].get_links():
                    if lk.get("kind") == _fitz.LINK_GOTO:
                        doc[pi].delete_link(lk)
            for lk in edited_links:
                pi = lk["page"]
                if 0 <= pi < len(doc) and 0 <= lk["dest_page"] < len(doc):
                    doc[pi].insert_link({
                        "kind": _fitz.LINK_GOTO,
                        "from": _fitz.Rect(lk["rect"]),
                        "page": lk["dest_page"],
                        "to": _fitz.Point(0, 0)
                    })
            doc.save(job["result_path"] + "_pub.pdf", garbage=4, deflate=True, incremental=False)
            doc.close()
            pub_path = job["result_path"] + "_pub.pdf"
        except Exception as e:
            return jsonify({"error": f"Failed to save links: {e}"}), 500
    else:
        pub_path = job["result_path"]

    try:
        # Archive old file with timestamp
        if os.path.isfile(target_path):
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base = os.path.splitext(source_filename)[0]
            archive_name = f"{base}__{ts}.pdf"
            shutil.move(target_path, os.path.join(old_dir, archive_name))

        # Copy new file into place
        shutil.copy2(pub_path, target_path)

        # Clean up tmp pub file
        if pub_path != job["result_path"]:
            try: os.unlink(pub_path)
            except: pass

        # Delete Old Versions files older than 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        for fname in os.listdir(old_dir):
            fpath = os.path.join(old_dir, fname)
            if os.path.isfile(fpath):
                mtime = datetime.utcfromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    try: os.unlink(fpath)
                    except: pass

        return jsonify({"ok": True, "message": f"Published to {source_job} / {source_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500






# ── Packing List Tracker ──────────────────────────────────────────────────────
import threading as _threading
import json as _json

_pl_jobs      = {}
_pl_jobs_lock = _threading.Lock()

def _pl_tracking_dir(job_name):  return safe_join(job_name, "Delivery Tracking")
def _pl_dxf_dir(job_name):
    d = safe_join(job_name, "DXF CAD FILE")
    return d if os.path.isdir(d) else None
def _pl_state_path(job_name):    return os.path.join(_pl_tracking_dir(job_name), "delivery_state.json")
def _pl_cache_path(job_name):    return os.path.join(_pl_tracking_dir(job_name), "panel_locations_v2.json")  # v2 = DXF-coordinate locator
def _pl_output_path(job_name):   return os.path.join(_pl_tracking_dir(job_name), "tracked_blueprint.pdf")
def _pl_cells_path(job_name):    return os.path.join(_pl_tracking_dir(job_name), "table_cells.json")

def _find_blueprint(job_name):
    bp_dir = safe_join(job_name, "Blueprints")
    if os.path.isdir(bp_dir):
        for f in sorted(os.listdir(bp_dir)):
            if f.lower().endswith(".pdf") and "Old Versions" not in f and "Delivery Tracked" not in f:
                return os.path.join(bp_dir, f)
    return None

def _run_pl_job(job_name, packing_list_path, shipment_label):
    try:
        from packing_list_engine import parse_packing_list, scan_blueprint_panels, generate_tracked_blueprint
        os.makedirs(_pl_tracking_dir(job_name), exist_ok=True)

        delivery_state = {}
        if os.path.exists(_pl_state_path(job_name)):
            with open(_pl_state_path(job_name)) as f:
                delivery_state = _json.load(f)

        with _pl_jobs_lock:
            _pl_jobs[job_name].update({"message": "Parsing packing list...", "progress": 10})

        panels_added = 0
        parsed, parse_warnings = parse_packing_list(packing_list_path)
        with _pl_jobs_lock:
            skid_count = len(parsed)
            raw_panels = sum(len(v) for v in parsed.values())
            _pl_jobs[job_name].update({"message": f"Parsed {raw_panels} panels across {skid_count} skids…", "progress": 15})

        for skid_num, panels in parsed.items():
            for p in panels:
                if p not in delivery_state:
                    delivery_state[p] = {"skid": skid_num, "shipment": shipment_label}
                    panels_added += 1

        with _pl_jobs_lock:
            _pl_jobs[job_name].update({"message": f"Added {panels_added} new panels — scanning blueprint…", "progress": 18})

        with open(_pl_state_path(job_name), "w") as f:
            _json.dump(delivery_state, f)

        blueprint_path = _find_blueprint(job_name)
        if not blueprint_path:
            raise FileNotFoundError("No blueprint PDF found for this job.")

        def progress_cb(pg, total):
            with _pl_jobs_lock:
                _pl_jobs[job_name].update({
                    "progress": 20 + int(60 * pg / max(total, 1)),
                    "message": f"Scanning blueprint page {pg+1}/{total}..."
                })

        dxf_dir = _pl_dxf_dir(job_name)
        # Report DXF status before scanning
        if dxf_dir:
            try:
                import ezdxf as _ezdxf_check
                dxf_status = f"DXF validation active ({os.path.basename(dxf_dir)})"
            except ImportError:
                dxf_status = "⚠ DXF validation unavailable — ezdxf not installed (run deploy.bat)"
                dxf_dir = None
        else:
            dxf_status = "⚠ No DXF folder found — panel numbers not validated"
        with _pl_jobs_lock:
            _pl_jobs[job_name].update({"message": f"Scanning blueprint… {dxf_status}", "progress": 19})

        panel_locations = scan_blueprint_panels(blueprint_path, _pl_cache_path(job_name), progress_cb, dxf_dir=dxf_dir)

        # Re-apply the user's saved manual corrections so re-processing never
        # undoes their hand-fixes (deletions, renumbers, manual additions).
        corr = _pl_load_corrections(job_name)
        if any(corr.get(k) for k in ("deletions", "renames", "additions")):
            _apply_corrections(delivery_state, panel_locations, corr)
            with open(_pl_state_path(job_name), "w") as f:
                _json.dump(delivery_state, f)
            with open(_pl_cache_path(job_name), "w") as f:
                _json.dump(panel_locations, f)

        with _pl_jobs_lock:
            _pl_jobs[job_name].update({"progress": 85, "message": "Generating annotated blueprint..."})

        table_cells = generate_tracked_blueprint(blueprint_path, delivery_state, panel_locations, _pl_output_path(job_name))
        try:
            with open(_pl_cells_path(job_name), "w") as f:
                _json.dump(table_cells or {}, f)
        except Exception:
            pass

        located = sum(1 for p in delivery_state if p in panel_locations)
        with _pl_jobs_lock:
            _pl_jobs[job_name].update({
                "status": "done", "progress": 100,
                "message": f"Complete — {panels_added} new panels added, {located} located on blueprint",
                "panels_added": panels_added, "total_panels": len(delivery_state),
                "warnings": parse_warnings,
                "located": located,
                "skids": sorted(set(v["skid"] for v in delivery_state.values()), key=lambda x: (int(x) if str(x).isdigit() else float('inf'), str(x))),
            })
    except Exception as e:
        with _pl_jobs_lock:
            _pl_jobs[job_name].update({"status": "error", "message": str(e)})


# ── Panel Print Mapper ────────────────────────────────────────────────────────
# Verification tool: render a job's blueprint with every panel boxed in red and
# its number labeled above, so a human can confirm panels are read correctly.

_pm_jobs = {}                     # job_name -> {status, progress, message, ...}
_pm_jobs_lock = _threading.Lock()

def _pm_dir(job_name):
    return safe_join(job_name, "Panel Map")

def _pm_safe(name):
    base = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:80]

def _pm_sig(pages):
    """Short signature for a kept-pages selection (None/empty = whole doc)."""
    if not pages:
        return ""
    import hashlib
    key = ",".join(str(p) for p in sorted(pages))
    return "_p" + hashlib.md5(key.encode()).hexdigest()[:8]

def _pm_cache_path(job_name, bp_name, pages=None):
    return os.path.join(_pm_dir(job_name), f"locs_{_pm_safe(bp_name)}{_pm_sig(pages)}.json")

def _pm_output_path(job_name, bp_name):
    return os.path.join(_pm_dir(job_name), f"map_{_pm_safe(bp_name)}.pdf")

def _pm_session_path(job_name):
    return os.path.join(_pm_dir(job_name), "session.json")

def _pm_load_session(job_name):
    p = _pm_session_path(job_name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return _json.load(f)
        except Exception:
            pass
    return None

def _pm_page_dims(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    dims = [{"w": pg.rect.width, "h": pg.rect.height} for pg in doc]
    doc.close()
    return dims

def _pm_make_trimmed(bp_path, pages, dest):
    """Write a new PDF containing only `pages` (1-based) from bp_path, in order."""
    import fitz
    src = fitz.open(bp_path)
    keep = sorted({p - 1 for p in pages if 1 <= p <= src.page_count})
    if not keep:
        keep = list(range(src.page_count))
    src.select(keep)
    src.save(dest, garbage=4, deflate=True)
    src.close()
    return len(keep)

def _run_pm_job(job_name, bp_name, pages=None):
    try:
        from packing_list_engine import scan_blueprint_panels, generate_panel_map_blueprint
        os.makedirs(_pm_dir(job_name), exist_ok=True)

        bp_path = safe_join(job_name, "Blueprints", bp_name)
        if not os.path.isfile(bp_path):
            raise FileNotFoundError(f"Blueprint not found: {bp_name}")

        # If the user pre-selected pages, scan a trimmed copy so blank pages are
        # never even OCR'd (much faster). Otherwise scan the whole blueprint.
        scan_path = bp_path
        if pages:
            trimmed = os.path.join(_pm_dir(job_name), f"trimmed_{_pm_safe(bp_name)}{_pm_sig(pages)}.pdf")
            kept_n = _pm_make_trimmed(bp_path, pages, trimmed)
            scan_path = trimmed
            with _pm_jobs_lock:
                _pm_jobs[job_name].update({"message": f"Scanning {kept_n} selected pages…"})

        dxf_dir = _pl_dxf_dir(job_name)
        if dxf_dir:
            try:
                import ezdxf as _ezdxf_check  # noqa: F401
                dxf_status = "DXF validation active"
            except ImportError:
                dxf_status = "⚠ ezdxf not installed — panels not validated"
                dxf_dir = None
        else:
            dxf_status = "⚠ No DXF folder — panel numbers not validated"

        with _pm_jobs_lock:
            _pm_jobs[job_name].update({"message": f"Scanning blueprint… {dxf_status}", "progress": 10})

        def progress_cb(pg, total):
            with _pm_jobs_lock:
                _pm_jobs[job_name].update({
                    "progress": 10 + int(70 * pg / max(total, 1)),
                    "message": f"Scanning page {pg+1}/{total}…",
                })

        panel_locations = scan_blueprint_panels(
            scan_path, _pm_cache_path(job_name, bp_name, pages), progress_cb, dxf_dir=dxf_dir)

        with _pm_jobs_lock:
            _pm_jobs[job_name].update({"progress": 85, "message": "Drawing panel map…"})

        # Keep ALL loaded pages in the output (the user already chose which pages
        # to include), even pages where no panels were detected.
        result = generate_panel_map_blueprint(
            scan_path, panel_locations, _pm_output_path(job_name, bp_name),
            keep_only_panel_pages=False)
        drawn   = result["drawn"]
        out_pgs = result["output_pages"]
        withp   = result["pages_with_panels"]

        # Save a session so the editor can reload the base prints + panel positions.
        try:
            with open(_pm_session_path(job_name), "w") as f:
                _json.dump({"bp_name": bp_name, "scan_pdf": scan_path,
                            "locs": _pm_cache_path(job_name, bp_name, pages),
                            "pages": pages or []}, f)
        except Exception:
            pass

        with _pm_jobs_lock:
            _pm_jobs[job_name].update({
                "status": "done", "progress": 100, "blueprint": bp_name,
                "message": f"Complete — {drawn} panels mapped over {out_pgs} pages "
                           f"({withp} page(s) had panels).",
                "panels": drawn, "output_pages": out_pgs,
                "pages_with_panels": withp, "panel_pages": result["panel_pages"],
            })
    except Exception as e:
        with _pm_jobs_lock:
            _pm_jobs[job_name].update({"status": "error", "message": str(e)})


@app.route("/panel-print-mapper")
@login_required
def panel_print_mapper():
    return render_template("panel_print_mapper.html")


@app.route("/api/panel-map/blueprints/<path:job_name>")
@login_required
def panel_map_blueprints(job_name):
    """List blueprint PDFs for a job, plus whether the job has DXF validation."""
    bp_dir = safe_join(job_name, "Blueprints")
    files = []
    if os.path.isdir(bp_dir):
        for f in sorted(os.listdir(bp_dir)):
            if not f.lower().endswith(".pdf") or "Delivery Tracked" in f:
                continue
            try:
                d = datetime.fromtimestamp(os.path.getmtime(os.path.join(bp_dir, f)))
                date = f"{d.strftime('%b')} {d.day}, {d.year}"
            except Exception:
                date = ""
            files.append({"name": f, "date": date})
    return jsonify({"blueprints": files, "has_dxf": _pl_dxf_dir(job_name) is not None})


@app.route("/api/panel-map/process/<path:job_name>", methods=["POST"])
@login_required
def panel_map_process(job_name):
    data    = request.get_json(silent=True) or {}
    bp_name = (data.get("blueprint") or "").strip()
    if not bp_name or not bp_name.lower().endswith(".pdf"):
        return jsonify({"error": "Choose a blueprint PDF"}), 400
    if not os.path.isfile(safe_join(job_name, "Blueprints", bp_name)):
        return jsonify({"error": f"Blueprint not found: {bp_name}"}), 404

    # Optional manual page selection (1-based page numbers to keep / scan).
    pages = data.get("pages")
    if pages:
        try:
            pages = sorted({int(p) for p in pages if int(p) >= 1})
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid page selection"}), 400
        if not pages:
            return jsonify({"error": "Select at least one page"}), 400
    else:
        pages = None

    if data.get("rescan"):
        cp = _pm_cache_path(job_name, bp_name, pages)
        if os.path.exists(cp):
            os.unlink(cp)
    with _pm_jobs_lock:
        _pm_jobs[job_name] = {"status": "processing", "progress": 0,
                              "message": "Starting…", "blueprint": bp_name}
    _threading.Thread(target=_run_pm_job, args=(job_name, bp_name, pages), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/panel-map/load-only/<path:job_name>", methods=["POST"])
@login_required
def panel_map_load_only(job_name):
    """Load the selected pages into the editor WITHOUT detecting panels — the user
    will place every panel by hand. Sets up an empty session and opens the editor."""
    from packing_list_engine import generate_panel_map_blueprint
    data    = request.get_json(silent=True) or {}
    bp_name = (data.get("blueprint") or "").strip()
    if not bp_name or not bp_name.lower().endswith(".pdf"):
        return jsonify({"error": "Choose a blueprint PDF"}), 400
    bp_path = safe_join(job_name, "Blueprints", bp_name)
    if not os.path.isfile(bp_path):
        return jsonify({"error": f"Blueprint not found: {bp_name}"}), 404

    pages = data.get("pages")
    if pages:
        try:
            pages = sorted({int(p) for p in pages if int(p) >= 1})
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid page selection"}), 400
        if not pages:
            return jsonify({"error": "Select at least one page"}), 400
    else:
        pages = None

    os.makedirs(_pm_dir(job_name), exist_ok=True)

    # Trim to the selected pages (or use the whole blueprint).
    scan_path = bp_path
    if pages:
        scan_path = os.path.join(_pm_dir(job_name),
                                 f"trimmed_{_pm_safe(bp_name)}{_pm_sig(pages)}.pdf")
        _pm_make_trimmed(bp_path, pages, scan_path)

    # Empty panel set — the editor starts with a clean sheet to add panels onto.
    locs_path = _pm_cache_path(job_name, bp_name, pages)
    with open(locs_path, "w") as f:
        _json.dump({}, f)

    with open(_pm_session_path(job_name), "w") as f:
        _json.dump({"bp_name": bp_name, "scan_pdf": scan_path,
                    "locs": locs_path, "pages": pages or []}, f)

    # Produce an (un-annotated) output so Download/Open still work before any edits.
    try:
        generate_panel_map_blueprint(scan_path, {}, _pm_output_path(job_name, bp_name),
                                     keep_only_panel_pages=False)
    except Exception:
        pass

    return jsonify({"ok": True})


@app.route("/api/panel-map/status/<path:job_name>")
@login_required
def panel_map_status(job_name):
    with _pm_jobs_lock:
        job = dict(_pm_jobs.get(job_name, {}))
    bp_name = job.get("blueprint", "")
    job["has_output"] = bool(bp_name) and os.path.exists(_pm_output_path(job_name, bp_name))
    return jsonify(job)


@app.route("/api/panel-map/download/<path:job_name>")
@login_required
def panel_map_download(job_name):
    bp_name = (request.args.get("blueprint") or "").strip()
    if not bp_name:
        with _pm_jobs_lock:
            bp_name = _pm_jobs.get(job_name, {}).get("blueprint", "")
    out = _pm_output_path(job_name, bp_name) if bp_name else None
    if not out or not os.path.exists(out):
        return jsonify({"error": "No panel map yet"}), 404
    return send_file(out, mimetype="application/pdf", as_attachment=False,
                     download_name=f"{job_name} - Panel Map.pdf")


# ── Panel map editor (select / renumber / delete / add panels) ───────────────
@app.route("/panel-map/editor/<path:job_name>")
@login_required
def panel_map_editor(job_name):
    return render_template("panel_map_editor.html", job_name=job_name)


@app.route("/api/panel-map/editor-data/<path:job_name>")
@login_required
def panel_map_editor_data(job_name):
    sess = _pm_load_session(job_name)
    if not sess or not os.path.isfile(sess.get("scan_pdf", "")):
        return jsonify({"error": "Run the panel mapper first."}), 404
    locs = {}
    if os.path.isfile(sess.get("locs", "")):
        with open(sess["locs"]) as f:
            locs = _json.load(f)
    return jsonify({
        "job": job_name,
        "blueprint": sess.get("bp_name", ""),
        "pages": _pm_page_dims(sess["scan_pdf"]),
        "panel_locations": locs,
    })


@app.route("/api/panel-map/base/<path:job_name>")
@login_required
def panel_map_base(job_name):
    sess = _pm_load_session(job_name)
    if not sess or not os.path.isfile(sess.get("scan_pdf", "")):
        return jsonify({"error": "No base PDF"}), 404
    return send_file(sess["scan_pdf"], mimetype="application/pdf")


@app.route("/api/panel-map/update/<path:job_name>", methods=["POST"])
@login_required
def panel_map_update(job_name):
    from packing_list_engine import generate_panel_map_blueprint
    sess = _pm_load_session(job_name)
    if not sess or not os.path.isfile(sess.get("scan_pdf", "")):
        return jsonify({"error": "Run the panel mapper first."}), 404
    locs = {}
    if os.path.isfile(sess.get("locs", "")):
        with open(sess["locs"]) as f:
            locs = _json.load(f)

    data = request.get_json(silent=True) or {}
    new_locs = data.get("locations")
    if not isinstance(new_locs, dict):
        return jsonify({"error": "Missing locations"}), 400

    clean = {}
    for panel, v in new_locs.items():
        p = str(panel).strip()
        if not p or not isinstance(v, dict):
            continue
        try:
            bbox = [float(x) for x in v.get("bbox", [])][:4]
            if len(bbox) != 4:
                continue
            clean[p] = {"page": int(v.get("page")), "bbox": bbox}
        except (TypeError, ValueError):
            continue

    old_keys = set(locs.keys())
    new_keys = set(clean.keys())

    os.makedirs(_pm_dir(job_name), exist_ok=True)
    with open(sess["locs"], "w") as f:
        _json.dump(clean, f)

    # Regenerate the map PDF with the corrected panels.
    bp_name = sess.get("bp_name", "")
    result = generate_panel_map_blueprint(
        sess["scan_pdf"], clean, _pm_output_path(job_name, bp_name),
        keep_only_panel_pages=False)

    # Log the human corrections to the shared cross-project record so the
    # packing-list tracker can benefit from how panels were dialed in.
    try:
        ts = datetime.utcnow().isoformat()
        with open(_GLOBAL_CORRECTIONS, "a") as gf:
            for p in (old_keys - new_keys):
                gf.write(_json.dumps({"type": "pm_remove", "panel": p, "job": job_name, "ts": ts}) + "\n")
            for p in (new_keys - old_keys):
                gf.write(_json.dumps({"type": "pm_add", "panel": p,
                                      "page": clean[p]["page"], "bbox": clean[p]["bbox"],
                                      "job": job_name, "ts": ts}) + "\n")
    except Exception:
        pass

    return jsonify({"ok": True, "panel_locations": clean,
                    "count": len(clean), "output_pages": result["output_pages"]})


@app.route("/packing-list-tracker")
@login_required
def packing_list_tracker():
    return render_template("packing_list_tracker.html")


@app.route("/api/packing-list/upload/<path:job_name>", methods=["POST"])
@login_required
def packing_list_upload(job_name):
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Must be a PDF"}), 400
    os.makedirs(_pl_tracking_dir(job_name), exist_ok=True)
    label     = request.form.get("label", f.filename.replace(".pdf", ""))
    save_path = os.path.join(_pl_tracking_dir(job_name), "upload_" + f.filename)
    f.save(save_path)
    with _pl_jobs_lock:
        _pl_jobs[job_name] = {"status": "processing", "progress": 0, "message": "Starting..."}
    _threading.Thread(target=_run_pl_job, args=(job_name, save_path, label), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/packing-list/process-file/<path:job_name>", methods=["POST"])
@login_required
def packing_list_process_file(job_name):
    data     = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()
    if not filename or not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Invalid filename"}), 400
    pl_path = safe_join(job_name, "Packing Lists", filename)
    if not os.path.isfile(pl_path):
        return jsonify({"error": f"File not found: {filename}"}), 404
    label = data.get("label") or filename.replace(".pdf", "")
    with _pl_jobs_lock:
        _pl_jobs[job_name] = {"status": "processing", "progress": 0, "message": "Starting..."}
    _threading.Thread(target=_run_pl_job, args=(job_name, pl_path, label), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/packing-list/status/<path:job_name>")
@login_required
def packing_list_status(job_name):
    with _pl_jobs_lock:
        job = dict(_pl_jobs.get(job_name, {}))
    if os.path.exists(_pl_state_path(job_name)):
        with open(_pl_state_path(job_name)) as f:
            state = _json.load(f)

        # Build per-shipment stats preserving insertion order (= color index order)
        shipment_info = {}   # label -> {count, skids, color_index}
        for info in state.values():
            s = info.get("shipment", "Unknown")
            if s not in shipment_info:
                shipment_info[s] = {"count": 0, "skids": set(), "color_index": len(shipment_info)}
            shipment_info[s]["count"] += 1
            shipment_info[s]["skids"].add(info.get("skid", ""))

        job["total_panels"] = len(state)
        _sk = lambda x: (int(x) if str(x).isdigit() else float('inf'), str(x))
        job["total_skids"]  = sorted(set(v["skid"] for v in state.values()), key=_sk)
        job["shipments"]    = [
            {"label": k, "count": v["count"],
             "skids": sorted(v["skids"], key=_sk),
             "color_index": v["color_index"]}
            for k, v in shipment_info.items()
        ]
        # Map filename -> color_index so the UI can highlight file items
        job["file_colors"]  = {
            s: v["color_index"] for s, v in shipment_info.items()
        }
    job["has_output"] = os.path.exists(_pl_output_path(job_name))
    return jsonify(job)


@app.route("/api/packing-list/download/<path:job_name>")
@login_required
def packing_list_download(job_name):
    output_path = _pl_output_path(job_name)
    if not os.path.exists(output_path):
        return jsonify({"error": "No tracked blueprint yet"}), 404
    return send_file(output_path, mimetype="application/pdf",
                     as_attachment=False,
                     download_name=f"{job_name}_delivery_tracked.pdf")


@app.route("/api/packing-list/publish/<path:job_name>", methods=["POST"])
@login_required
def packing_list_publish(job_name):
    output_path = _pl_output_path(job_name)
    if not os.path.exists(output_path):
        return jsonify({"error": "No tracked blueprint to publish"}), 404
    bp_dir = safe_join(job_name, "Blueprints")
    os.makedirs(bp_dir, exist_ok=True)
    used = {int(re.match(r'^(\d+)\s*-', fn).group(1))
            for fn in os.listdir(bp_dir) if re.match(r'^(\d+)\s*-', fn)}
    n = 1
    while n in used: n += 1
    dest = os.path.join(bp_dir, f"{n} - {job_name} Delivery Tracked.pdf")
    import shutil; shutil.copy2(output_path, dest)
    return jsonify({"ok": True, "filename": os.path.basename(dest), "number": n})


@app.route("/api/packing-list/reset/<path:job_name>", methods=["POST"])
@login_required
def packing_list_reset(job_name):
    for p in [_pl_state_path(job_name), _pl_output_path(job_name)]:
        if os.path.exists(p): os.unlink(p)
    with _pl_jobs_lock:
        _pl_jobs.pop(job_name, None)
    return jsonify({"ok": True})


# ── Packing List Editor (interactive cross-reference) ─────────────────────────

_sk_key = lambda x: (int(x) if str(x).isdigit() else float('inf'), str(x))

def _pl_stats(state):
    """Per-shipment stats from a delivery_state dict, color index = first-seen order."""
    shipment_info = {}
    for info in state.values():
        s = info.get("shipment", "Unknown")
        if s not in shipment_info:
            shipment_info[s] = {"count": 0, "skids": set(), "color_index": len(shipment_info)}
        shipment_info[s]["count"] += 1
        shipment_info[s]["skids"].add(str(info.get("skid", "")))
    shipments = [
        {"label": k, "count": v["count"],
         "skids": sorted(v["skids"], key=_sk_key),
         "color_index": v["color_index"]}
        for k, v in shipment_info.items()
    ]
    return {
        "total_panels": len(state),
        "total_skids": sorted({str(v.get("skid", "")) for v in state.values()}, key=_sk_key),
        "shipments": shipments,
        "file_colors": {s: v["color_index"] for s, v in shipment_info.items()},
    }

def _pl_load_state(job_name):
    if os.path.exists(_pl_state_path(job_name)):
        with open(_pl_state_path(job_name)) as f:
            return _json.load(f)
    return {}

def _pl_load_locations(job_name):
    if os.path.exists(_pl_cache_path(job_name)):
        with open(_pl_cache_path(job_name)) as f:
            return _json.load(f)
    return {}

def _pl_load_cells(job_name):
    if os.path.exists(_pl_cells_path(job_name)):
        try:
            with open(_pl_cells_path(job_name)) as f:
                return _json.load(f)
        except Exception:
            pass
    return {}

# ── Manual corrections store ─────────────────────────────────────────────────
# Captures every hand-fix made in the editor (delete a false positive, renumber a
# panel, add a missing one). Stored per job so the fixes survive re-processing,
# and appended to a single cross-project log so future panel-finding work can
# learn from how humans corrected the automatic results.
_GLOBAL_CORRECTIONS = os.path.join(JOBS_DIR, ".panel_corrections.jsonl")

def _pl_corrections_path(job_name):
    return os.path.join(_pl_tracking_dir(job_name), "corrections.json")

def _pl_load_corrections(job_name):
    c = {}
    p = _pl_corrections_path(job_name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                c = _json.load(f)
        except Exception:
            c = {}
    c.setdefault("deletions", [])
    c.setdefault("renames", {})
    c.setdefault("additions", {})
    return c

def _pl_save_corrections(job_name, c):
    try:
        os.makedirs(_pl_tracking_dir(job_name), exist_ok=True)
        with open(_pl_corrections_path(job_name), "w") as f:
            _json.dump(c, f)
    except Exception:
        pass

def _log_global_correction(job_name, event):
    """Append one correction event to the cross-project corrections log."""
    try:
        ev = dict(event)
        ev["job"] = job_name
        ev["ts"] = datetime.utcnow().isoformat() + "Z"
        with open(_GLOBAL_CORRECTIONS, "a") as f:
            f.write(_json.dumps(ev) + "\n")
    except Exception:
        pass

def _apply_corrections(delivery_state, panel_locations, corr):
    """Re-apply a job's saved manual corrections after an automatic scan, so the
    user's fixes are not undone by re-processing."""
    for old, new in (corr.get("renames") or {}).items():
        if old in panel_locations:
            panel_locations[new] = panel_locations.pop(old)
        if old in delivery_state:
            delivery_state[new] = delivery_state.pop(old)
    for p in (corr.get("deletions") or []):
        panel_locations.pop(p, None)
        delivery_state.pop(p, None)
    for p, info in (corr.get("additions") or {}).items():
        if info.get("page") is not None and info.get("bbox"):
            panel_locations[p] = {"page": int(info["page"]), "bbox": info["bbox"]}
        if p not in delivery_state and info.get("shipment"):
            delivery_state[p] = {"skid": info.get("skid", ""), "shipment": info["shipment"]}

def _pl_blueprint_dims(job_name):
    """Per-page [{width,height}] of the job blueprint, in PDF points."""
    bp = _find_blueprint(job_name)
    if not bp:
        return [], None
    import fitz as _fitz
    doc = _fitz.open(bp)
    dims = [{"width": p.rect.width, "height": p.rect.height} for p in doc]
    doc.close()
    return dims, bp


@app.route("/packing-list/editor/<path:job_name>")
@login_required
def packing_list_editor(job_name):
    return render_template("packing_list_editor.html", job_name=job_name)


@app.route("/api/packing-list/editor-data/<path:job_name>")
@login_required
def packing_list_editor_data(job_name):
    """Everything the editor needs to render the blueprint with panel overlays."""
    state = _pl_load_state(job_name)
    locations = _pl_load_locations(job_name)
    dims, bp = _pl_blueprint_dims(job_name)
    if not bp:
        return jsonify({"error": "No blueprint PDF found for this job."}), 404

    # Available packing list files (for the right pane selector)
    pl_files = []
    pl_dir = safe_join(job_name, "Packing Lists")
    if os.path.isdir(pl_dir):
        pl_files = sorted(f for f in os.listdir(pl_dir) if f.lower().endswith(".pdf"))

    stats = _pl_stats(state)
    return jsonify({
        "job": job_name,
        "pages": dims,
        "panel_locations": locations,   # {panel: {page, bbox}}  ALL panels on blueprint
        "delivery_state": state,        # {panel: {skid, shipment}} delivered only
        "table_cells": _pl_load_cells(job_name),  # {panel: {page, bbox}} DELIVERED table row
        "packing_lists": pl_files,
        **stats,
        "has_output": os.path.exists(_pl_output_path(job_name)),
    })


@app.route("/api/packing-list/blueprint/<path:job_name>")
@login_required
def packing_list_blueprint(job_name):
    """Serve the base (un-annotated) blueprint PDF — overlays are drawn client-side."""
    bp = _find_blueprint(job_name)
    if not bp or not os.path.exists(bp):
        return jsonify({"error": "No blueprint PDF found"}), 404
    return send_file(bp, mimetype="application/pdf")


def _pl_safe_list_file(job_name, filename):
    if not filename or not filename.lower().endswith(".pdf"):
        return None
    p = safe_join(job_name, "Packing Lists", filename)
    return p if os.path.isfile(p) else None


@app.route("/api/packing-list/pl-file/<path:job_name>")
@login_required
def packing_list_pl_file(job_name):
    """Serve a single packing list PDF for the editor's right pane."""
    p = _pl_safe_list_file(job_name, request.args.get("file", ""))
    if not p:
        return jsonify({"error": "File not found"}), 404
    return send_file(p, mimetype="application/pdf")


@app.route("/api/packing-list/pl-positions/<path:job_name>")
@login_required
def packing_list_pl_positions(job_name):
    """OCR a packing list for panel-number positions (cached) for cross-highlighting."""
    filename = request.args.get("file", "")
    p = _pl_safe_list_file(job_name, filename)
    if not p:
        return jsonify({"error": "File not found"}), 404
    try:
        from packing_list_engine import scan_packing_list_positions
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        # v2 = PANEL #-column-aware scan (invalidates older full-page caches)
        cache = os.path.join(_pl_tracking_dir(job_name), f"pl_pos_v2_{safe_name}.json")
        os.makedirs(_pl_tracking_dir(job_name), exist_ok=True)
        data = scan_packing_list_positions(p, cache_path=cache)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/packing-list/update-panels/<path:job_name>", methods=["POST"])
@login_required
def packing_list_update_panels(job_name):
    """Add/remove/renumber delivered panels, then regenerate the tracked blueprint.

    Body: {
      "add":     [{"panel","skid","shipment","page"?,"bbox"?}, ...],
      "remove":  ["panel", ...],
      "renames": [{"from","to","skid"?,"shipment"?}, ...]
    }
    All edits are also recorded in the per-job + global corrections store.
    """
    data = request.get_json(silent=True) or {}
    to_add = data.get("add", []) or []
    to_remove = data.get("remove", []) or []
    renames = data.get("renames", []) or []

    state = _pl_load_state(job_name)
    locations = _pl_load_locations(job_name)
    corr = _pl_load_corrections(job_name)

    # ── Renames (renumber a panel; the table will then show the correct number) ──
    for r in renames:
        old = str(r.get("from", "")).strip()
        new = str(r.get("to", "")).strip()
        if not old or not new or old == new:
            continue
        if old in state:
            state[new] = state.pop(old)
        if old in locations:
            locations[new] = locations.pop(old)
        corr["renames"][old] = new
        if old in corr["additions"]:
            corr["additions"][new] = corr["additions"].pop(old)
        if old in corr["deletions"]:
            corr["deletions"].remove(old)
        _log_global_correction(job_name, {
            "type": "rename", "from": old, "to": new,
            "page": (locations.get(new) or {}).get("page"),
            "bbox": (locations.get(new) or {}).get("bbox")})

    removed = 0
    for panel in to_remove:
        if panel in state:
            del state[panel]
            removed += 1
        loc = locations.pop(panel, None)   # also drop the highlight location (false positives)
        if panel not in corr["deletions"]:
            corr["deletions"].append(panel)
        corr["additions"].pop(panel, None)
        _log_global_correction(job_name, {
            "type": "delete", "panel": panel,
            "page": (loc or {}).get("page"), "bbox": (loc or {}).get("bbox")})

    added = 0
    for item in to_add:
        panel = str(item.get("panel", "")).strip()
        if not panel:
            continue
        skid = str(item.get("skid", "")).strip()
        shipment = str(item.get("shipment", "")).strip() or "Manual"
        state[panel] = {"skid": skid, "shipment": shipment}
        page = item.get("page")
        bbox = None
        # If the panel wasn't located by OCR, store the box the user drew so the
        # regenerated PDF highlights it too.
        if item.get("bbox") and page is not None:
            try:
                bbox = [float(v) for v in item["bbox"]]
                locations[panel] = {"page": int(page), "bbox": bbox}
            except Exception:
                bbox = None
        # Record as a manual addition so a future re-scan keeps it.
        corr["additions"][panel] = {"panel": panel, "skid": skid, "shipment": shipment,
                                    "page": (int(page) if page is not None else None), "bbox": bbox}
        if panel in corr["deletions"]:
            corr["deletions"].remove(panel)
        _log_global_correction(job_name, {
            "type": "add", "panel": panel, "skid": skid, "shipment": shipment,
            "page": (int(page) if page is not None else None), "bbox": bbox})
        added += 1

    _pl_save_corrections(job_name, corr)

    os.makedirs(_pl_tracking_dir(job_name), exist_ok=True)
    with open(_pl_state_path(job_name), "w") as f:
        _json.dump(state, f)
    with open(_pl_cache_path(job_name), "w") as f:
        _json.dump(locations, f)

    # Regenerate the annotated PDF so Download / Publish reflect the edits.
    regen_ok, regen_err = True, None
    table_cells = {}
    try:
        from packing_list_engine import generate_tracked_blueprint
        bp = _find_blueprint(job_name)
        if bp:
            table_cells = generate_tracked_blueprint(bp, state, locations, _pl_output_path(job_name)) or {}
            try:
                with open(_pl_cells_path(job_name), "w") as f:
                    _json.dump(table_cells, f)
            except Exception:
                pass
        else:
            regen_ok, regen_err = False, "No blueprint PDF found"
    except Exception as e:
        regen_ok, regen_err = False, str(e)

    stats = _pl_stats(state)
    located = sum(1 for p in state if p in locations)
    return jsonify({
        "ok": True, "added": added, "removed": removed,
        "located": located, "regenerated": regen_ok, "regen_error": regen_err,
        "panel_locations": locations,
        "delivery_state": state,
        "table_cells": table_cells,
        **stats,
        "has_output": os.path.exists(_pl_output_path(job_name)),
    })


# ── Public document links (shareable without login) ──────────────────────────
PL_DOCLINKS_FILE = os.path.join(JOBS_DIR, ".pl_doclinks.json")

def _load_doclinks():
    if os.path.exists(PL_DOCLINKS_FILE):
        try:
            with open(PL_DOCLINKS_FILE) as f:
                return _json.load(f)
        except Exception:
            pass
    return {}

def _save_doclinks(d):
    try:
        with open(PL_DOCLINKS_FILE, "w") as f:
            _json.dump(d, f)
    except Exception:
        pass


@app.route("/api/packing-list/public-link/<path:job_name>", methods=["POST"])
@login_required
def packing_list_public_link(job_name):
    """Create (or reuse) a public, login-free link to a document for SMS/email sharing."""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "bp")
    file = (data.get("file") or "").strip()
    if kind not in ("bp", "pl"):
        return jsonify({"error": "Bad document type"}), 400
    if kind == "bp":
        if not os.path.exists(_pl_output_path(job_name)):
            return jsonify({"error": "No tracked blueprint yet — process a packing list first"}), 404
    else:
        if not file.lower().endswith(".pdf") or not _pl_safe_list_file(job_name, file):
            return jsonify({"error": "Packing list not found"}), 404

    rotate = bool(data.get("rotate"))
    links = _load_doclinks()
    want_file = file if kind == "pl" else ""
    def _matches(v):
        return v.get("job") == job_name and v.get("kind") == kind and (v.get("file") or "") == want_file
    if rotate:
        # "Change link" — revoke any previous link(s) for this document.
        links = {t: v for t, v in links.items() if not _matches(v)}
    else:
        # One link per document — reuse the existing token if there is one.
        for t, v in links.items():
            if _matches(v):
                return jsonify({"url": f"/p/{t}", "rotated": False})
    token = secrets.token_urlsafe(12)
    links[token] = {"job": job_name, "kind": kind, "file": want_file,
                    "created": datetime.utcnow().isoformat()}
    _save_doclinks(links)
    return jsonify({"url": f"/p/{token}", "rotated": rotate})


@app.route("/p/<token>")
def public_doc(token):
    """Serve a shared document with no login required."""
    info = _load_doclinks().get(token)
    if not info:
        return "This link has expired or does not exist.", 404
    job, kind, file = info["job"], info.get("kind", "bp"), info.get("file", "")
    path = _pl_output_path(job) if kind == "bp" else _pl_safe_list_file(job, file)
    if not path or not os.path.exists(path):
        return "Document not found.", 404
    dl = f"{job} Delivery Tracked.pdf" if kind == "bp" else file
    return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=dl)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=True)
