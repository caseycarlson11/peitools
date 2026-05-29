from flask import Flask, send_from_directory, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

# ── Tool routes ─────────────────────────────────────────────
# Replace the placeholder returns below with your actual tool
# app logic (or import and call functions from your tool files).

@app.route("/sheet_editor")
def sheet_editor():
    return render_template("sheet_editor.html")

@app.route("/sheet_extractor", methods=["GET", "POST"])
def sheet_extractor():
    if request.method == "GET":
        return render_template("panel_sheet_mapper.html")

    # POST: process uploaded DXF files
    files = request.files.getlist("files")
    if not files:
        return "No files uploaded", 400

    mapping = {}

    for f in files:
        fname = f.filename
        lines = [l.decode("utf-8", errors="ignore").strip() for l in f.read().splitlines()]

        # Build layout -> block name mapping
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

        # Extract panel TEXT entities by block
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

    # Sort sheets numerically within each panel
    def sort_sheets(sheets):
        def key(s):
            try: return [float(p) for p in s.split(".")]
            except: return [999]
        return sorted(sheets, key=key)

    for p in mapping:
        mapping[p]["sheets"] = sort_sheets(mapping[p]["sheets"])

    # Convert keys to strings for JSON
    str_mapping = {str(k): v for k, v in sorted(mapping.items())}

    return jsonify({"mapping": str_mapping, "job_name": "", "count": len(str_mapping)})

# ────────────────────────────────────────────────────────────

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), filename)

if __name__ == "__main__":
    app.run(debug=True)
