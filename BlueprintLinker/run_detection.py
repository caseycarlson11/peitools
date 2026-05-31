"""Main processing script - uses callout_engine.py"""
import fitz, json, sys, os
sys.path.insert(0, '/sessions/zealous-youthful-hamilton/mnt/outputs')
from callout_engine import detect_callouts_on_page, apply_corrections, find_callout_circles

PDF = '/sessions/zealous-youthful-hamilton/mnt/uploads/2023-11-01 U3925 Modesto.pdf'
OUT = '/sessions/zealous-youthful-hamilton/mnt/outputs/callouts_v2.json'

doc = fitz.open(PDF)

# Manual corrections: page_index -> list of (det, dp) tuples
# "D/D18" treated as (1, 18)
CORRECTIONS = {
    6:  [(1,1),(4,6)],
    7:  [(1,9),(1,13)],
    8:  [(2,7),(1,1)],
    9:  [(1,9),(2,11),(2,13)],
    10: [(2,13),(2,11),(1,1)],
    11: [(2,17),(2,17),(4,17)],
    12: [(2,18),(4,17)],
    13: [(4,17),(4,17)],
    14: [(1,20),(2,20),(1,21),(2,21),(2,21)],
    19: [(1,4),(1,4),(1,3),(2,2),(2,8),(2,2),(2,10),(1,9)],
    20: [(1,6),(4,8),(1,1),(2,2),(1,8),(2,3),(2,2),(2,4),(2,3),(2,4),(2,3)],
    21: [(2,15),(2,7),(3,15),(1,9),(2,13),(1,9)],
    23: [(2,2),(2,4),(2,4),(2,3),(1,1),(2,6),(2,10),(2,2)],
    24: [(2,2)],
    26: [(1,19),(4,17),(1,19),(3,18),(2,18),(2,19),(1,18),(2,19),(1,17),(1,19),(1,19),(4,18),(1,19)],
    27: [(2,19),(2,17),(2,19),(2,17)],
    28: [(2,19),(1,19),(2,17),(2,17),(2,19),(2,17)],
    29: [(2,19),(1,19),(4,17),(1,17),(1,19),(2,19),(1,19),(4,17),(1,19),(4,17),(1,17)],
    30: [(2,22),(2,22),(3,22),(1,23),(2,22),(4,22),(2,22),(2,22),(2,20),(2,21)],
    31: [(2,21),(4,20),(2,22),(4,22),(1,22),(2,22),(4,22),(2,22),(4,22)],
    32: [(2,2),(4,3),(1,2),(2,2),(2,2),(2,4),(2,3)],
    33: [(2,11),(1,14),(1,11),(1,10),(5,13),(3,11),(1,9),(1,12)],
}

# Load existing results
data = json.load(open(OUT)) if os.path.exists(OUT) else {'callouts':[],'done':[]}
done = set(data.get('done',[]))

start = int(sys.argv[1]) if len(sys.argv)>1 else 0
end   = int(sys.argv[2]) if len(sys.argv)>2 else 5

for pi in range(start, min(end, 38)):
    if pi in done:
        print(f"p{pi+1}: skip"); continue
    results = detect_callouts_on_page(doc, pi)
    data['callouts'].extend(results)
    done.add(pi)
    if results:
        for r in results: print(f"  p{pi+1}: {r['call']}")
    else:
        n_circles = len(find_callout_circles(doc[pi]))
        print(f"p{pi+1}: {n_circles} circles → no D-refs")

data['done'] = list(done)
with open(OUT,'w') as f: json.dump(data,f,indent=2)
print(f"Total so far: {len(data['callouts'])}")
