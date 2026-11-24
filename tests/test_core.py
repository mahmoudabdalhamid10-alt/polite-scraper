import pytest
from bs4 import BeautifulSoup
from scraper.core import PoliteFetcher, ScrapeError, parse_books


def test_blocklist():
    for u in ["https://www.alibaba.com/x", "https://amazon.com/y", "http://localhost/z"]:
        with pytest.raises(ScrapeError):
            PoliteFetcher().check_allowed(u)


def test_parse_books():
    html = ('<article class="product_pod"><p class="star-rating Three"></p>'
            '<h3><a href="a.html" title="T">T</a></h3><p class="price_color">\u00a351.77</p>'
            '<p class="availability">In stock</p></article><li class="next"><a href="page-2.html">n</a></li>')
    rows, nxt = parse_books(BeautifulSoup(html, "html.parser"), "https://books.toscrape.com/")
    assert rows[0]["price_gbp"] == 51.77 and rows[0]["rating_1_to_5"] == 3
    assert nxt.endswith("page-2.html")
