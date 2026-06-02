"""
PEI Tools — Local callout engine tester
Usage:
    python test_engine.py path/to/blueprint.pdf
    python test_engine.py path/to/blueprint.pdf --pages 1-5
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'BlueprintLinker'))

def main():
    parser = argparse.ArgumentParser(description='Test callout detection on a blueprint PDF')
    parser.add_argument('pdf', help='Path to blueprint PDF')
    parser.add_argument('--pages', help='Page range to test, e.g. 1-5 or 3', default=None)
    parser.add_argument('--scale', type=int, default=3, help='Render scale (default 3)')
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"ERROR: File not found: {args.pdf}")
        sys.exit(1)

    try:
        import fitz
    except ImportError:
        print("ERROR: pymupdf not installed. Run: pip install pymupdf")
        sys.exit(1)

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:
        print("WARNING: Tesseract not found or not working.")
        print("  Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  Then add it to PATH or set pytesseract.pytesseract.tesseract_cmd")

    from callout_engine import detect_callouts_on_page

    doc     = fitz.open(args.pdf)
    n_pages = len(doc)
    print(f"\nBlueprint: {os.path.basename(args.pdf)}")
    print(f"Pages: {n_pages}")

    # Parse page range
    if args.pages:
        if '-' in args.pages:
            a, b = args.pages.split('-')
            pages = range(int(a)-1, min(int(b), n_pages))
        else:
            pages = range(int(args.pages)-1, int(args.pages))
    else:
        pages = range(n_pages)

    print(f"Testing pages: {list(p+1 for p in pages)}\n")
    print("-" * 50)

    total    = []
    t_start  = time.time()

    for pi in pages:
        t_page = time.time()
        found  = detect_callouts_on_page(doc, pi, scale=args.scale)
        elapsed = time.time() - t_page

        if found:
            print(f"Page {pi+1:3d}: {len(found):3d} callouts  ({elapsed:.1f}s)")
            for c in sorted(found, key=lambda x: (x['cx'], x['cy'])):
                print(f"          {c['call']}  cx={c['cx']:.0f} cy={c['cy']:.0f}")
        else:
            print(f"Page {pi+1:3d}:   0 callouts  ({elapsed:.1f}s)")

        total.extend(found)

    total_time = time.time() - t_start
    print("-" * 50)
    print(f"\nTotal callouts found : {len(total)}")
    print(f"Total time           : {total_time:.1f}s")
    print(f"Avg per page         : {total_time/max(len(list(pages)),1):.1f}s")

    # Summary by D-page
    if total:
        from collections import Counter
        dp_counts = Counter(c['dp'] for c in total)
        print(f"\nCallouts by D-page:")
        for dp in sorted(dp_counts):
            print(f"  D{dp:2d}: {dp_counts[dp]} links")

    doc.close()

if __name__ == '__main__':
    main()
