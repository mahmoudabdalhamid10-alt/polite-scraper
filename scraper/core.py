"""Polite scraping core: robots.txt check, rate limit, blocklist, parsers."""
import ipaddress
import socket
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "PoliteScraper/1.0 (portfolio project; respects robots.txt)"
MIN_DELAY = 1.0  # seconds between requests to the same host
MAX_PAGES = 20   # hard cap per run

# Sites whose terms forbid automated collection. Extend as needed.
BLOCKED_HOSTS = (
    "alibaba.com", "aliexpress.com", "amazon", "facebook.com", "instagram.com",
    "linkedin.com", "tiktok.com", "x.com", "twitter.com",
)
MAX_BYTES = 2_000_000  # per page download cap
MAX_REDIRECTS = 3


def _blocked_host(host):
    parts = host.split(".")
    for b in BLOCKED_HOSTS:
        if "." in b:
            if host == b or host.endswith("." + b):
                return True
        elif b in parts or any(x.startswith(b) for x in parts):
            return True
    return False


def _public_ip_only(host):
    """Reject hosts that resolve to private, loopback, link-local or reserved addresses (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ScrapeError(f"Cannot resolve {host}.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ScrapeError("Local or private addresses are not allowed.")


class ScrapeError(Exception):
    pass


class PoliteFetcher:
    def __init__(self, delay=MIN_DELAY):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = {}
        self._robots = {}

    def check_allowed(self, url):
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ScrapeError("Only http/https URLs are supported.")
        host = p.hostname.lower()
        if _blocked_host(host):
            raise ScrapeError(f"{host} forbids automated collection. Blocked.")
        _public_ip_only(host)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt", timeout=10)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        if not self._robots[base].can_fetch(USER_AGENT, url):
            raise ScrapeError(f"robots.txt disallows fetching {url}")

    def get(self, url):
        self.check_allowed(url)
        host = urlparse(url).hostname
        wait = self.delay - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        cur = url
        try:
            for _ in range(MAX_REDIRECTS + 1):
                r = self.session.get(cur, timeout=15, stream=True, allow_redirects=False)
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                    cur = urljoin(cur, r.headers["Location"])
                    self.check_allowed(cur)  # every hop is re-checked
                    continue
                break
            else:
                raise ScrapeError("Too many redirects.")
            if r.status_code != 200:
                raise ScrapeError(f"HTTP {r.status_code} for {cur}")
            body = r.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(body) > MAX_BYTES:
                raise ScrapeError("Page is too large (limit 2 MB).")
        finally:
            self._last[host] = time.time()
        return BeautifulSoup(body, "html.parser")


RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_books(soup, url):
    rows = []
    for a in soup.select("article.product_pod"):
        price = a.select_one(".price_color").text.strip()
        price = "".join(c for c in price if c.isdigit() or c == ".")
        rating = RATINGS.get(a.select_one("p.star-rating")["class"][1], None)
        rows.append({
            "title": a.h3.a["title"],
            "price_gbp": float(price),
            "rating_1_to_5": rating,
            "in_stock": "In stock" in a.select_one(".availability").text,
            "url": urljoin(url, a.h3.a["href"]),
        })
    nxt = soup.select_one("li.next a")
    return rows, urljoin(url, nxt["href"]) if nxt else None


def parse_quotes(soup, url):
    rows = [{
        "quote": q.select_one(".text").text.strip("\u201c\u201d"),
        "author": q.select_one(".author").text,
        "tags": ", ".join(t.text for t in q.select("a.tag")),
    } for q in soup.select("div.quote")]
    nxt = soup.select_one("li.next a")
    return rows, urljoin(url, nxt["href"]) if nxt else None


def parse_tables(soup, url):
    """Generic: extract the first HTML table on a page, else the page links."""
    table = soup.find("table")
    if table:
        head = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                keys = head if len(head) == len(cells) else [f"col{i+1}" for i in range(len(cells))]
                rows.append(dict(zip(keys, cells)))
        return rows, None
    return [{"text": a.get_text(strip=True), "url": urljoin(url, a["href"])}
            for a in soup.find_all("a", href=True) if a.get_text(strip=True)], None


SOURCES = {
    "books": ("https://books.toscrape.com/", parse_books),
    "quotes": ("https://quotes.toscrape.com/", parse_quotes),
}


def scrape(source=None, url=None, pages=1, delay=MIN_DELAY, progress=None):
    """Return a list of dict rows. Pass a named source or a custom URL."""
    pages = max(1, min(int(pages), MAX_PAGES))
    if source:
        if source not in SOURCES:
            raise ScrapeError(f"Unknown source {source!r}")
        start, parser = SOURCES[source]
    elif url:
        start, parser = url, parse_tables
        pages = 1
    else:
        raise ScrapeError("Give a source or a URL.")
    f, rows, cur = PoliteFetcher(delay), [], start
    for i in range(pages):
        if not cur:
            break
        new, cur = parser(f.get(cur), cur)
        rows += new
        if progress:
            progress(i + 1, len(rows))
    return rows
