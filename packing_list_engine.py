"""
Packing List Engine -- PEItools.com
Parses KPS packing lists and annotates blueprint PDFs with delivery highlights.
"""
import re, json, os, subprocess, logging
import fitz
from PIL import Image

log = logging.getLogger(__name__)

# --- Packing List Parser ---------------------------------------------------

def parse_packing_list(pdf_path):
    """Parse KPS packing list (up to 4 skid blocks per page, 2x2 grid).
    Returns:
        results  : { "skid_num": ["panel1", ...], ... }
        warnings : list of strings for skids needing human review.
                   Warnings starting with SKIP: mean panels were excluded.
    """
    doc = fitz.open(pdf_path)
    results  = {}
    warnings = []

    for pg_idx in range(doc.page_count):
        page = doc[pg_idx]
        pix  = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        w, h = img.size

        quads = [("TL", (0,    0,    w//2, h//2)),
                 ("TR", (w//2, 0,    w,    h//2)),
                 ("BL", (0,    h//2, w//2, h   )),
                 ("BR", (w//2, h//2, w,    h   ))]

        for qname, crop in quads:
            tmp = f"/tmp/plq_{pg_idx}_{qname}.png"
            img.crop(crop).save(tmp)
            r = subprocess.run(
                ["tesseract", tmp, "stdout", "--psm", "6", "-l", "eng"],
                capture_output=True, text=True)
            text = r.stdout

            skid_m = re.search(r"SKID\s*[#*]?\s*(\d+)", text, re.I)
            if not skid_m:
                continue
            skid_num = skid_m.group(1)

            panels, warn = _parse_skid_block(text, skid_num)

            if warn:
                warnings.append(warn)
                if warn.startswith("SKIP:"):
                    log.warning("Skid #%s skipped: %s", skid_num, warn)
                    continue

            if panels:
                bucket = results.setdefault(skid_num, [])
                for p in panels:
                    if p not in bucket:
                        bucket.append(p)

    doc.close()
    return results, warnings


def _parse_skid_block(text, skid_num):
    """Parse one skid quadrant. Returns (panels, warning_or_None).
    Warnings starting with SKIP: mean the caller should not include panels."""
    # Fix OCR artifact: "2/7" -> "27" (order numbers through printed table lines)
    text = re.sub(r"(?<!\d)(\d)/(\d{1,2})(?!\d)", r"\1\2", text)

    # Explicit not-shipping check
    if re.search(r"\b(NOT\s*SHIP|NO\s*SHIP|DO\s*NOT\s*SHIP)\b", text, re.I):
        return [], f"SKIP:#{skid_num}: Not-shipping note detected -- skid excluded. Please verify."

    # Expected panel count from "X PANELS" footer
    count_m  = re.search(r"\b(\d+)\s+PANELS\b", text, re.I)
    expected = int(count_m.group(1)) if count_m else None

    panels = _extract_panels(text)

    warning = None
    if expected is None and re.search(r"\bPANELS\b", text, re.I):
        # PANELS keyword found but count unreadable -- heavy OCR corruption
        # Classic sign of handwriting overlaying the printed panel count
        warning = (
            f"SKIP:#{skid_num}: Panel count footer unreadable -- "
            f"possible handwriting or not-shipping note. "
            f"Extracted {len(panels)} tentative panels but excluded. "
            f"Please review this skid manually."
        )
    elif expected is not None and len(panels) < expected * 0.70:
        warning = (
            f"#{skid_num}: Only {len(panels)} of {expected} expected panels extracted -- "
            f"OCR may have missed some. Please verify."
        )

    return panels, warning


def _extract_panels(text):
    """Extract valid panel numbers from skid block OCR text.
    Panel numbers: 1-700, optional R suffix (remake).
    Leading order numbers (<=99) are detected and skipped.
    """
    skip = re.compile(
        r"\b(SKID|ORDER|PANEL|PANELS|HEIGHT|WIDTH|LENGTH|ACCESSORIES|DONE|CM|"
        r"PROJECT|PAGE|SHIP|TO|FROM|VIA|RE|Keith|Alex|Phone|Fax|Attn|"
        r"Enclosed|Total|Clips|Starter|Track|Spline|Thermal|Parapet|"
        r"Horizontal|Brakeshapes|Breakshapes|Alfrex|Champagne|Shop|Site|"
        r"Zone|Done)\b", re.I)

    panels = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or skip.search(line):
            continue
        nums = re.findall(r"\b(\d{1,3}R?)\b", line)
        if not nums:
            continue
        if len(nums) >= 2:
            try:
                first_val = int(re.match(r"(\d+)", nums[0]).group(1))
                rest_vals = [int(re.match(r"(\d+)", n).group(1)) for n in nums[1:]]
                if first_val <= 99 and any(v > 99 for v in rest_vals):
                    nums = nums[1:]
            except Exception:
                pass
        for n in nums:
            base = int(re.match(r"(\d+)", n).group(1))
            if 1 <= base <= 700:
                panels.append(n)
    return panels


# --- Blueprint Panel Scanner -----------------------------------------------

def scan_blueprint_panels(pdf_path, cache_path=None, progress_cb=None, dxf_dir=None):
    """Scan blueprint PDF for panel number positions using OCR.

    If dxf_dir is provided, loads all DXF files in that folder and builds a
    whitelist of valid panel numbers. OCR results are then filtered to only
    include numbers confirmed by the DXF — eliminating misreads and false
    positives while keeping exact PDF positions.

    Workflow: OCR finds position → DXF confirms it's a real panel number.
    """
    if cache_path and os.path.exists(cache_path):
        if os.path.getmtime(cache_path) > os.path.getmtime(pdf_path):
            with open(cache_path) as f:
                return json.load(f)

    # Build DXF whitelist if available
    dxf_valid = _load_dxf_panel_set(dxf_dir) if dxf_dir else None
    if dxf_valid:
        log.info("DXF whitelist loaded: %d valid panel numbers", len(dxf_valid))

    doc = fitz.open(pdf_path)
    panel_locations = {}
    scale = 300 / 72

    for pg_idx in range(doc.page_count):
        if progress_cb:
            progress_cb(pg_idx, doc.page_count)
        page  = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height

        first_line = page.get_text().split("\n")[0].strip()
        if re.match(r"^[Dd]\d+", first_line) or pg_idx < 3:
            continue

        words = _ocr_page_words(page, pg_idx, scale)

        for text, x0, y0, x1, y1 in words:
            t = text.strip(".,\'\"")
            if not re.match(r"^\d+[A-Z]?$", t):
                continue
            val = int(re.match(r"(\d+)", t).group(1))
            if not (1 <= val <= 700):
                continue

            # DXF confirmation: if we have a whitelist, only accept known panels
            if dxf_valid and t not in dxf_valid:
                continue

            h = y1 - y0
            if h < 4 or h >= 9:
                continue
            if x0 > pw * 0.82:
                continue
            if y0 < ph * 0.08:
                continue
            if x0 < pw * 0.02:
                continue
            if t not in panel_locations:
                panel_locations[t] = {"page": pg_idx, "bbox": [x0, y0, x1, y1]}

    doc.close()

    # Without DXF: remove isolated single-digit noise
    if not dxf_valid:
        to_remove = [p for p, loc in panel_locations.items()
                     if int(re.match(r"(\d+)", p).group(1)) <= 9
                     and not _has_panel_neighbors(p, loc["bbox"], loc["page"], panel_locations)]
        for p in to_remove:
            del panel_locations[p]

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(panel_locations, f)

    return panel_locations


def _load_dxf_panel_set(dxf_dir):
    """Read all DXF files in dxf_dir and return a set of valid panel number strings."""
    try:
        import ezdxf
    except ImportError:
        log.warning("ezdxf not installed — DXF validation skipped")
        return None

    valid = set()
    for fname in os.listdir(dxf_dir):
        if not fname.lower().endswith(".dxf"):
            continue
        try:
            doc = ezdxf.readfile(os.path.join(dxf_dir, fname))
            # Search paper space blocks and model space for PANELS layer text
            for block in doc.blocks:
                for e in block:
                    if not (hasattr(e.dxf, "layer") and e.dxf.layer.upper() == "PANELS"):
                        continue
                    txt = ""
                    if e.dxftype() == "TEXT":
                        txt = e.dxf.text.strip()
                    elif e.dxftype() == "MTEXT":
                        import re as _re
                        txt = _re.sub(r"\\[^;]+;|\{[^}]*\}", "", e.text).strip()
                    if not txt:
                        continue
                    if re.match(r"^\d+[A-Z]?$", txt):
                        val = int(re.match(r"(\d+)", txt).group(1))
                        if 1 <= val <= 700:
                            valid.add(txt)
        except Exception as ex:
            log.warning("DXF read error %s: %s", fname, ex)

    return valid if valid else None


def _has_panel_neighbors(panel_str, bbox, page_idx, all_locs, radius=200):
    x0, y0 = bbox[0], bbox[1]
    for other, loc in all_locs.items():
        if other == panel_str or loc["page"] != page_idx:
            continue
        if abs(loc["bbox"][1] - y0) < 15 and abs(loc["bbox"][0] - x0) < radius:
            return True
    return False


def _ocr_page_words(page, pg_idx, scale=300/72):
    import xml.etree.ElementTree as ET
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    tmp = f"/tmp/bpscan_{pg_idx}.png"
    pix.save(tmp)
    subprocess.run(
        ["tesseract", tmp, f"/tmp/bphocr_{pg_idx}", "--psm", "12", "-l", "eng", "hocr"],
        capture_output=True)
    words = []
    try:
        tree = ET.parse(f"/tmp/bphocr_{pg_idx}.hocr")
        for word in tree.iter():
            if word.get("class") != "ocrx_word":
                continue
            title = word.get("title", "")
            bm = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
            if not bm:
                continue
            conf_m = re.search(r"x_wconf (\d+)", title)
            if conf_m and int(conf_m.group(1)) < 75:
                continue
            px0, py0, px1, py1 = [int(v) for v in bm.groups()]
            t = "".join(word.itertext()).strip()
            if t:
                words.append((t, px0/scale, py0/scale, px1/scale, py1/scale))
    except Exception:
        pass
    return words


# --- Blueprint Annotator ---------------------------------------------------

_SHIPMENT_COLORS = [
    ((0.1, 0.95, 0.25), (0.0, 0.55, 0.1)),
    ((1.0, 0.92, 0.0),  (0.75, 0.60, 0.0)),
    ((0.0, 0.78, 1.0),  (0.0, 0.45, 0.80)),
    ((1.0, 0.55, 0.0),  (0.80, 0.30, 0.0)),
    ((0.85, 0.0, 0.85), (0.55, 0.0, 0.55)),
    ((0.0, 0.92, 0.85), (0.0, 0.55, 0.50)),
    ((0.75, 0.25, 1.0), (0.50, 0.0, 0.80)),
    ((1.0, 0.35, 0.35), (0.75, 0.0, 0.0)),
]

def _shipment_color(shipment_index):
    return _SHIPMENT_COLORS[shipment_index % len(_SHIPMENT_COLORS)]


def generate_tracked_blueprint(blueprint_path, delivery_state, panel_locations, output_path):
    doc = fitz.open(blueprint_path)

    shipment_order = {}
    for info in delivery_state.values():
        s = info.get("shipment", "")
        if s not in shipment_order:
            shipment_order[s] = len(shipment_order)

    page_panels = {}
    for panel_str, info in delivery_state.items():
        if panel_str not in panel_locations:
            continue
        loc = panel_locations[panel_str]
        pg  = loc["page"]
        page_panels.setdefault(pg, []).append(
            (panel_str, info["skid"], info.get("shipment", ""), loc["bbox"]))

    for pg_idx, panels in page_panels.items():
        if pg_idx >= doc.page_count:
            continue
        page   = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height
        for panel_str, skid_num, shipment, bbox in panels:
            x0, y0, x1, y1 = bbox
            pad = 3
            fill_c, stroke_c = _shipment_color(shipment_order.get(shipment, 0))
            page.draw_rect(fitz.Rect(x0-pad, y0-pad, x1+pad, y1+pad),
                           color=stroke_c, fill=fill_c, fill_opacity=0.50, width=0.8)
        _insert_delivery_table(page, panels, pw, ph, shipment_order)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()


def _insert_delivery_table(page, panels, pw, ph, shipment_order):
    if not panels:
        return

    panels_sorted = sorted(panels, key=lambda x: _sort_key(x[0]))

    FONT_SIZE = 10; HDR_SIZE = 8.5; CHAR_W = 6.0; PAD = 8
    ROW_H = 14; BANNER_H = 26; SUBHDR_H = 14; DIVIDER = 6
    SWATCH_W = 6; MAX_HEIGHT = ph * 0.74; MARGIN = 4

    max_p  = max(max(len(s[0]) for s in panels_sorted), len("PANEL"))
    max_s  = max(max(len(s[1]) for s in panels_sorted), len("SKID"))
    col_p  = int(max_p * CHAR_W) + PAD * 2
    col_s  = int(max_s * CHAR_W) + PAD * 2
    unit_w = SWATCH_W + col_p + col_s

    page_shipments = list(dict.fromkeys(p[2] for p in panels_sorted))
    LEGEND_ROW_H = 12
    legend_h = len(page_shipments) * LEGEND_ROW_H + 4

    avail_rows   = max(1, int((MAX_HEIGHT - BANNER_H - SUBHDR_H - legend_h) / ROW_H))
    n            = len(panels_sorted)
    n_data_cols  = 2 if n > avail_rows else 1
    rows_per_col = (n + 1) // 2 if n_data_cols == 2 else n

    BANNER_TITLE = "DELIVERED"
    min_tbl_w    = int(len(BANNER_TITLE) * 7.0) + PAD * 2
    tbl_w = max(unit_w * n_data_cols + (DIVIDER if n_data_cols == 2 else 0), min_tbl_w)
    tbl_h = BANNER_H + SUBHDR_H + rows_per_col * ROW_H + legend_h + 4

    rx1 = pw - MARGIN; rx0 = rx1 - tbl_w
    ry0 = MARGIN;      ry1 = ry0 + tbl_h

    page.draw_rect(fitz.Rect(rx0, ry0, rx1, ry1), color=(0,0,0), fill=(1,1,1), width=1.0)
    page.draw_rect(fitz.Rect(rx0, ry0, rx1, ry0+BANNER_H),
                   color=(0,0,0), fill=(0.08,0.08,0.12), width=0)
    page.insert_text((rx0+PAD, ry0+BANNER_H-8), BANNER_TITLE,
                     fontsize=11, color=(1,1,1), fontname="Helvetica-Bold")

    shy = ry0 + BANNER_H
    for dc in range(n_data_cols):
        ox = rx0 + dc * (unit_w + DIVIDER)
        page.draw_rect(fitz.Rect(ox, shy, ox+unit_w, shy+SUBHDR_H),
                       color=(0.5,0.5,0.5), fill=(0.88,0.88,0.92), width=0.3)
        page.insert_text((ox+SWATCH_W+PAD, shy+SUBHDR_H-4), "PANEL",
                         fontsize=HDR_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.insert_text((ox+SWATCH_W+col_p+PAD, shy+SUBHDR_H-4), "SKID",
                         fontsize=HDR_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.draw_line((ox+SWATCH_W+col_p, shy), (ox+SWATCH_W+col_p, ry1-legend_h-2),
                       color=(0.65,0.65,0.65), width=0.3)

    for i, (panel_str, skid_num, shipment, _) in enumerate(panels_sorted):
        dc  = i // rows_per_col
        row = i  % rows_per_col
        ox  = rx0 + dc * (unit_w + DIVIDER)
        ry  = shy + SUBHDR_H + row * ROW_H
        fill_c, stroke_c = _shipment_color(shipment_order.get(shipment, 0))
        tint = tuple(min(1.0, 0.55+0.45*c) for c in fill_c)
        page.draw_rect(fitz.Rect(ox, ry, ox+unit_w, ry+ROW_H),
                       color=(0.78,0.78,0.78), fill=tint, width=0.2)
        page.draw_rect(fitz.Rect(ox, ry, ox+SWATCH_W, ry+ROW_H),
                       color=stroke_c, fill=fill_c, width=0)
        page.insert_text((ox+SWATCH_W+PAD, ry+ROW_H-4), panel_str,
                         fontsize=FONT_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.insert_text((ox+SWATCH_W+col_p+PAD, ry+ROW_H-4), skid_num,
                         fontsize=FONT_SIZE, color=(0,0,0), fontname="Helvetica")

    legend_y = ry1 - legend_h
    page.draw_line((rx0, legend_y), (rx1, legend_y), color=(0.7,0.7,0.7), width=0.5)
    for j, ship in enumerate(page_shipments):
        ly  = legend_y + 2 + j * LEGEND_ROW_H
        idx = shipment_order.get(ship, 0)
        fill_c, stroke_c = _shipment_color(idx)
        page.draw_rect(fitz.Rect(rx0+PAD, ly+2, rx0+PAD+10, ly+LEGEND_ROW_H-2),
                       color=stroke_c, fill=fill_c, width=0)
        label = ship if len(ship) <= 30 else ship[:30] + "..."
        page.insert_text((rx0+PAD+14, ly+LEGEND_ROW_H-3), label,
                         fontsize=7, color=(0.1,0.1,0.1), fontname="Helvetica")

    page.draw_rect(fitz.Rect(rx0, ry0, rx1, ry1), color=(0,0,0), fill=None, width=1.2)


def _sort_key(panel_str):
    m = re.match(r"(\d+)", panel_str)
    return int(m.group(1)) if m else 0
hy, ox+unit_w, shy+SUBHDR_H),
                       color=(0.5,0.5,0.5), fill=(0.88,0.88,0.92), width=0.3)
        page.insert_text((ox+SWATCH_W+PAD, shy+SUBHDR_H-4), "PANEL",
                         fontsize=HDR_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.insert_text((ox+SWATCH_W+col_p+PAD, shy+SUBHDR_H-4), "SKID",
                         fontsize=HDR_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.draw_line((ox+SWATCH_W+col_p, shy), (ox+SWATCH_W+col_p, ry1-legend_h-2),
                       color=(0.65,0.65,0.65), width=0.3)

    for i, (panel_str, skid_num, shipment, _) in enumerate(panels_sorted):
        dc  = i // rows_per_col
        row = i  % rows_per_col
        ox  = rx0 + dc * (unit_w + DIVIDER)
        ry  = shy + SUBHDR_H + row * ROW_H
        fill_c, stroke_c = _shipment_color(shipment_order.get(shipment, 0))
        tint = tuple(min(1.0, 0.55+0.45*c) for c in fill_c)
        page.draw_rect(fitz.Rect(ox, ry, ox+unit_w, ry+ROW_H),
                       color=(0.78,0.78,0.78), fill=tint, width=0.2)
        page.draw_rect(fitz.Rect(ox, ry, ox+SWATCH_W, ry+ROW_H),
                       color=stroke_c, fill=fill_c, width=0)
        page.insert_text((ox+SWATCH_W+PAD, ry+ROW_H-4), panel_str,
                         fontsize=FONT_SIZE, color=(0,0,0), fontname="Helvetica-Bold")
        page.insert_text((ox+SWATCH_W+col_p+PAD, ry+ROW_H-4), skid_num,
                         fontsize=FONT_SIZE, color=(0,0,0), fontname="Helvetica")

    legend_y = ry1 - legend_h
    page.draw_line((rx0, legend_y), (rx1, legend_y), color=(0.7,0.7,0.7), width=0.5)
    for j, ship in enumerate(page_shipments):
        ly  = legend_y + 2 + j * LEGEND_ROW_H
        idx = shipment_order.get(ship, 0)
        fill_c, stroke_c = _shipment_color(idx)
        page.draw_rect(fitz.Rect(rx0+PAD, ly+2, rx0+PAD+10, ly+LEGEND_ROW_H-2),
                       color=stroke_c, fill=fill_c, width=0)
        label = ship if len(ship) <= 30 else ship[:30] + "..."
        page.insert_text((rx0+PAD+14, ly+LEGEND_ROW_H-3), label,
                         fontsize=7, color=(0.1,0.1,0.1), fontname="Helvetica")

    page.draw_rect(fitz.Rect(rx0, ry0, rx1, ry1), color=(0,0,0), fill=None, width=1.2)


def _sort_key(panel_str):
    m = re.match(r"(\d+)", panel_str)
    return int(m.group(1)) if m else 0
