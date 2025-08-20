import httpx
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"

async def search_arxiv_async(query: str, limit: int = 5) -> list[dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max(1, int(limit)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    out = []
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(ARXIV_API, params=params)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            year = None
            published = entry.findtext("atom:published", default="", namespaces=ns)
            if published:
                try:
                    year = int(published[:4])
                except:
                    pass
            doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break
            authors = [a.findtext("atom:name", default="", namespaces=ns).strip()
                       for a in entry.findall("atom:author", ns) if a.findtext("atom:name", default="", namespaces=ns)]
            out.append({
                "title": title or None,
                "authors": authors or None,
                "year": year,
                "doi": doi,
                "url_pdf": pdf_url,
                "source": "arXiv",
                "venue": "arXiv",
                "abstract": summary or None,
            })
    return out
