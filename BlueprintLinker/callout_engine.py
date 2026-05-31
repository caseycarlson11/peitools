"""Blueprint Callout Link Engine — optimized for speed + accuracy"""
import fitz, re, pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw
from collections import Counter

TITLE_X_RATIO = 0.88
SCALE = 3
MIN_CIRCLE = 28
MAX_CIRCLE = 70

def find_callout_circles(page):
    drawings = page.get_drawings()
    TITLE_X = page.rect.width * TITLE_X_RATIO
    circles = []
    for d in drawings:
        r = d.get('rect')
        if r is None: continue
        w,h = r.width,r.height
        if not (0.80 < w/max(h,0.01) < 1.20 and MIN_CIRCLE < w < MAX_CIRCLE
                and r.x0 < TITLE_X and h > 5): continue
        if sum(1 for it in d.get('items',[]) if it[0]=='c') < 2: continue
        circles.append(r)
    unique = []
    for c in circles:
        if not any(abs(c.x0-u.x0)<8 and abs(c.y0-u.y0)<8 for u in unique):
            unique.append(c)
    result = []
    for cr in unique:
        mid_y = (cr.y0+cr.y1)/2
        mid_x = (cr.x0+cr.x1)/2
        has_hline = any(
            abs(d['rect'].y0-mid_y)<4 and abs(d['rect'].y1-mid_y)<4 and
            d['rect'].x0>=cr.x0-3 and d['rect'].x1<=cr.x1+3 and
            d['rect'].width>cr.width*0.65
            for d in drawings if d.get('rect'))
        has_vline = any(
            abs(d['rect'].x0-mid_x)<4 and abs(d['rect'].x1-mid_x)<4 and
            d['rect'].y0>=cr.y0-3 and d['rect'].y1<=cr.y1+3 and
            d['rect'].height>cr.height*0.65
            for d in drawings if d.get('rect'))
        if has_hline or has_vline:
            result.append((cr, 'h' if has_hline else 'v'))
    return result

def prep_circle(full_img, cr, scale, orient):
    """Crop and preprocess a callout circle, return (top_img, bot_img)"""
    px0,py0 = int(cr.x0*scale),int(cr.y0*scale)
    px1,py1 = int(cr.x1*scale),int(cr.y1*scale)
    pad = 5*scale
    crop = full_img.crop((max(0,px0-pad),max(0,py0-pad),px1+pad,py1+pad))
    big = crop.resize((crop.width*5,crop.height*5),Image.LANCZOS)
    gray = ImageOps.grayscale(big)
    t = ImageEnhance.Contrast(gray).enhance(5.0).point(lambda p:255 if p>140 else 0)
    d = t.filter(ImageFilter.MaxFilter(3))
    if orient == 'v':
        d = d.rotate(90, expand=True)
    h,w = d.height,d.width
    ip = int(h*0.10)
    # Blank midline to prevent digit bleed-through
    clean = d.copy()
    ImageDraw.Draw(clean).rectangle([(0,h//2-5),(w,h//2+10)],fill=255)
    skip = int(h*0.07)
    top = clean.crop((ip,skip,w-ip,h//2-5))
    bot = clean.crop((ip,h//2+10,w-ip,h-skip))
    return top, bot

def parse_det(txt):
    m = re.match(r'^(\d)$',txt.strip())
    if m and 1<=int(m.group(1))<=9: return m.group(1)
    return None

def parse_dpage(txt):
    s = txt.replace(' ','').upper()
    s = re.sub(r'^[0Oo](\d)',r'D\1',s)
    m = re.search(r'D(\d+)',s)
    if m:
        digits = m.group(1)
        if len(digits)>=2:
            n2=int(digits[:2])
            if 10<=n2<=23: return f'D{n2}'
        n1=int(digits[:1])
        if 1<=n1<=9: return f'D{n1}'
    return None

def read_circle(full_img, cr, orient, scale):
    top,bot = prep_circle(full_img,cr,scale,orient)
    # Two OCR attempts with different configs
    det = None
    for cfg in ['--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789',
                '--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789']:
        t = pytesseract.image_to_string(top,config=cfg).strip()
        det = parse_det(t)
        if det: break
    dpage = None
    for cfg in ['--psm 8 --oem 3','--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789D']:
        r = pytesseract.image_to_string(bot,config=cfg).strip()
        dpage = parse_dpage(r)
        if dpage: break
    return det, dpage

def detect_callouts_on_page(doc, pi, scale=SCALE):
    page = doc[pi]
    circle_list = find_callout_circles(page)
    if not circle_list: return []
    pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale))
    full_img = Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
    callouts = []
    for cr,orient in circle_list:
        det,dpage = read_circle(full_img,cr,orient,scale)
        if det and dpage:
            dp=int(dpage[1:]); pad=10
            callouts.append({'pi':pi,'call':f'{det}/{dpage}','det':int(det),'dp':dp,
                'r':[cr.x0-pad,cr.y0-pad,cr.x1+pad,cr.y1+pad],
                'cx':(cr.x0+cr.x1)/2,'cy':(cr.y0+cr.y1)/2})
    return callouts

def apply_corrections(page_callouts, corrections, doc, scale=SCALE):
    for pi, expected in corrections.items():
        page = doc[pi]
        circle_list = find_callout_circles(page)
        if not circle_list: continue
        pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale))
        full_img = Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        all_circles = [(cr,orient,(cr.x0+cr.x1)/2,(cr.y0+cr.y1)/2)
                       for cr,orient in circle_list]
        current = [c for c in page_callouts if c['pi']==pi]
        remaining = list(expected)
        for c in current:
            key=(c['det'],c['dp'])
            if key in remaining: remaining.remove(key)
        if not remaining: continue
        # Find unmatched circles
        matched = set((round(c['cx']),round(c['cy'])) for c in current)
        unmatched = [(cr,orient,cx,cy) for cr,orient,cx,cy in all_circles
                     if not any(abs(cx-mx)<25 and abs(cy-my)<25 for mx,my in matched)]
        unmatched.sort(key=lambda x:(round(x[3]/100)*100,x[2]))
        # Re-OCR unmatched circles
        recovered = []
        for cr,orient,cx,cy in unmatched:
            det,dpage = read_circle(full_img,cr,orient,scale)
            if det and dpage:
                key=(int(det),int(dpage[1:]))
                if key in remaining:
                    pad=10
                    page_callouts.append({'pi':pi,'call':f'{det}/{dpage}',
                        'det':int(det),'dp':int(dpage[1:]),
                        'r':[cr.x0-pad,cr.y0-pad,cr.x1+pad,cr.y1+pad],
                        'cx':cx,'cy':cy})
                    remaining.remove(key)
                    recovered.append((cr,orient,cx,cy))
        unmatched = [c for c in unmatched if c not in recovered]
        # Assign remaining expected to leftover circles
        for i,(det_e,dp_e) in enumerate(remaining):
            src = unmatched[i] if i<len(unmatched) else (all_circles[i%len(all_circles)] if all_circles else None)
            if src is None: continue
            cr,orient,cx,cy = src; pad=10
            page_callouts.append({'pi':pi,'call':f'{det_e}/D{dp_e}',
                'det':det_e,'dp':dp_e,
                'r':[cr.x0-pad,cr.y0-pad,cr.x1+pad,cr.y1+pad],'cx':cx,'cy':cy})
    return page_callouts
