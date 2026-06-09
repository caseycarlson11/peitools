"""
Packing List Engine -- PEItools.com
Parses KPS packing lists and annotates blueprint PDFs with delivery highlights.
"""
import re, json, os, subprocess, logging
import fitz
from PIL import Image

log = logging.getLogger(__name__)

# ── Panel conventions (shared, project-agnostic) ────────────────────────────
# KPS panel numbers: 1–3 digits with an optional letter suffix (e.g. 242R =
# remake). Every Pacific Erectors job uses the same KPS DXF conventions, so the
# DXF locator works for any project — but anything project-specific is kept here
# as a single tuning point for the future.
PANEL_RE     = re.compile(r"^\d{1,3}[A-Za-z]?$")
PANEL_MIN    = 1
PANEL_MAX    = 700
PANELS_LAYER = "PANELS"          # DXF layer that holds panel-number text

# DXF→PDF registration tuning (page-agnostic, units = PDF points)
REG_MIN_ANCHORS   = 4            # distinct matched panel numbers to trust a page
REG_MIN_SPREAD_PT = 80           # inliers must span this in BOTH axes (kills number columns)
REG_MAX_RESID_PT  = 5.0          # max median anchor residual for an accepted transform

def _is_panel(txt):
    """True if txt is a valid panel number (shared by every step of the engine)."""
    if not txt or not PANEL_RE.match(txt):
        return False
    return PANEL_MIN <= int(re.match(r"(\d+)", txt).group(1)) <= PANEL_MAX

# --- Packing List Parser ---------------------------------------------------

