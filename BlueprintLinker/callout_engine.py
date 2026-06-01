"""Blueprint Callout Link Engine — v4, accuracy + speed"""
import fitz, re, pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw
from collections import Counter

TITLE_X_RATIO = 0.88
SCALE = 3
MIN_CIRCLE = 24
MAX_CIRCLE = 75


# ── Circle detection ─────────────────────────────────────────

def find_callout_circles(page):
    """Single-pass detection: collect strict + relaxed candidates together."""
    drawings = page.get_drawings()
    TITLE_X = page.rect.width * TITLE_X_RATIO

    strict = []   # >= 2 curve items
    relaxed = []  # >= 1 curve item (TYP/compound paths)

    for d in drawings:
        r = d.get('rect')
        if r is None:
            continue
        w, h = r.width, r.height
        if not (0.75 < w / max(h, 0.01) < 1.30
                and MIN_CIRCLE < w < MAX_CIRCLE
                and r.x0 < TITLE_X and h > 5):
            continue
        curves = sum(1 for it in d.get('items', []) if it[0] == 'c')
        if curves >= 2:
            strict.append(r)
        elif curves >= 1:
            relaxed.append(r)

    def dedup(rects):
        unique = []
        for c in rects:
            if not any(abs(c.x0 - u.x0) < 8 and abs(c.y0 - u.y0) < 8 for u in unique):
                unique.append(c)
        return unique

    strict  = dedup(strict)
    relaxed = dedup(relaxed)

    def with_orientation(rects):
        result = []
        for cr in rects:
            mid_y = (cr.y0 + cr.y1) / 2
            mid_x = (cr.x0 + cr.x1) / 2
            has_h = any(
                abs(d['rect'].y0 - mid_y) < 5 and abs(d['rect'].y1 - mid_y) < 5 and
                d['rect'].x0 >= cr.x0 - 4 and d['rect'].x1 <= cr.x1 + 4 and
                d['rect'].width > cr.width * 0.55
                for d in drawings if d.get('rect'))
            has_v = any(
                abs(d['rect'].x0 - mid_x) < 8 and abs(d['rect'].x1 - mid_x) < 8 and
                d['rect'].y0 >= cr.y0 - 4 and d['rect'].y1 <= cr.y1 + 4 and
                d['rect'].height > cr.height * 0.55
                for d in drawings if d.get('rect'))
            if has_h or has_v:
                result.append((cr, 'h' if has_h else 'v'))
        return result

    primary = with_orientation(strict)

    # Only add relaxed (TYP) circles on pages with few primary detections
    # and only if they don't overlap a primary circle
    if len(primary) < 5:
        primary_centres = {(round((cr.x0+cr.x1)/2), round((cr.y0+cr.y1)/2))
                           for cr, _ in primary}
        for cr in relaxed:
            cx, cy = round((cr.x0+cr.x1)/2), round((cr.y0+cr.y1)/2)
            if not any(abs(cx-px) < 12 and abs(cy-py) < 12 for px,py in primary_centres):
                # Default orient for relaxed: check, else 'h'
                mid_y = (cr.y0+cr.y1)/2; mid_x = (cr.x0+cr.x1)/2
                has_v = any(abs(d['rect'].x0-mid_x)<8 and abs(d['rect'].x1-mid_x)<8 and
                            d['rect'].height>cr.height*0.55
                            for d in drawings if d.get('rect'))
                primary.append((cr, 'v' if has_v else 'h'))

    return primary


# ── Image masking ─────────────────────────────────────────────

def _apply_circle_mask(img):
    """White-out everything outside the circle — removes TYP triangles and nearby text."""
    w, h = img.size
    cx, cy = w / 2, h / 2
    r = min(cx, cy) * 0.92
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=255)
    white = Image.new('RGB', img.size, (255, 255, 255))
    inv = Image.eval(mask, lambda p: 255 - p)
    return Image.composite(white, img, inv)


