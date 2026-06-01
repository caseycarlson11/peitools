"""Blueprint Callout Link Engine — v3, improved detection"""
import fitz, re, pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw
from collections import Counter
import math

TITLE_X_RATIO = 0.88
SCALE = 3
MIN_CIRCLE = 24   # slightly wider to catch smaller TYP circles
MAX_CIRCLE = 75   # slightly wider for large cross-section circles


# ─────────────────────────────────────────────────────────────
# Circle detection — primary (strict) + secondary (relaxed for TYP)
# ─────────────────────────────────────────────────────────────

def find_callout_circles(page):
    drawings = page.get_drawings()
    TITLE_X = page.rect.width * TITLE_X_RATIO

    # ── Primary pass: requires ≥2 curve items + bisecting line ──
    primary = _detect_circles(drawings, TITLE_X, min_curves=2, require_bisect=True)

    # ── Secondary pass: ≥1 curve item, no bisect required (catches TYP) ──
    secondary = _detect_circles(drawings, TITLE_X, min_curves=1, require_bisect=False)

    # Merge: add secondary hits that aren't already in primary (>12pt apart)
    result = list(primary)
    primary_centres = {( round((cr.x0+cr.x1)/2), round((cr.y0+cr.y1)/2) )
                       for cr, _ in primary}
    for cr, orient in secondary:
        cx, cy = round((cr.x0+cr.x1)/2), round((cr.y0+cr.y1)/2)
        if not any(abs(cx-px)<12 and abs(cy-py)<12 for px,py in primary_centres):
            result.append((cr, orient))

    return result


def _detect_circles(drawings, TITLE_X, min_curves, require_bisect):
    candidates = []
    for d in drawings:
        r = d.get('rect')
        if r is None: continue
        w, h = r.width, r.height
        if not (0.75 < w/max(h, 0.01) < 1.30 and MIN_CIRCLE < w < MAX_CIRCLE
                and r.x0 < TITLE_X and h > 5):
            continue
        if sum(1 for it in d.get('items', []) if it[0] == 'c') < min_curves:
            continue
        candidates.append(r)

    # De-duplicate
    unique = []
    for c in candidates:
        if not any(abs(c.x0-u.x0) < 8 and abs(c.y0-u.y0) < 8 for u in unique):
            unique.append(c)

    result = []
    for cr in unique:
        mid_y = (cr.y0 + cr.y1) / 2
        mid_x = (cr.x0 + cr.x1) / 2

        has_hline = any(
            abs(d['rect'].y0 - mid_y) < 5 and abs(d['rect'].y1 - mid_y) < 5 and
            d['rect'].x0 >= cr.x0 - 4 and d['rect'].x1 <= cr.x1 + 4 and
            d['rect'].width > cr.width * 0.55
            for d in drawings if d.get('rect'))

        # Relaxed vertical tolerance: 8pt (was 4pt) — catches cross-section circles
        has_vline = any(
            abs(d['rect'].x0 - mid_x) < 8 and abs(d['rect'].x1 - mid_x) < 8 and
            d['rect'].y0 >= cr.y0 - 4 and d['rect'].y1 <= cr.y1 + 4 and
            d['rect'].height > cr.height * 0.55
            for d in drawings if d.get('rect'))

        if require_bisect:
            if has_hline or has_vline:
                result.append((cr, 'h' if has_hline else 'v'))
        else:
            # For secondary pass: prefer detected orientation, default to 'h'
            orient = 'v' if has_vline and not has_hline else 'h'
            result.append((cr, orient))

    return result


# ─────────────────────────────────────────────────────────────
# Image prep — mask outside circle, split top/bot
# ─────────────────────────────────────────────────────────────

def _apply_circle_mask(img, pad_frac=0.08):
    """White-out everything outside the circle boundary.
    Removes triangle TYP markers, nearby text, and overlapping graphics."""
    w, h = img.size
    cx, cy = w / 2, h / 2
    # Radius: half the smaller dimension minus a small margin
    r = min(cx, cy) * (1.0 - pad_frac)
    mask = Image.new('L', img.size, 0)   # black = keep
    ImageDraw.Draw(mask).ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=255)
    white = Image.new('RGB', img.size, (255, 255, 255))
    # Invert mask: pixels outside circle become white
    inv_mask = Image.eval(mask, lambda p: 255 - p)
    return Image.composite(white, img, inv_mask)


