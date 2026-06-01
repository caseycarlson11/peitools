"""Blueprint Callout Link Engine — v5, speed-first
Strategy:
  1. Find every circle with a bisecting line (geometric only, no OCR)
  2. OCR only the bottom half — single fast pass — get the D-page number
  3. Link to that D-page. Skip top half entirely.
"""
import fitz, re, pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw

TITLE_X_RATIO = 0.88
SCALE = 3
MIN_CIRCLE = 28
MAX_CIRCLE = 70


def find_callout_circles(page):
    """Geometric detection only — find bisected circles."""
    drawings = page.get_drawings()
    TITLE_X  = page.rect.width * TITLE_X_RATIO

    circles = []
    for d in drawings:
        r = d.get('rect')
        if r is None: continue
        w, h = r.width, r.height
        if not (0.80 < w / max(h, 0.01) < 1.20
                and MIN_CIRCLE < w < MAX_CIRCLE
                and r.x0 < TITLE_X and h > 5):
            continue
        if sum(1 for it in d.get('items', []) if it[0] == 'c') < 2:
            continue
        circles.append(r)

    # De-duplicate
    unique = []
    for c in circles:
        if not any(abs(c.x0-u.x0) < 8 and abs(c.y0-u.y0) < 8 for u in unique):
            unique.append(c)

    # Keep only circles that have a bisecting line (h or v)
    result = []
    for cr in unique:
        mid_y = (cr.y0 + cr.y1) / 2
        mid_x = (cr.x0 + cr.x1) / 2
        has_h = any(
            abs(d['rect'].y0 - mid_y) < 4 and abs(d['rect'].y1 - mid_y) < 4 and
            d['rect'].x0 >= cr.x0 - 3 and d['rect'].x1 <= cr.x1 + 3 and
            d['rect'].width > cr.width * 0.65
            for d in drawings if d.get('rect'))
        has_v = any(
            abs(d['rect'].x0 - mid_x) < 4 and abs(d['rect'].x1 - mid_x) < 4 and
            d['rect'].y0 >= cr.y0 - 3 and d['rect'].y1 <= cr.y1 + 3 and
            d['rect'].height > cr.height * 0.65
            for d in drawings if d.get('rect'))
        if has_h or has_v:
            result.append((cr, 'h' if has_h else 'v'))

    return result


def read_bottom(full_img, cr, orient, scale):
    """Crop the bottom half of the circle and OCR it — one fast pass."""
    px0 = int(cr.x0 * scale)
    py0 = int(cr.y0 * scale)
    px1 = int(cr.x1 * scale)
    py1 = int(cr.y1 * scale)
    pad = 4 * scale

    crop = full_img.crop((max(0, px0-pad), max(0, py0-pad), px1+pad, py1+pad))
    big  = crop.resize((crop.width*5, crop.height*5), Image.LANCZOS)

    gray = ImageOps.grayscale(big)
    t    = ImageEnhance.Contrast(gray).enhance(5.0).point(lambda p: 255 if p > 140 else 0)
    img  = t.filter(ImageFilter.MaxFilter(3))

    if orient == 'v':
        img = img.rotate(90, expand=True)

    H, W  = img.height, img.width
    ip    = int(H * 0.10)
    skip  = int(H * 0.07)

    # Blank midline, then crop just the bottom half
    clean = img.copy()
    ImageDraw.Draw(clean).rectangle([(0, H//2-5), (W, H//2+10)], fill=255)
    bot = clean.crop((ip, H//2+10, W-ip, H-skip))

    # Single OCR pass — fast config
    txt = pytesseract.image_to_string(
        bot, config='--psm 8 --oem 3').strip()
    return _parse_dpage(txt)


def _parse_dpage(txt):
    s = txt.replace(' ', '').upper()
    s = re.sub(r'^[0Oo](\d)', r'D\1', s)
    m = re.search(r'D(\d+)', s)
    if m:
        digits = m.group(1)
        if len(digits) >= 2:
            n2 = int(digits[:2])
            if 10 <= n2 <= 23:
                return f'D{n2}'
        n1 = int(digits[:1])
        if 1 <= n1 <= 9:
            return f'D{n1}'
    return None


def detect_callouts_on_page(doc, pi, scale=SCALE, known_dpages=None):
    page        = doc[pi]
    circle_list = find_callout_circles(page)
    if not circle_list:
        return []

    pix      = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    full_img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

    callouts = []
    for cr, orient in circle_list:
        dpage = read_bottom(full_img, cr, orient, scale)
        if not dpage:
            continue
        dp  = int(dpage[1:])
        pad = 10
        callouts.append({
            'pi':  pi,
            'call': f'?/{dpage}',
            'det':  0,
            'dp':   dp,
            'r':    [cr.x0-pad, cr.y0-pad, cr.x1+pad, cr.y1+pad],
            'cx':   (cr.x0 + cr.x1) / 2,
            'cy':   (cr.y0 + cr.y1) / 2,
        })
    return callouts
