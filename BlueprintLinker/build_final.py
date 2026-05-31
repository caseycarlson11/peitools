import fitz, json, re

PDF_IN  = '/sessions/zealous-youthful-hamilton/mnt/uploads/2023-11-01 U3925 Modesto.pdf'
PDF_OUT = '/sessions/zealous-youthful-hamilton/mnt/PEItools.com/Modesto_Linked3.pdf'
DATA    = '/sessions/zealous-youthful-hamilton/mnt/outputs/callouts_v2.json'

doc  = fitz.open(PDF_IN)
data = json.load(open(DATA))
callouts = list(data['callouts'])

CORRECTIONS = {
    6:[(1,1),(4,6)],7:[(1,9),(1,13)],8:[(2,7),(1,1)],
    9:[(1,9),(2,11),(2,13)],10:[(2,13),(2,11),(1,1)],
    11:[(2,17),(2,17),(4,17)],12:[(2,18),(4,17)],13:[(4,17),(4,17)],
    14:[(1,20),(2,20),(1,21),(2,21),(2,21)],
    19:[(1,4),(1,4),(1,3),(2,2),(2,8),(2,2),(2,10),(1,9)],
    20:[(1,6),(4,8),(1,1),(2,2),(1,8),(2,3),(2,2),(2,4),(2,3),(2,4),(2,3)],
    21:[(2,15),(2,7),(3,15),(1,9),(2,13),(1,9)],
    23:[(2,2),(2,4),(2,4),(2,3),(1,1),(2,6),(2,10),(2,2)],
    24:[(2,2)],
    26:[(1,19),(4,17),(1,19),(3,18),(2,18),(2,19),(1,18),(2,19),(1,17),(1,19),(1,19),(4,18),(1,19)],
    27:[(2,19),(2,17),(2,19),(2,17)],
    28:[(2,19),(1,19),(2,17),(2,17),(2,19),(2,17)],
    29:[(2,19),(1,19),(4,17),(1,17),(1,19),(2,19),(1,19),(4,17),(1,19),(4,17),(1,17)],
    30:[(2,22),(2,22),(3,22),(1,23),(2,22),(4,22),(2,22),(2,22),(2,20),(2,21)],
    31:[(2,21),(4,20),(2,22),(4,22),(1,22),(2,22),(4,22),(2,22),(4,22)],
    32:[(2,2),(4,3),(1,2),(2,2),(2,2),(2,4),(2,3)],
    33:[(2,11),(1,14),(1,11),(1,10),(5,13),(3,11),(1,9),(1,12)],
}

# Apply corrections: for each correction page, add missing callouts
# Use positions from existing detections where possible, else use circle positions from drawings
for pi, expected in CORRECTIONS.items():
    page = doc[pi]
    current = [c for c in callouts if c['pi']==pi]
    remaining = list(expected)
    # Remove already-found ones
    for c in current:
        key=(c['det'],c['dp'])
        if key in remaining: remaining.remove(key)
    if not remaining: continue

    # Get circle positions from page drawings (no OCR needed)
    from PIL import Image
    drawings = page.get_drawings()
    TITLE_X = page.rect.width * 0.88
    circle_rects = []
    for d in drawings:
        r = d.get('rect')
        if r is None: continue
        w,h = r.width,r.height
        if not (0.80<w/max(h,0.01)<1.20 and 28<w<70 and r.x0<TITLE_X and h>5): continue
        if sum(1 for it in d.get('items',[]) if it[0]=='c') < 2: continue
        circle_rects.append(r)
    # De-dup
    unique = []
    for c in circle_rects:
        if not any(abs(c.x0-u.x0)<8 and abs(c.y0-u.y0)<8 for u in unique):
            unique.append(c)
    # Filter circles already matched
    matched_pos = set((round(c.get('cx',0)),round(c.get('cy',0))) for c in current)
    unmatched = [r for r in unique if not any(
        abs((r.x0+r.x1)/2-mx)<25 and abs((r.y0+r.y1)/2-my)<25
        for mx,my in matched_pos)]
    unmatched.sort(key=lambda r:(round((r.y0+r.y1)/2/100)*100,(r.x0+r.x1)/2))

    for i,(det_e,dp_e) in enumerate(remaining):
        if i < len(unmatched):
            cr = unmatched[i]
            pad=10
            r=[cr.x0-pad,cr.y0-pad,cr.x1+pad,cr.y1+pad]
            cx=(cr.x0+cr.x1)/2; cy=(cr.y0+cr.y1)/2
        else:
            # Fallback: use a default position in the drawing area
            pw,ph = page.rect.width, page.rect.height
            r=[pw*0.1,ph*0.1,pw*0.1+60,ph*0.1+60]
            cx,cy = pw*0.1+30, ph*0.1+30
        callouts.append({'pi':pi,'call':f'{det_e}/D{dp_e}','det':det_e,'dp':dp_e,
                         'r':r,'cx':cx,'cy':cy})
        print(f"  Correction p{pi+1}: {det_e}/D{dp_e}")

print(f"Total callouts: {len(callouts)}")

# Build D-page zones
def get_zones(page, n):
    blocks = page.get_text('blocks')
    pos=[]
    for b in blocks:
        txt=b[4].replace('\n',' ')
        if 'ARCH' in txt and 'REF' in txt and b[0]<2400:
            pos.append(((b[0]+b[2])/2,(b[1]+b[3])/2))
    pw,ph=page.rect.width,page.rect.height; DX=pw*0.88
    if pos:
        pos.sort(key=lambda p:(round(p[0]/300)*300,p[1]))
        zones=[]
        for cx,cy in pos:
            hw=min(DX/n*0.55,700)
            z=fitz.Rect(cx-hw,cy-100,cx+hw,cy+600)&fitz.Rect(0,0,DX,ph)
            zones.append(z)
        return zones
    sw=DX/n
    return [fitz.Rect(i*sw,0,(i+1)*sw,ph) for i in range(n)]

d_zones={}
for dn in range(1,24):
    pi=38+dn-1; page=doc[pi]
    n=sum(1 for b in page.get_text('blocks') if 'ARCH' in b[4] and 'REF' in b[4] and b[0]<2400)
    if n==0: n=1
    d_zones[dn]=get_zones(page,n)

ORANGE=(1.0,0.65,0.2); BORDER=(0.85,0.45,0.0)
added=0
for c in callouts:
    pi=c['pi']; det=c['det']; dp=c['dp']
    rect=fitz.Rect(c['r']); dest_pi=38+dp-1
    zones=d_zones.get(dp,[]); zi=min(det-1,max(0,len(zones)-1))
    page=doc[pi]
    sh=page.new_shape()
    sh.draw_rect(rect)
    sh.finish(color=BORDER,fill=ORANGE,fill_opacity=0.35,width=1.2)
    sh.commit()
    to_pt=fitz.Point(zones[zi].x0,zones[zi].y0) if zones else fitz.Point(0,0)
    page.insert_link({'kind':fitz.LINK_GOTO,'from':rect,'page':dest_pi,'to':to_pt})
    added+=1

print(f"Links added: {added}")
doc.save(PDF_OUT,garbage=4,deflate=True,incremental=False)
print(f"Saved: {PDF_OUT}")
