# backend/app/sources_dergipark.py
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

BASE = "https://dergipark.org.tr"

def _ua():
    return {"User-Agent": "literature-app/1.0 (+https://example.local)"}

async def _get_html(client: httpx.AsyncClient, url: str) -> BeautifulSoup:
    r = await client.get(url, headers=_ua())
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

async def search_dergipark_async(query: str, limit: int = 5):
    """
    DergiPark arama: sonuç listesinde farklı tema varyasyonlarını tolere eder.
    - Başlık ve detay sayfası linki
    - Detay sayfasından PDF/DOI/yıl/yazarlar (meta) çekilir
    """
    q = quote_plus(query)
    url = f"{BASE}/tr/search?q={q}"

    out = []
    timeout = httpx.Timeout(20.0, read=20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        soup = await _get_html(client, url)

        # Sonuç listesinde başlık linkleri için birden fazla seçici dene:
        candidates = []
        # Varyasyon 1: h5.article-title a
        candidates += soup.select("h5.article-title a")
        # Varyasyon 2: a.article-title
        candidates += soup.select("a.article-title")
        # Varyasyon 3: kart tabanlı listeler
        candidates += soup.select("div.card-body h5 a[href*='/tr/']")

        seen = set()
        links = []
        for a in candidates:
            href = (a.get("href") or "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE + href
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(strip=True)
            if not title:
                continue
            links.append((title, href))
            if len(links) >= max(1, limit):
                break

        for title, art_url in links:
            # Detay sayfasına git
            try:
                s2 = await _get_html(client, art_url)
            except httpx.HTTPError:
                continue

            pdf_url, doi, year, authors = None, None, None, []

            # PDF link (indir butonu)
            pdf_a = s2.select_one('a[href*="/download/"]')
            if pdf_a:
                href2 = (pdf_a.get("href") or "").strip()
                if href2:
                    pdf_url = href2 if href2.startswith("http") else (BASE + href2)

            # DOI
            mdoi = s2.select_one('meta[name="citation_doi"]')
            if mdoi and mdoi.get("content"):
                doi = mdoi["content"].strip()

            # Yıl
            myear = s2.select_one('meta[name="citation_date"]')
            if myear and myear.get("content"):
                m = re.match(r"(\d{4})", myear["content"])
                if m:
                    year = int(m.group(1))

            # Yazarlar
            for ma in s2.select('meta[name="citation_author"]'):
                val = (ma.get("content") or "").strip()
                if val:
                    authors.append(val)

            out.append({
                "title": title,
                "authors": authors or None,
                "year": year,
                "doi": doi,
                "url_pdf": pdf_url,
                "source": "DergiPark",
                "venue": None,
                "abstract": None,
            })

    return out