def prep_circle(full_img, cr, scale, orient):
    """Crop, mask, and preprocess a callout circle → (top_img, bot_img)."""
    px0, py0 = int(cr.x0 * scale), int(cr.y0 * scale)
    px1, py1 = int(cr.x1 * scale), int(cr.y1 * scale)
    pad = 5 * scale
    crop = full_img.crop((max(0, px0-pad), max(0, py0-pad), px1+pad, py1+pad))
    big = crop.resize((crop.width*5, crop.height*5), Image.LANCZOS)

    # Mask outside the circle before any processing
    big = _apply_circle_mask(big)

    gray = ImageOps.grayscale(big)
    t = ImageEnhance.Contrast(gray).enhance(5.0).point(lambda p: 255 if p > 140 else 0)
    d = t.filter(ImageFilter.MaxFilter(3))

    if orient == 'v':
        d = d.rotate(90, expand=True)

    H, W = d.height, d.width
    ip = int(H * 0.10)
    skip = int(H * 0.07)

    # Narrower midline blank (6px vs 15px) — reduces bleed without losing digits
    clean = d.copy()
    ImageDraw.Draw(clean).rectangle([(0, H//2-3), (W, H//2+3)], fill=255)

    top = clean.crop((ip, skip,      W-ip, H//2-3))
    bot = clean.crop((ip, H//2+3,    W-ip, H-skip))

    # Extra crop: start bot a bit lower to eliminate midline residue
    bot_tight = clean.crop((ip, H//2+8, W-ip, H-skip))

    return top, bot, bot_tight


# ─────────────────────────────────────────────────────────────
# OCR helpers
# ─────────────────────────────────────────────────────────────

def parse_det(txt):
    m = re.match(r'^(\d)$', txt.strip())
    if m and 1 <= int(m.group(1)) <= 9:
        return m.group(1)
    return None


def parse_dpage(txt):
    s = txt.replace(' ', '').upper()
    s = re.sub(r'^[0Oo](\d)', r'D\1', s)
    m = re.search(r'D(\d+)', s)
    if m:
        digits = m.group(1)
        # Try 2-digit match first (D10–D30)
        if len(digits) >= 2:
            n2 = int(digits[:2])
            if 10 <= n2 <= 30:
                return f'D{n2}'
        # Single digit (D1–D9)
        n1 = int(digits[:1])
        if 1 <= n1 <= 9:
            return f'D{n1}'
    return None


def _ocr_top(img):
    """Try multiple configs to read the detail number (1–9)."""
    for cfg in [
        '--psm 10 --oem 3 -c tessedit_char_whitelist=123456789',
        '--psm 8  --oem 3 -c tessedit_char_whitelist=123456789',
        '--psm 13 --oem 3 -c tessedit_char_whitelist=123456789',
    ]:
        t = pytesseract.image_to_string(img, config=cfg).strip()
        det = parse_det(t)
        if det:
            return det
    return None


def _ocr_bot(img, img_tight):
    """Try multiple configs + crops to read the D-page number.
    Returns the most common valid result across all attempts."""
    results = []
    configs = [
        '--psm 8  --oem 3',
        '--psm 7  --oem 3 -c tessedit_char_whitelist=D0123456789',
        '--psm 13 --oem 3 -c tessedit_char_whitelist=D0123456789',
        '--psm 6  --oem 3',
    ]
    for img_src in (img, img_tight):
        for cfg in configs:
            r = pytesseract.image_to_string(img_src, config=cfg).strip()
            dp = parse_dpage(r)
            if dp:
                results.append(dp)

    if not results:
        return None
    # Return majority vote; on tie, prefer the shorter number (D1 > D11)
    counts = Counter(results)
    max_count = max(counts.values())
    candidates = [k for k, v in counts.items() if v == max_count]
    return min(candidates, key=lambda x: int(x[1:]))  # shorter = smaller number


def read_circle(full_img, cr, orient, scale):
    top, bot, bot_tight = prep_circle(full_img, cr, scale, orient)
    det   = _ocr_top(top)
    dpage = _ocr_bot(bot, bot_tight)
    return det, dpage


# ─────────────────────────────────────────────────────────────
# Main detection entry point
# ─────────────────────────────────────────────────────────────

def detect_callouts_on_page(doc, pi, scale=SCALE, known_dpages=None):
    """Detect all N/Dn callout circles on page pi.

    known_dpages: set of valid D-numbers (ints) found in the document.
    When provided, D-numbers not in the set are corrected or dropped.
    """
    page = doc[pi]
    circle_list = find_callout_circles(page)
    if not circle_list:
        return []

    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    full_img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

    callouts = []
    for cr, orient in circle_list:
        det, dpage = read_circle(full_img, cr, orient, scale)
        if not (det and dpage):
            continue

        dp = int(dpage[1:])

        # ── Validate / correct dp against known D-pages ──
        if known_dpages:
            if dp not in known_dpages:
                # Try shorter number (D11→D1, D12→D1, etc.)
                shorter = dp // 10
                if shorter > 0 and shorter in known_dpages:
                    dp = shorter
                    dpage = f'D{dp}'
                else:
                    # Try last digit (D21→D1, etc.)
                    last = dp % 10
                    if last > 0 and last in known_dpages:
                        dp = last
                        dpage = f'D{dp}'
                    else:
                        continue  # no valid D-page match

        LINK = 24.5  # half of 49pt stamp size
        callouts.append({
            'pi': pi,
            'call': f'{det}/{dpage}',
            'det': int(det),
            'dp': dp,
            'r': [cr.x0 - LINK, cr.y0 - LINK, cr.x1 + LINK - (cr.x1-cr.x0),
                  cr.y0 - LINK + (cr.x1-cr.x0)],   # kept for legacy; actual rect built in app.py
            'cx': (cr.x0 + cr.x1) / 2,
            'cy': (cr.y0 + cr.y1) / 2,
        })

    return callouts
