import httpx

CROSSREF_API = "https://api.crossref.org/works"

def _pick_pdf_url(item: dict) -> str | None:
    for link in item.get("link", []) or []:
        ct = (link.get("content-type") or "").lower()
        if "pdf" in ct:
            return link.get("URL")
    return None

async def search_crossref_async(query: str, limit: int = 5) -> list[dict]:
    params = {"query": query, "rows": max(1, int(limit))}
    out = []
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(CROSSREF_API, params=params)
        r.raise_for_status()
        items = (r.json().get("message", {}) or {}).get("items", []) or []
        for it in items:
            title = (it.get("title") or [None])[0]
            year = None
            try:
                parts = (it.get("published-print") or it.get("published-online") or it.get("created") or {}).get("date-parts", [[]])
                if parts and parts[0]:
                    year = parts[0][0]
            except Exception:
                pass
            authors = []
            for a in it.get("author", []) or []:
                name = " ".join([x for x in [a.get("given"), a.get("family")] if x])
                if name:
                    authors.append(name)
            doi = it.get("DOI")
            pdf_url = _pick_pdf_url(it)
            container = it.get("container-title") or []
            venue = container[0] if container else None
            out.append({
                "title": title,
                "authors": authors or None,
                "year": year,
                "doi": doi,
                "url_pdf": pdf_url,
                "source": "Crossref",
                "venue": venue,
                "abstract": None,
            })
    return out
