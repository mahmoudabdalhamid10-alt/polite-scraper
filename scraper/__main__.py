import argparse
from .core import scrape, ScrapeError
from .export import to_csv, to_xlsx

p = argparse.ArgumentParser(description="Polite scraper (robots.txt, rate limited)")
p.add_argument("--source", choices=["books", "quotes"])
p.add_argument("--url")
p.add_argument("--pages", type=int, default=1)
p.add_argument("--out", default="data.csv", help="data.csv or data.xlsx")
a = p.parse_args()
try:
    rows = scrape(a.source, a.url, a.pages, progress=lambda pg, n: print(f"page {pg}: {n} rows"))
except ScrapeError as e:
    raise SystemExit(f"Refused: {e}")
with open(a.out, "wb") as fh:
    fh.write((to_xlsx if a.out.endswith(".xlsx") else to_csv)(rows))
print(f"Wrote {len(rows)} rows to {a.out}")
