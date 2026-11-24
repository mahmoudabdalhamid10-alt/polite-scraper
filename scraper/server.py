"""Tiny web UI using only the standard library. Run: python -m scraper.server"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import ScrapeError, scrape
from .export import to_csv, to_xlsx

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Polite Scraper</title>
<style>body{font:16px system-ui;max-width:640px;margin:40px auto;padding:0 16px;background:#0f172a;color:#e2e8f0}
input,select,button{font:inherit;padding:10px;margin:4px 0;border-radius:8px;border:1px solid #334155;background:#1e293b;color:inherit;width:100%;box-sizing:border-box}
button{background:#f5b301;color:#111;font-weight:600;cursor:pointer}h1{color:#f5b301}small{color:#94a3b8}</style>
<h1>Polite Scraper</h1>
<p>Pick a practice source or paste a public URL. Output: CSV or Excel. Obeys robots.txt, 1 request/second, no personal data.</p>
<form action=/download>
<label>Source</label><select name=source><option value=books>Books (books.toscrape.com)</option>
<option value=quotes>Quotes (quotes.toscrape.com)</option><option value="">Custom URL (first table or links)</option></select>
<label>Custom URL</label><input name=url placeholder="https://example.com/page-with-a-table">
<label>Pages (max 20)</label><input name=pages type=number min=1 max=20 value=2>
<label>Format</label><select name=fmt><option>csv</option><option>xlsx</option></select>
<button>Scrape and download</button></form>
<p><small>Blocked: Alibaba, AliExpress, Amazon, social networks. Not for personal data.</small></p>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/download":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                rows = scrape(q.get("source") or None, q.get("url") or None, q.get("pages", 1))
            except (ScrapeError, ValueError) as e:
                return self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")
            except Exception as e:  # network errors etc.
                return self._send(502, json.dumps({"error": f"Fetch failed: {e}"}).encode(), "application/json")
            if q.get("fmt") == "xlsx":
                return self._send(200, to_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  {"Content-Disposition": "attachment; filename=data.xlsx"})
            return self._send(200, to_csv(rows), "text/csv; charset=utf-8",
                              {"Content-Disposition": "attachment; filename=data.csv"})
        self._send(404, b"not found", "text/plain")


def main(port=8000):
    print(f"http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    main()
