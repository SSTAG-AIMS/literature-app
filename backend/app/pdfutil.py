# app/pdfutil.py

import os
import re
import httpx
import fitz  # PyMuPDF
import tempfile
from urllib.parse import urlparse
from typing import Optional

# --- Yardımcılar ---

_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_name(name: str) -> str:
    """
    Dosya adı için güvenli karakter seti.
    """
    name = (name or "").strip()[:200]
    name = _SAFE_CHARS.sub("_", name)
    return name or "file"


def _unique_path(dir_path: str, base_name: str) -> str:
    """
    Aynı isim varsa _1, _2 ... ekleyerek benzersiz yol döndürür.
    """
    os.makedirs(dir_path, exist_ok=True)
    stem, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".pdf"
    out = os.path.join(dir_path, stem + ext)
    c = 1
    while os.path.exists(out):
        out = os.path.join(dir_path, f"{stem}_{c}{ext}")
        c += 1
    return out


# --- İndirme API'si ---

async def download_pdf_to_dir(url: str, out_dir: str, timeout_s: int = 45) -> Optional[str]:
    """
    URL'den PDF indirir, out_dir içine güvenli ve benzersiz bir dosya adıyla kaydeder.
    Başarılı olursa dosya yolunu, aksi halde None döner.

    out_dir örn: "data/pdfs"
    """
    if not url:
        return None

    parsed = urlparse(url)
    base = os.path.basename(parsed.path) or "paper.pdf"
    base = _safe_name(base)
    if not base.lower().endswith(".pdf"):
        base += ".pdf"

    out_path = _unique_path(out_dir, base)

    # İndirme
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
            r = await client.get(url)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    # İçerik türünü kontrol et. Bazı sunucular yanlış header döndürebilir.
    ctype = (r.headers.get("content-type") or "").lower()
    is_pdf_header = r.content[:4] == b"%PDF"
    looks_like_pdf = ("pdf" in ctype) or out_path.lower().endswith(".pdf") or is_pdf_header

    if not looks_like_pdf:
        return None

    # Yaz
    try:
        with open(out_path, "wb") as f:
            f.write(r.content)
    except Exception:
        return None

    return out_path


async def download_pdf(url: str) -> Optional[str]:
    """
    Geriye dönük uyumluluk için: temp yerine proje klasöründe tutmak daha mantıklı.
    Bu nedenle varsayılan olarak 'data/pdfs' içine indirir ve yol döner.
    """
    out_dir = os.path.join("data", "pdfs")
    return await download_pdf_to_dir(url, out_dir, timeout_s=60)


# --- PDF metin çıkarma ---

def extract_text(pdf_path: str) -> str:
    """
    PDF içinden düz metin çıkarır. Şifreli veya hatalı dosyalarda boş string dönebilir.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ""

    try:
        # context manager ile güvenli aç/kapat
        with fitz.open(pdf_path) as doc:
            if doc.is_encrypted:
                # Şifreli dosyalarda metin alınamayabilir
                try:
                    doc.authenticate("")  # boş şifre dener
                except Exception:
                    return ""
            chunks = []
            for page in doc:
                try:
                    chunks.append(page.get_text())
                except Exception:
                    # Sayfa bazlı hata olursa devam et
                    continue
            return "\n".join(chunks)
    except Exception:
        return ""
