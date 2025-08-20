import httpx

def _pick_pdf_url(w: dict) -> str | None:
    # 1) En güvenilir: best_oa_location.url_for_pdf
    bol = (w.get("best_oa_location") or {})
    if bol.get("url_for_pdf"):
        return bol["url_for_pdf"]
    # 2) open_access.open_access_locations[*].url_for_pdf
    oa = w.get("open_access") or {}
    for loc in (oa.get("open_access_locations") or []):
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"]
    # 3) host_venue . pdf_url (nadir)
    hv = w.get("host_venue") or {}
    if hv.get("pdf_url"):
        return hv["pdf_url"]
    # 4) Son çare: oa_url (çoğu zaman landing page olur)
    if oa.get("oa_url"):
        return oa["oa_url"]
    return None

async def search_openalex_async(query: str, limit=8):
    base = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": "open_access.is_oa:true",
        "per_page": limit
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(base, params=params)
        r.raise_for_status()
        out = []
        for w in r.json().get("results", []):
            title = w.get("title")
            year = w.get("publication_year")
            doi = (w.get("doi") or "").replace("https://doi.org/","").strip() if w.get("doi") else None
            abstract = (w.get("abstract") or "").replace("\n"," ").strip()
            pdf = _pick_pdf_url(w)  # <-- BURASI ÖNEMLİ
            authors = []
            for a in (w.get("authorships") or []):
                if a.get("author") and a["author"].get("display_name"):
                    authors.append(a["author"]["display_name"])
            venue = (w.get("host_venue") or {}).get("display_name")
            out.append({
                "title": title, "year": year, "doi": doi, "abstract": abstract,
                "url_pdf": pdf, "authors": authors, "source":"OpenAlex", "venue": venue
            })
        return out