def prep_circle(full_img, cr, scale, orient):
    px0, py0 = int(cr.x0*scale), int(cr.y0*scale)
    px1, py1 = int(cr.x1*scale), int(cr.y1*scale)
    pad = 5 * scale
    crop = full_img.crop((max(0, px0-pad), max(0, py0-pad), px1+pad, py1+pad))
    big  = crop.resize((crop.width*5, crop.height*5), Image.LANCZOS)
    big  = _apply_circle_mask(big)

    gray = ImageOps.grayscale(big)
    t    = ImageEnhance.Contrast(gray).enhance(5.0).point(lambda p: 255 if p > 140 else 0)
    d    = t.filter(ImageFilter.MaxFilter(3))

    if orient == 'v':
        d = d.rotate(90, expand=True)

    H, W = d.height, d.width
    ip   = int(H * 0.10)
    skip = int(H * 0.07)

    clean = d.copy()
    ImageDraw.Draw(clean).rectangle([(0, H//2-3), (W, H//2+3)], fill=255)

    top      = clean.crop((ip, skip,    W-ip, H//2-3))
    bot      = clean.crop((ip, H//2+3,  W-ip, H-skip))
    bot_deep = clean.crop((ip, H//2+10, W-ip, H-skip))
    return top, bot, bot_deep


# ── OCR ───────────────────────────────────────────────────────

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
        if len(digits) >= 2:
            n2 = int(digits[:2])
            if 10 <= n2 <= 30:
                return f'D{n2}'
        n1 = int(digits[:1])
        if 1 <= n1 <= 9:
            return f'D{n1}'
    return None


def _ocr_top(img):
    """Read detail number (1-9). Stop on first success."""
    for cfg in [
        '--psm 10 --oem 3 -c tessedit_char_whitelist=123456789',
        '--psm 8  --oem 3 -c tessedit_char_whitelist=123456789',
    ]:
        t   = pytesseract.image_to_string(img, config=cfg).strip()
        det = parse_det(t)
        if det:
            return det
    return None


def _ocr_bot(img, img_deep):
    """Read D-page number. Stop as soon as 2 results agree."""
    configs = [
        '--psm 8 --oem 3',
        '--psm 7 --oem 3 -c tessedit_char_whitelist=D0123456789',
    ]
    results = []
    for src in (img, img_deep):
        for cfg in configs:
            r  = pytesseract.image_to_string(src, config=cfg).strip()
            dp = parse_dpage(r)
            if dp:
                results.append(dp)
                # Early exit: two matching results is enough
                if len(results) >= 2 and results.count(dp) >= 2:
                    return dp
    if not results:
        return None
    counts = Counter(results)
    best   = max(counts, key=lambda k: (counts[k], -int(k[1:])))
    return best


def read_circle(full_img, cr, orient, scale):
    top, bot, bot_deep = prep_circle(full_img, cr, scale, orient)
    det   = _ocr_top(top)
    if not det:
        return None, None          # skip bottom OCR if top already failed
    dpage = _ocr_bot(bot, bot_deep)
    return det, dpage


# ── Main entry point ──────────────────────────────────────────

def detect_callouts_on_page(doc, pi, scale=SCALE, known_dpages=None):
    page        = doc[pi]
    circle_list = find_callout_circles(page)
    if not circle_list:
        return []

    pix      = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    full_img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)

    callouts = []
    for cr, orient in circle_list:
        det, dpage = read_circle(full_img, cr, orient, scale)
        if not (det and dpage):
            continue

        dp = int(dpage[1:])

        # Validate against known D-pages and correct if needed
        if known_dpages and dp not in known_dpages:
            shorter = dp // 10
            if shorter > 0 and shorter in known_dpages:
                dp = shorter
            else:
                last = dp % 10
                if last > 0 and last in known_dpages:
                    dp = last
                else:
                    continue

        callouts.append({
            'pi':  pi,
            'call': f'{det}/D{dp}',
            'det':  int(det),
            'dp':   dp,
            'r':    [cr.x0, cr.y0, cr.x1, cr.y1],   # app.py applies LINK_SIZE
            'cx':   (cr.x0 + cr.x1) / 2,
            'cy':   (cr.y0 + cr.y1) / 2,
        })

    return callouts
