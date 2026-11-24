# Polite Scraper

A small web app and command-line tool that collects public data and exports it to CSV or Excel, built to be a good citizen on the web.

- Checks `robots.txt` before every fetch
- Waits at least 1 second between requests to a host, hard cap of 20 pages per run
- Blocks sites whose terms forbid automated collection (Alibaba, AliExpress, Amazon, social networks)
- No personal data, no logins, no CAPTCHA tricks
- Excel-friendly CSV (UTF-8 with BOM, so Arabic text opens correctly)

## Run it

```bash
pip install -r requirements.txt
python -m scraper.server          # web UI at http://127.0.0.1:8000
python -m scraper --source books --pages 3 --out books.xlsx   # CLI
```

Built-in sources: `books` (books.toscrape.com) and `quotes` (quotes.toscrape.com), both made for scraping practice. A custom URL mode extracts the first HTML table (or the page links) from any public page that allows it.

## Tests

```bash
pip install pytest && pytest
```

## Add a source

Write a parser `parse_x(soup, url) -> (rows, next_page_url)` in `scraper/core.py` and register it in `SOURCES`.

## Responsible use

Only scrape pages you are allowed to. Read the site's terms and `robots.txt`. Do not collect personal data.

## AI assistance disclosure

This project was written with help from an AI assistant (Instinct), working on behalf of the repository owner, who directed the project. It is not solely hand-written. Please keep that in mind if you reuse it.

## License

MIT
