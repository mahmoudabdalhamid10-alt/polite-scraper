"""Small web app using only the standard library. Run: python -m scraper.server
Reads PORT and HOST from the environment (defaults 8000 / 127.0.0.1)."""
import json
import os
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import ScrapeError, scrape
from .export import to_csv, to_xlsx

PAGE = (Path(__file__).parent / "web" / "index.html").read_bytes()
GATE = threading.BoundedSemaphore(3)       # at most 3 scrapes at once
HITS = defaultdict(deque)                  # per-IP request times
MAX_RUNS_PER_MIN = 6


def too_many(ip):
    now, q = time.time(), HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= MAX_RUNS_PER_MIN:
        return True
    q.append(now)
    return False


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _run(self, q):
        ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        if too_many(ip):
            raise ScrapeError("Too many runs. Please wait a minute and try again.")
        if not GATE.acquire(blocking=False):
            raise ScrapeError("The server is busy. Try again in a few seconds.")
        try:
            return scrape(q.get("source") or None, q.get("url") or None, q.get("pages", 1))
        finally:
            GATE.release()

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/healthz":
            return self._send(200, b"ok", "text/plain")
        if u.path in ("/api/preview", "/download"):
            try:
                rows = self._run(q)
            except (ScrapeError, ValueError) as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:  # network errors etc.
                return self._json(502, {"error": f"Fetch failed: {type(e).__name__}"})
            if u.path == "/api/preview":
                return self._json(200, {"total": len(rows), "rows": rows[:100]})
            if q.get("fmt") == "xlsx":
                return self._send(200, to_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  {"Content-Disposition": "attachment; filename=data.xlsx"})
            return self._send(200, to_csv(rows), "text/csv; charset=utf-8",
                              {"Content-Disposition": "attachment; filename=data.csv"})
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):
        pass


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    main()
