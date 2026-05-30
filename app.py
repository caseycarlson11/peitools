from flask import Flask, send_from_directory, render_template, request, jsonify, session, abort
import os, re

app = Flask(__name__)
app.secret_key = "pei-tools-secret-2024"

# ── Jobs folder (persisted via Docker volume) ────────────────
JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

ADMIN_PASSWORD = "PEI2024"

CATEGORIES = ["Blueprints", "Packing Lists", "Fab Sheets"]
IMAGE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}

def safe_join(*parts):
    """Resolve a path and ensure it stays inside JOBS_DIR."""
    path = os.path.realpath(os.path.join(JOBS_DIR, *parts))
    if not path.startswith(os.path.realpath(JOBS_DIR)):
        abort(403)
    return path

# ── Landing page ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Existing tools ───────────────────────────────────────────
@app.route("/sheet_editor")
def sheet_editor():
    return render_template("sheet_editor.html")

@app.route("/sheet_extractor", methods=["GET", "POST"])
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

# ── Blueprint viewer (public) ────────────────────────────────
@app.route("/blueprints")
def blueprints():
    return render_template("blueprints.html")

@app.route("/field-compass")
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

@app.route("/files/<path:filepath>")
def serve_file(filepath):
    full = safe_join(filepath)
    directory = os.path.dirname(full)
    filename  = os.path.basename(full)
    return send_from_directory(directory, filename)

# ── Admin (password protected) ───────────────────────────────
@app.route("/admin", methods=["GET"])
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
def admin_create_job():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    job_name = (data or {}).get("name", "").strip()
    if not job_name or re.search(r'[\\/:*?"<>|]', job_name):
        return jsonify({"error": "Invalid job name"}), 400
    job_path = safe_join(job_name)
    for cat in CATEGORIES:
        os.makedirs(os.path.join(job_path, cat), exist_ok=True)
    return jsonify({"ok": True})

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    job      = request.form.get("job", "").strip()
    category = request.form.get("category", "").strip()
    if not job or category not in CATEGORIES:
        return jsonify({"error": "Invalid job or category"}), 400
    cat_path = safe_join(job, category)
    os.makedirs(cat_path, exist_ok=True)
    uploaded = []
    for f in request.files.getlist("files"):
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in IMAGE_EXTS:
            fname = re.sub(r'[\\/:*?"<>|]', "_", f.filename)
            f.save(os.path.join(cat_path, fname))
            uploaded.append(fname)
    return jsonify({"ok": True, "uploaded": uploaded})

@app.route("/admin/delete-file", methods=["POST"])
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
def admin_check_auth():
    return jsonify({"authenticated": bool(session.get("admin"))})

# ── Static files ─────────────────────────────────────────────
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), filename)

if __name__ == "__main__":
    app.run(debug=True)
