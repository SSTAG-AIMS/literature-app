# backend/app/sources_unpaywall.py
import re
import httpx
from urllib.parse import quote
from typing import Dict, Any, Optional

_DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)

def _normalize_doi(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip()
    s = _DOI_PREFIX.sub("", s)  # "https://doi.org/..." -> pure DOI
    return s or None

async def enrich_with_unpaywall(rec: Dict[str, Any], email: str) -> None:
    """
    DOI varsa Unpaywall'dan OA linki çekip rec'i yerinde zenginleştirir.
    - url_pdf yoksa, best_oa_location.url_for_pdf veya url alanını doldurur
    - Bilgi amaçlı bazı OA alanlarını ekler (model bunları kaydetmeyebilir, sorun değil)
    """
    doi = _normalize_doi(rec.get("doi") or "")
    if not doi or not email:
        return

    url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={quote(email)}"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return
        j = r.json() or {}
    except Exception:
        return

    best = (j.get("best_oa_location") or {}) if isinstance(j, dict) else {}
    # PDF → yoksa landing page
    pdf_url = best.get("url_for_pdf") or best.get("url")
    if pdf_url and not rec.get("url_pdf"):
        rec["url_pdf"] = pdf_url

    # (opsiyonel, sadece görüntüleme/zengin bilgi için)
    rec["is_oa"] = bool(j.get("is_oa"))
    rec["oa_status"] = j.get("oa_status")
    rec["oa_version"] = (best or {}).get("version")
    rec["oa_license"] = (best or {}).get("license")