def parse_packing_list(pdf_path):
    """Parse KPS packing list (up to 4 skid blocks per page, 2x2 grid).

    Hybrid approach:
    - Crops each quadrant and runs psm-6 plain-text OCR to reliably detect the
      SKID number, expected panel count, and handwriting/not-shipping flags —
      the same signals the old parser used, which work well on cropped images.
    - Then runs hOCR on the same cropped image to get word positions.  Finds
      the PANEL # column header and extracts only numbers that sit inside the
      panel column — eliminating false order-number drops for small panels like
      1, 3, 60 that are ≤99 and were missed by the old text heuristic.

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
        # Cap at 2400px on the long side — prevents Tesseract from hanging on
        # high-res scans (e.g. iPad photos saved as PDF).
        MAX_DIM = 2400
        if img.width > MAX_DIM or img.height > MAX_DIM:
            scale = MAX_DIM / max(img.width, img.height)
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        w, h = img.size

        quads = [("TL", (0,    0,    w//2, h//2)),
                 ("TR", (w//2, 0,    w,    h//2)),
                 ("BL", (0,    h//2, w//2, h   )),
                 ("BR", (w//2, h//2, w,    h   ))]

        for qname, crop in quads:
            tmp = f"/tmp/plq_{pg_idx}_{qname}.png"
            img.crop(crop).save(tmp)

            # ── Step 1: plain-text OCR for SKID, count, and not-shipping ──────
            try:
                r = subprocess.run(
                    ["tesseract", tmp, "stdout", "--psm", "6", "-l", "eng"],
                    capture_output=True, text=True, timeout=60)
                text = r.stdout
            except subprocess.TimeoutExpired:
                logging.warning(f"Tesseract timed out on {tmp} — skipping quadrant")
                continue
            # Fix OCR artifact: "2/7" → "27"
            text = re.sub(r"(?<!\d)(\d)/(\d{1,2})(?!\d)", r"\1\2", text)

            skid_m = re.search(r"SKID\s*[#*]?\s*(\d+)", text, re.I)
            if not skid_m:
                continue
            skid_num = skid_m.group(1)

            # Not-shipping check from plain text
            if re.search(r"\b(NOT\s*SHIP|NO\s*SHIP|DO\s*NOT\s*SHIP)\b", text, re.I):
                warnings.append(f"SKIP:#{skid_num}: Not-shipping note detected — skid excluded.")
                continue

            # Expected count and garbled-footer check from plain text
            count_m  = re.search(r"\b(\d+)\s+PANELS\b", text, re.I)
            expected = int(count_m.group(1)) if count_m else None
            panels_kw_present = bool(re.search(r"\bPANELS\b", text, re.I))

            if expected is None and panels_kw_present:
                # Footer garbled (handwriting) — exclude and flag
                warnings.append(
                    f"SKIP:#{skid_num}: Panel count footer unreadable — "
                    f"possible handwriting or not-shipping note. "
                    f"Please review this skid manually."
                )
                continue

            # ── Step 2: hOCR for word positions within this quadrant ──────────
            # Returns {panel_str: order_num_str}
            panel_orders = _extract_panels_positional(tmp, skid_num)

            # Fall back to text heuristic if positional extraction found nothing
            if not panel_orders:
                panel_orders = {p: "" for p in _extract_panels(text)}

            # ── Step 3: validate ──────────────────────────────────────────────
            if expected is not None and len(panel_orders) < expected * 0.70:
                warnings.append(
                    f"#{skid_num}: Only {len(panel_orders)} of {expected} expected panels "
                    f"extracted — OCR may have missed some. Please verify."
                )

            if panel_orders:
                bucket = results.setdefault(skid_num, {})
                for p, order_num in panel_orders.items():
                    if p not in bucket:
                        bucket[p] = order_num

    doc.close()
    return results, warnings


def _extract_panels_positional(img_path, skid_num):
    """Run hOCR on a quadrant image and extract panel numbers from the PANEL #
    column only, using word x-positions to separate them from ORDER # numbers.
    Returns a list of panel strings, or [] if the PANEL # header isn't found.
    """
    import xml.etree.ElementTree as ET
    base = img_path.replace(".png", "_hocr")
    try:
        subprocess.run(
            ["tesseract", img_path, base, "--psm", "6", "-l", "eng", "hocr"],
            capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        logging.warning(f"Tesseract hOCR timed out on {img_path}")
        return {}
    try:
        tree = ET.parse(base + ".hocr")
    except Exception:
        return []
    finally:
        try: os.unlink(base + ".hocr")
        except Exception: pass

    # Collect all words with bounding boxes
    words = []
    for word in tree.iter():
        if word.get("class") != "ocrx_word":
            continue
        bm = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", word.get("title", ""))
        if not bm:
            continue
        t  = "".join(word.itertext()).strip()
        x0, y0, x1, y1 = [int(v) for v in bm.groups()]
        words.append((t, x0, y0, x1, y1))

    if not words:
        return []

    img_w = max(x1 for _, _, _, x1, _ in words) if words else 1000

    # Find "PANEL #" header → gives us the left edge of the panel column
    panel_hx = panel_hy = None
    for t, x0, y0, x1, y1 in words:
        if re.match(r"PANEL", t, re.I):
            panel_hx, panel_hy = x0, y0
            break

    if panel_hx is None:
        return []   # can't locate column — caller will fall back

    # Find "X PANELS" footer → gives the bottom boundary
    footer_y = None
    for i, (t, x0, y0, x1, y1) in enumerate(words):
        if re.search(r"\bPANELS\b", t, re.I) and y0 > panel_hy:
            footer_y = y0
            break
    y_bot = footer_y if footer_y else img_w * 2   # generous fallback

    # Collect ORDER # column words for matching to panel rows by y-position
    order_words = []  # (order_num_str, y_center)
    for t, x0, y0, x1, y1 in words:
        tt = t.strip(".,:'\"")
        if (re.fullmatch(r'\d{1,2}', tt) and int(tt) <= 99 and
                x0 < panel_hx - 15 and panel_hy < y0 < y_bot):
            order_words.append((tt, (y0 + y1) / 2))

    # Column region: x >= panel_hx - small_margin, y between header and footer
    # Returns dict {panel_str: order_num_str} instead of plain list
    #
    # ORDER# matching uses "nearest preceding" logic: for each panel, find the
    # ORDER# word with the HIGHEST y that is still at-or-above the panel (y ≤
    # panel_cy + 20px OCR tolerance).  This correctly handles multi-line panel
    # groups — the ORDER# appears once on the first line; continuation lines
    # have no ORDER# at all, so they keep inheriting the same preceding number
    # no matter how far below they fall.
    order_words_sorted_desc = sorted(order_words, key=lambda x: x[1], reverse=True)

    panel_orders = {}
    for t, x0, y0, x1, y1 in words:
        tt = t.strip(".,:'\"")
        if not _is_panel(tt):
            continue
        if x0 < panel_hx - 15:
            continue    # left of panel column = order number territory
        if not (panel_hy < y0 < y_bot):
            continue
        if tt not in panel_orders:
            panel_cy = (y0 + y1) / 2
            assigned = ""
            # Walk from bottom to top; first match is the nearest preceding ORDER#
            for onum, oy in order_words_sorted_desc:
                if oy <= panel_cy + 20:   # at or just below panel (20px OCR tolerance)
                    assigned = onum
                    break
            if not assigned and order_words:
                # Panel is above all order words — fall back to nearest by distance
                assigned = min(order_words, key=lambda x: abs(x[1] - panel_cy))[0]
            panel_orders[tt] = assigned

    return panel_orders


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


# --- Packing List Position Scanner -----------------------------------------

def scan_packing_list_positions(pdf_path, cache_path=None, progress_cb=None):
    """OCR a packing list PDF for the positions of panel-like numbers.

    Used by the Packing List Editor so a panel selected on the blueprint can be
    cross-highlighted on the packing list. Returns:

        {
          "pages":     [{"width": <pt>, "height": <pt>}, ...],
          "positions": [{"panel": "42", "page": 0, "bbox": [x0,y0,x1,y1]}, ...]
        }

    bbox is in PDF points (72dpi space), top-left origin — same convention as
    panel_locations from scan_blueprint_panels, so the browser maps both the
    same way.
    """
    if cache_path and os.path.exists(cache_path):
        try:
            if os.path.getmtime(cache_path) > os.path.getmtime(pdf_path):
                with open(cache_path) as f:
                    return json.load(f)
        except Exception:
            pass

    doc = fitz.open(pdf_path)
    scale = 300 / 72
    pages = []
    positions = []

    for pg_idx in range(doc.page_count):
        if progress_cb:
            progress_cb(pg_idx, doc.page_count)
        page = doc[pg_idx]
        W, H = page.rect.width, page.rect.height
        pages.append({"width": W, "height": H})

        words = list(_ocr_page_words(page, f"pl{pg_idx}", scale))

        # A skid sheet has up to 4 skid blocks (2x2). Panels live ONLY in each
        # block's "PANEL #" column (the red box) — never in the ORDER # column,
        # the SKID # / HEIGHT / WIDTH / LENGTH fields, or the "N PANELS" footer.
        # Find the PANEL # headers and PANELS footers, then read numbers only
        # inside each PANEL # column region.
        panel_headers = []   # (hy, hx)
        footers       = []   # (fy, fx0)
        for t, x0, y0, x1, y1 in words:
            tu = t.upper().strip(" #:.")
            if tu == "PANEL":
                panel_headers.append((y0, x0))
            elif tu.startswith("PANELS"):
                footers.append((y0, x0))

        # One region per PANEL # header: spans from just below the header to its
        # footer (or the next header / a bounded fallback), within its page half.
        regions = []  # (hx, y_top, y_bot, x_max)
        for left in (True, False):
            hs = sorted([(hy, hx) for (hy, hx) in panel_headers if (hx < W / 2) == left])
            fs = sorted([fy for (fy, fx0) in footers if (fx0 < W / 2) == left])
            for i, (hy, hx) in enumerate(hs):
                next_hy = hs[i + 1][0] if i + 1 < len(hs) else H
                fbot = next((fy for fy in fs if hy < fy < next_hy), None)
                y_bot = fbot if fbot is not None else min(hy + H * 0.40, next_hy - 5)
                x_max = W * 0.49 if left else W * 0.99
                regions.append((hx, hy, y_bot, x_max))

        seen = set()  # de-dupe identical panel strings at near-identical spots
        for t, x0, y0, x1, y1 in words:
            tt = t.strip(".,:'\"")
            if not re.match(r"^\d{1,3}R?$", tt):
                continue
            val = int(re.match(r"(\d+)", tt).group(1))
            if not (1 <= val <= 700):
                continue
            # Must sit inside a PANEL # column region (excludes ORDER #, SKID #,
            # dimensions and the footer count by construction).
            in_col = any(hx - 14 <= x0 <= x_max and hy < y0 < y_bot
                         for (hx, hy, y_bot, x_max) in regions)
            if not in_col:
                continue
            key = (tt, round(x0 / 6), round(y0 / 6))
            if key in seen:
                continue
            seen.add(key)
            positions.append({"panel": tt, "page": pg_idx,
                              "bbox": [x0, y0, x1, y1]})

    doc.close()

    result = {"pages": pages, "positions": positions}
    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(result, f)
        except Exception:
            pass
    return result


# --- Blueprint Panel Scanner -----------------------------------------------

def scan_blueprint_panels(pdf_path, cache_path=None, progress_cb=None, dxf_dir=None):
    """Locate panel numbers on the blueprint PDF.

    Primary method (when DXF files are present): the DXF paper-space layouts hold
    every panel number with an exact coordinate. For each PDF page we OCR a few
    panel numbers as ANCHORS, match the page to its DXF layout, solve the
    DXF->PDF affine transform from those anchors, then place ALL of that layout's
    panels by transforming their DXF coordinates. This finds far more panels than
    OCR alone (OCR can only read a fraction of the small numbers on a dense sheet).

    Panels are placed ONLY through a validated transform — raw OCR hits are never
    placed when DXF is present, so note numbers, dimensions and grid bubbles that
    merely look like panel numbers are not highlighted. With no DXF at all, falls
    back to the classic OCR-only scan.

    Project-agnostic: works for any job whose DXF follows the KPS conventions
    (panel-number text on the PANELS layer, one paper-space layout per sheet).
    Tunables live in the constants near the top of this module.
    """
    if cache_path and os.path.exists(cache_path):
        if os.path.getmtime(cache_path) > os.path.getmtime(pdf_path):
            with open(cache_path) as f:
                return json.load(f)

    layout_maps = _load_dxf_layout_panels(dxf_dir) if dxf_dir else None
    if layout_maps:
        dxf_valid = set()
        for m in layout_maps.values():
            dxf_valid |= set(m.keys())
        log.info("DXF layouts: %d, unique panel numbers: %d", len(layout_maps), len(dxf_valid))
    else:
        dxf_valid = _load_dxf_panel_set(dxf_dir) if dxf_dir else None

    doc = fitz.open(pdf_path)
    panel_locations = {}
    scale = 300 / 72

    for pg_idx in range(doc.page_count):
        if progress_cb:
            progress_cb(pg_idx, doc.page_count)
        page  = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height

        # Lower OCR confidence when we have DXF layouts: the whitelist + RANSAC
        # reject misreads, so more candidate anchors is strictly better.
        words = _ocr_page_words(page, pg_idx, scale, min_conf=(45 if layout_maps else 75))
        hits = []
        for text, x0, y0, x1, y1 in words:
            t = text.strip(".,\'\"")
            if not re.match(r"^\d+[A-Z]?$", t):
                continue
            val = int(re.match(r"(\d+)", t).group(1))
            if 1 <= val <= 700:
                hits.append((t, x0, y0, x1, y1))

        placed = {}   # panel -> bbox on this page

        # 1) DXF registration ------------------------------------------------
        if layout_maps:
            anchors = [(t, (x0+x1)/2, (y0+y1)/2)
                       for (t, x0, y0, x1, y1) in hits if t in dxf_valid]
            reg = _register_page_to_layout(anchors, layout_maps)
            if reg:
                aff, lm = reg
                a, b, c, d, e, f = aff
                for panel, (dx, dy, dh, dw) in lm.items():
                    # transform the text's 4 corners (handles sheet rotation/flip)
                    xs, ys = [], []
                    for gx, gy in ((dx, dy), (dx+dw, dy), (dx, dy+dh), (dx+dw, dy+dh)):
                        xs.append(a*gx + b*gy + c)
                        ys.append(d*gx + e*gy + f)
                    cx = (min(xs) + max(xs)) / 2.0
                    cy = (min(ys) + max(ys)) / 2.0
                    if not (-10 <= cx <= pw+10 and -10 <= cy <= ph+10):
                        continue
                    # cap to a sane highlight size regardless of DXF text height
                    bw = min(max(max(xs)-min(xs), 7.0), 26.0)
                    bh = min(max(max(ys)-min(ys), 6.0), 16.0)
                    placed[panel] = [cx-bw/2, cy-bh/2, cx+bw/2, cy+bh/2]

        # 2) No DXF at all -> classic OCR-only placement (whitelist + filters).
        #    NOTE: when DXF layouts exist we deliberately do NOT place raw OCR
        #    hits — doing so highlighted note numbers, dimensions and grid
        #    bubbles that merely look like panel numbers. With DXF present,
        #    panels come ONLY from the validated coordinate transform above.
        if not layout_maps:
            for t, x0, y0, x1, y1 in hits:
                if dxf_valid and t not in dxf_valid:
                    continue
                h = y1 - y0
                if h < 4 or h >= 9:
                    continue
                if x0 > pw*0.82 or y0 < ph*0.08 or x0 < pw*0.02:
                    continue
                placed[t] = [x0, y0, x1, y1]

        for panel, bbox in placed.items():
            if panel not in panel_locations:
                panel_locations[panel] = {"page": pg_idx, "bbox": bbox}

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


# --- DXF coordinate registration (DXF panel positions -> PDF page) ----------

def _load_dxf_layout_panels(dxf_dir):
    """Return {(file, layout_name): {panel: (x, y, height, width_est)}} from the
    paper-space PANELS-layer text of every DXF. Paper-space coords are the sheet
    coordinates, so each layout maps to a PDF page by an affine transform."""
    try:
        import ezdxf
    except ImportError:
        log.warning("ezdxf not installed — DXF positioning skipped")
        return None

    out = {}
    for fname in os.listdir(dxf_dir):
        if not fname.lower().endswith(".dxf"):
            continue
        try:
            doc = ezdxf.readfile(os.path.join(dxf_dir, fname))
        except Exception as ex:
            log.warning("DXF read error %s: %s", fname, ex)
            continue
        for layout in doc.layouts:
            if layout.name.lower() == "model":
                continue
            d = {}
            for e in layout:
                if e.dxftype() not in ("TEXT", "MTEXT"):
                    continue
                if getattr(e.dxf, "layer", "").upper() != PANELS_LAYER:
                    continue
                if e.dxftype() == "TEXT":
                    txt = e.dxf.text.strip()
                    h = float(getattr(e.dxf, "height", 1.0) or 1.0)
                else:
                    txt = re.sub(r"\\[^;]+;|\{|\}", "", e.text).strip()
                    h = float(getattr(e.dxf, "char_height", 1.0) or 1.0)
                if not _is_panel(txt):
                    continue
                try:
                    p = e.dxf.insert
                    d.setdefault(txt, (float(p.x), float(p.y), h, len(txt)*h*0.7))
                except Exception:
                    continue
            if d:
                out[(fname, layout.name)] = d
    return out or None


def _solve3(A, bvec):
    """Solve a 3x3 linear system by Gaussian elimination. Returns None if singular."""
    M = [row[:] + [bvec[i]] for i, row in enumerate(A)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        M[col] = [v / pv for v in M[col]]
        for r in range(3):
            if r != col and abs(M[r][col]) > 1e-12:
                fac = M[r][col]
                M[r] = [a - fac*b for a, b in zip(M[r], M[col])]
    return [M[0][3], M[1][3], M[2][3]]


def _affine_fit(src, dst):
    """Least-squares 2D affine mapping src(x,y) -> dst(u,v).
    Returns (a,b,c,d,e,f): u=a*x+b*y+c, v=d*x+e*y+f. None if degenerate."""
    Sxx = Sxy = Sx = Syy = Sy = Sn = 0.0
    Sxu = Syu = Su = Sxv = Syv = Sv = 0.0
    for (x, y), (u, v) in zip(src, dst):
        Sxx += x*x; Sxy += x*y; Sx += x; Syy += y*y; Sy += y; Sn += 1
        Sxu += x*u; Syu += y*u; Su += u
        Sxv += x*v; Syv += y*v; Sv += v
    N = [[Sxx, Sxy, Sx], [Sxy, Syy, Sy], [Sx, Sy, Sn]]
    p = _solve3(N, [Sxu, Syu, Su])
    q = _solve3(N, [Sxv, Syv, Sv])
    if p is None or q is None:
        return None
    return (p[0], p[1], p[2], q[0], q[1], q[2])


def _affine_apply(aff, x, y):
    a, b, c, d, e, f = aff
    return (a*x + b*y + c, d*x + e*y + f)


def _ransac_affine(corr, iters=150, tol=18.0):
    """corr = [((dxf_x,dxf_y),(pdf_x,pdf_y)), ...]. Returns (aff, inliers) or None."""
    import random
    n = len(corr)
    if n < 3:
        return None
    best = None
    rng = random.Random(12345)
    for _ in range(iters):
        s = rng.sample(corr, 3)
        aff = _affine_fit([c[0] for c in s], [c[1] for c in s])
        if not aff:
            continue
        inl = []
        for c in corr:
            u, v = _affine_apply(aff, *c[0])
            if ((u-c[1][0])**2 + (v-c[1][1])**2) ** 0.5 < tol:
                inl.append(c)
        if best is None or len(inl) > len(best[1]):
            best = (aff, inl)
            if len(inl) == n:
                break
    if not best or len(best[1]) < REG_MIN_ANCHORS:
        return None
    refit = _affine_fit([c[0] for c in best[1]], [c[1] for c in best[1]])
    return (refit or best[0], best[1])


def _register_page_to_layout(anchors, layout_maps):
    """anchors = [(panel, pdf_cx, pdf_cy)]. Find the best-matching DXF layout and
    solve the DXF->PDF transform. Returns (aff, layout_panel_map) or None.

    Strict acceptance so non-panel pages (notes, schedules, grid/dimension
    numbers that merely look like panels) never register and place panels:
      - need >= REG_MIN_ANCHORS distinct matched anchors and inliers
      - inliers must span a 2D region (rejects a collinear column/row of numbers)
      - low median residual (random numbers won't fit a real layout's geometry)
      - transform must be a non-degenerate 2D mapping
    The DXF→PDF transform is a general affine (sheets may be plotted with
    different x/y scale), so no uniform-scale assumption is made.
    """
    if len(anchors) < REG_MIN_ANCHORS:
        return None
    best = None
    for key, m in layout_maps.items():
        ov = [a for a in anchors if a[0] in m]
        if best is None or len(ov) > len(best[1]):
            best = (key, ov, m)
    _key, ov, m = best
    corr, seen = [], set()
    for t, px, py in ov:
        if t in seen:
            continue
        seen.add(t)
        dx, dy = m[t][0], m[t][1]
        corr.append(((dx, dy), (px, py)))
    if len(corr) < REG_MIN_ANCHORS:
        return None
    res = _ransac_affine(corr)
    if not res:
        return None
    aff, inliers = res
    if len(inliers) < REG_MIN_ANCHORS:
        return None

    # 2D spread of inlier PDF points (reject a vertical/horizontal line of numbers)
    pus = [c[1][0] for c in inliers]
    pvs = [c[1][1] for c in inliers]
    if (max(pus) - min(pus)) < REG_MIN_SPREAD_PT or (max(pvs) - min(pvs)) < REG_MIN_SPREAD_PT:
        return None

    # median residual gate — this is the real junk filter: random note/grid/
    # dimension numbers won't fit a DXF layout's panel coordinates to a few points.
    ds = sorted(((u-c[1][0])**2 + (v-c[1][1])**2) ** 0.5
                for c in inliers for (u, v) in [_affine_apply(aff, *c[0])])
    if ds[len(ds)//2] > REG_MAX_RESID_PT:
        return None

    # transform must be non-degenerate (real 2D mapping, not a line collapse)
    a, b, c2, d, e, f = aff
    det = a*e - b*d
    if abs(det) < 1e-6:
        return None

    return aff, m


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


def _ocr_page_words(page, pg_idx, scale=300/72, min_conf=75):
    import xml.etree.ElementTree as ET
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    tmp = f"/tmp/bpscan_{pg_idx}.png"
    pix.save(tmp)
    try:
        subprocess.run(
            ["tesseract", tmp, f"/tmp/bphocr_{pg_idx}", "--psm", "12", "-l", "eng", "hocr"],
            capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        logging.warning(f"Tesseract timed out on blueprint page {pg_idx}")
        return []
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
            if conf_m and int(conf_m.group(1)) < min_conf:
                continue
            px0, py0, px1, py1 = [int(v) for v in bm.groups()]
            t = "".join(word.itertext()).strip()
            if t:
                words.append((t, px0/scale, py0/scale, px1/scale, py1/scale))
    except Exception:
        pass
    return words


def ocr_region(pdf_path, page_index, rect_pts, scale=400/72):
    """OCR a rectangular region (given in PDF points) of one page and return the
    panel-number candidates found there, as
    [{'panel': '211', 'bbox': [x0,y0,x1,y1]}] in page coordinates. De-duplicated,
    sorted by numeric value (panel numbers usually run in order)."""
    import xml.etree.ElementTree as ET, tempfile
    doc = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return []
        page = doc[page_index]
        rx0, ry0, rx1, ry1 = [float(v) for v in rect_pts]
        clip = fitz.Rect(min(rx0, rx1), min(ry0, ry1), max(rx0, rx1), max(ry0, ry1))
        pix  = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip)
        tmp  = tempfile.mktemp(suffix=".png"); base = tmp[:-4]
        pix.save(tmp)
        try:
            subprocess.run(["tesseract", tmp, base, "--psm", "11", "-l", "eng", "hocr"],
                           capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            logging.warning(f"Tesseract timed out on region OCR")
            return []
        seen, out = {}, []
        try:
            tree = ET.parse(base + ".hocr")
            for word in tree.iter():
                if word.get("class") != "ocrx_word":
                    continue
                bm = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", word.get("title", ""))
                if not bm:
                    continue
                t = "".join(word.itertext()).strip().strip(".,'\"")
                m = re.match(r"^(\d{1,3})([A-Z]?)$", t)
                if not m:
                    continue
                val = int(m.group(1))
                if not (PANEL_MIN <= val <= PANEL_MAX):
                    continue
                panel = m.group(1) + m.group(2)
                if panel in seen:
                    continue
                seen[panel] = True
                px0, py0, px1, py1 = [int(v) for v in bm.groups()]
                out.append({
                    "panel": panel, "val": val,
                    "bbox": [clip.x0 + px0/scale, clip.y0 + py0/scale,
                             clip.x0 + px1/scale, clip.y0 + py1/scale],
                })
        finally:
            for f in (tmp, base + ".hocr"):
                try: os.unlink(f)
                except Exception: pass
        out.sort(key=lambda r: r["val"])
        for r in out:
            r.pop("val", None)
        return out
    finally:
        doc.close()


# --- Blueprint Annotator ---------------------------------------------------

# No red — red is reserved for the Panel Mapper's panel boxes. These are the EXACT
# RGB equivalents of SHIP_COLORS in packing_list_editor.html / packing_list_tracker.html
# (same order) so a shipment's blueprint color matches its tracker color exactly.
_SHIPMENT_COLORS = [
    ((0.094, 0.949, 0.235), (0.094, 0.949, 0.235)),  # #18f23c green
    ((1.0,   0.851, 0.0),   (1.0,   0.851, 0.0)),    # #ffd900 yellow
    ((0.0,   0.776, 1.0),   (0.0,   0.776, 1.0)),    # #00c6ff cyan
    ((1.0,   0.533, 0.0),   (1.0,   0.533, 0.0)),    # #ff8800 orange
    ((0.878, 0.0,   0.878), (0.878, 0.0,   0.878)),  # #e000e0 magenta
    ((0.0,   0.910, 0.847), (0.0,   0.910, 0.847)),  # #00e8d8 teal
    ((0.722, 0.0,   1.0),   (0.722, 0.0,   1.0)),    # #b800ff purple
]

def _shipment_color(shipment_index):
    return _SHIPMENT_COLORS[shipment_index % len(_SHIPMENT_COLORS)]


def generate_tracked_blueprint_panel_map(scan_pdf, all_locs, delivery_state, output_path,
                                         shipment_colors=None):
    """Delivery-status version of the Panel Mapper output.

    Uses the Panel Mapper's pre-verified panel positions (``all_locs``) instead
    of running OCR.  Every panel in the drawing is shown:

    - **Delivered** panels → colored annotation in their shipment color + white
      chip showing  "PANEL  skid"  so you can read it at a glance.
    - **Undelivered** panels → faint gray annotation + gray chip (visible but
      clearly not delivered).

    The DELIVERED summary table is drawn in the top-right corner as usual.
    ``scan_pdf`` is the Panel Mapper's trimmed scan PDF (pages already match the
    0-based page indices stored in ``all_locs``).
    """
    doc = fitz.open(scan_pdf)

    # Use the persistent per-packing-list color map when provided (same colors as
    # the tracker UI + editor); otherwise fall back to first-seen order.
    if shipment_colors:
        shipment_order = dict(shipment_colors)
    else:
        shipment_order = {}
        for info in delivery_state.values():
            s = info.get("shipment", "")
            if s not in shipment_order:
                shipment_order[s] = len(shipment_order)

    # Delivered panel lookup: panel_str → (skid, shipment)
    delivered = {p: (info["skid"], info.get("shipment", ""))
                 for p, info in delivery_state.items()}

    # Group ALL panels by page
    page_all = {}
    for key, loc in all_locs.items():
        try:
            pg = int(loc["page"])
        except (KeyError, TypeError, ValueError):
            continue
        label = str(loc.get("label") or key)
        page_all.setdefault(pg, []).append((key, label, loc["bbox"]))

    GRAY_FILL   = (0.55, 0.55, 0.55)
    GRAY_STROKE = (0.35, 0.35, 0.35)
    WHITE       = (1.0, 1.0, 1.0)

    # Collect delivered panels per page for the summary table (same format as
    # generate_tracked_blueprint expects)
    page_delivered = {}

    for pg_idx, entries in page_all.items():
        if pg_idx >= doc.page_count:
            continue
        page = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height

        for key, label, bbox in entries:
            x0, y0, x1, y1 = bbox
            pad = 2.0
            rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)

            if label in delivered:
                skid_num, shipment = delivered[label]
                fill_c, stroke_c = _shipment_color(shipment_order.get(shipment, 0))
                opacity = 0.45
                chip_color = fill_c
                chip_text_color = (0.05, 0.05, 0.05)
                page_delivered.setdefault(pg_idx, []).append(
                    (label, skid_num, shipment, bbox))
            else:
                fill_c, stroke_c = GRAY_FILL, GRAY_STROKE
                opacity = 0.15
                chip_color = GRAY_FILL
                chip_text_color = (0.4, 0.4, 0.4)

            # Panel highlight: a filled rectangle drawn directly into the page with
            # NO stroke at all (color=None) — annotation borders straddle the edge and
            # show as a light ring that hides the printed number, even at width 0.
            page.draw_rect(rect, color=None, fill=fill_c, fill_opacity=opacity, width=0)

            # Number chip: left edge of chip = right edge of highlight, bottom of chip = top of highlight.
            fs = 7.0
            chip_w = fs * len(label) * 0.65 + 4
            chip_h = fs + 3
            cx0 = x1 + pad              # chip left edge = highlight right edge
            cx1 = cx0 + chip_w
            cy1 = y0 - pad              # chip bottom = highlight top
            cy0 = cy1 - chip_h
            # Clamp: keep chip within page bounds
            if cx1 > page.rect.width - 1:
                cx1 = page.rect.width - 1.0; cx0 = cx1 - chip_w
            if cy0 < 0:
                cy0 = y1 + pad; cy1 = cy0 + chip_h
            page.draw_rect(fitz.Rect(cx0, cy0, cx1, cy1),
                           color=stroke_c, fill=chip_color, width=0)
            page.insert_text((cx0 + 2, cy1 - 2), label,
                             fontsize=fs, color=chip_text_color,
                             fontname="Helvetica-Bold")

    # Draw the DELIVERED summary table on each page that has deliveries
    for pg_idx, panels in page_delivered.items():
        if pg_idx >= doc.page_count:
            continue
        page = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height
        _insert_delivery_table(page, panels, pw, ph, shipment_order)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()


def generate_tracked_blueprint(blueprint_path, delivery_state, panel_locations, output_path,
                               shipment_colors=None):
    doc = fitz.open(blueprint_path)

    # Use the persistent per-packing-list color map when provided; otherwise fall
    # back to first-seen order. Same map is used by the tracker UI + editor.
    if shipment_colors:
        shipment_order = dict(shipment_colors)
    else:
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

    table_cells = {}   # panel_str -> {"page": idx, "bbox": [x0,y0,x1,y1]} of its table row
    for pg_idx, panels in page_panels.items():
        if pg_idx >= doc.page_count:
            continue
        page   = doc[pg_idx]
        pw, ph = page.rect.width, page.rect.height
        for panel_str, skid_num, shipment, bbox in panels:
            x0, y0, x1, y1 = bbox
            pad = 3
            fill_c, stroke_c = _shipment_color(shipment_order.get(shipment, 0))
            # Use a PDF annotation (not a content-stream draw) so the highlight
            # is independently selectable and deletable in Acrobat/Preview/etc.
            # Deleting the annotation leaves the original drawing and numbers intact.
            # Filled rectangle, NO stroke (color=None) → never a border over the number.
            page.draw_rect(fitz.Rect(x0-pad, y0-pad, x1+pad, y1+pad),
                           color=None, fill=fill_c, fill_opacity=0.45, width=0)
        cells = _insert_delivery_table(page, panels, pw, ph, shipment_order)
        for ps, bbox in (cells or {}).items():
            table_cells[ps] = {"page": pg_idx, "bbox": bbox}

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return table_cells


def generate_panel_map_blueprint(blueprint_path, panel_locations, output_path,
                                 progress_cb=None, keep_only_panel_pages=True):
    """Verification view: draw a RED box on every located panel and print the
    panel number just above each box.

    Used by the Panel Print Mapper tool so a human can eyeball whether the panel
    locator read each number correctly (the printed label = what the tool thinks
    the panel number is, sitting right above the panel on the drawing).

    When ``keep_only_panel_pages`` is True (default) the saved PDF contains ONLY
    the pages that actually have panels — every blank/non-panel page is dropped so
    the viewer shows just the relevant sheets. The original blueprint is untouched.

    Returns a dict: {"drawn", "total_pages", "kept_pages", "kept_count"} where
    ``kept_pages`` is the list of original (1-based) page numbers kept.
    """
    doc = fitz.open(blueprint_path)

    # group panel locations by page
    page_panels = {}
    for panel_str, loc in panel_locations.items():
        try:
            pg = int(loc["page"])
        except (KeyError, TypeError, ValueError):
            continue
        # an instance may carry an explicit display label (duplicates of a number
        # are stored under unique keys but should print the real number)
        label = str(loc.get("label") or panel_str) if isinstance(loc, dict) else str(panel_str)
        page_panels.setdefault(pg, []).append((label, loc["bbox"]))

    RED   = (0.85, 0.10, 0.10)
    WHITE = (1, 1, 1)
    drawn = 0
    total_pages = doc.page_count

    for pg_idx in range(total_pages):
        if progress_cb:
            progress_cb(pg_idx, total_pages)
        if pg_idx not in page_panels:
            continue
        page   = doc[pg_idx]
        ph     = page.rect.height

        for panel_str, bbox in page_panels[pg_idx]:
            x0, y0, x1, y1 = bbox
            pad  = 2.0
            rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)

            # Red highlight box (selectable/deletable annotation, faint fill so
            # the underlying printed number stays readable).
            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=RED, fill=RED)
            annot.set_opacity(0.22)
            annot.set_border(width=1.0)
            annot.set_info(title=f"Panel {panel_str}")
            annot.update()

            # Confirmation number on a white chip.
            # Bottom-right corner of chip = top-right corner of highlight box.
            fs    = 7.0
            label = str(panel_str)
            try:
                tw = fitz.get_text_length(label, fontname="helv", fontsize=fs)
            except Exception:
                tw = len(label) * fs * 0.55
            lw   = tw + 3.0
            lh   = fs + 3.0
            lx0  = rect.x1 + 2           # chip left edge = highlight right edge
            lx1  = lx0 + lw
            ly1  = rect.y0               # chip bottom = highlight top
            ly0  = ly1 - lh
            if lx1 > page.rect.width - 2:  # clamp at the page's right margin
                lx1 = page.rect.width - 2.0; lx0 = lx1 - lw
            if ly0 < 2:                    # clamp at the page's top margin
                ly0 = 2.0; ly1 = ly0 + lh
            page.draw_rect(fitz.Rect(lx0, ly0, lx1, ly1),
                           color=RED, fill=WHITE, width=0.5)
            page.insert_text((lx0 + 1.5, ly1 - 2.5), label,
                             fontsize=fs, fontname="helv", color=RED)
            drawn += 1

    pages_with_panels = sorted(page_panels.keys())
    if keep_only_panel_pages and pages_with_panels:
        # Keep only the panel-bearing pages (annotations + labels travel with them).
        doc.select(pages_with_panels)

    output_pages = doc.page_count
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return {
        "drawn": drawn,
        "total_pages": total_pages,                       # pages scanned
        "output_pages": output_pages,                     # pages in the saved PDF
        "pages_with_panels": len(pages_with_panels),      # how many had panels
        "panel_pages": [p + 1 for p in pages_with_panels],
    }


def _insert_delivery_table(page, panels, pw, ph, shipment_order):
    if not panels:
        return {}

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

    cells = {}   # panel_str -> [x0, y0, x1, y1] of its table row (PDF points)
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
        cells[panel_str] = [ox, ry, ox+unit_w, ry+ROW_H]

    legend_y = ry1 - legend_h
    page.draw_line((rx0, legend_y), (rx1, legend_y), color=(0.7,0.7,0.7), width=0.5)
    for j, ship in enumerate(page_shipments):
        ly  = legend_y + 2 + j * LEGEND_ROW_H
        idx = shipment_order.get(ship, 0)
        fill_c, stroke_c = _shipment_color(idx)
        page.draw_rect(fitz.Rect(rx0+PAD, ly+2, rx0+PAD+10, ly+LEGEND_ROW_H-2),
                       color=stroke_c, fill=fill_c, width=0)
        label = _legend_short(ship)
        page.insert_text((rx0+PAD+14, ly+LEGEND_ROW_H-3), label,
                         fontsize=7, color=(0.1,0.1,0.1), fontname="Helvetica")

    page.draw_rect(fitz.Rect(rx0, ry0, rx1, ry1), color=(0,0,0), fill=None, width=1.2)
    return cells


def _legend_short(ship):
    """Reduce a shipment label (filename stem) to just '#N  date' for the PDF legend."""
    # Shipment number: '#5', 'Shipment 5', 'Shipment #5', or first bare number
    nm = re.search(r'#\s*(\d+)|[Ss]hipment\s+#?\s*(\d+)', ship)
    if nm:
        num = '#' + next(g for g in nm.groups() if g is not None)
    else:
        nm2 = re.search(r'\b(\d+)\b', ship)
        num = ('#' + nm2.group(1)) if nm2 else ''
    # Date: MM/DD/YYYY, MM-DD-YYYY, MM.DD.YYYY, or YYYY-MM-DD
    dm = re.search(r'\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|\d{4}[./\-]\d{1,2}[./\-]\d{1,2}', ship)
    date = dm.group(0) if dm else ''
    if num and date:
        return f'{num}  {date}'
    return num or date or ship[:25]


def _sort_key(panel_str):
    m = re.match(r"(\d+)", panel_str)
    return int(m.group(1)) if m else 0
