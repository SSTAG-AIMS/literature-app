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


async def download_pdf(url: str, timeout_s: int = 60) -> Optional[str]:
    """
    Arama/önizleme için: PDF'i DİSKE KALICI yazmadan indirir.
    Geçici klasöre (OS temp) indirir ve dosya yolunu döner.
    Metin çıkarımından sonra extract_text temizler.

    NOT: Diske kalıcı kaydetmek istiyorsanız download_pdf_to_dir(...) kullanın.
    """
    if not url:
        return None

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
            r = await client.get(url)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    ctype = (r.headers.get("content-type") or "").lower()
    is_pdf_header = r.content[:4] == b"%PDF"
    if not (("pdf" in ctype) or is_pdf_header):
        return None

    # OS temp içine benzersiz geçici dosya yaz
    fd, tmp_path = tempfile.mkstemp(prefix="tmp_pdfutil_", suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(r.content)
    except Exception:
        # yazarken hata olursa dosyayı temizle
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return None

    return tmp_path


# --- PDF metin çıkarma ---

def extract_text(pdf_path: str) -> str:
    """
    PDF içinden düz metin çıkarır. Şifreli veya hatalı dosyalarda boş string dönebilir.
    Eğer pdf_path bizim indirdiğimiz GEÇİCİ dosya ise, işlem sonunda otomatik siler.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ""

    text_out = ""
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
            text_out = "\n".join(chunks)
    except Exception:
        text_out = ""
    finally:
        # Eğer bizim oluşturduğumuz geçici dosyaysa temizle
        try:
            tmpdir = tempfile.gettempdir()
            base = os.path.basename(pdf_path or "")
            if pdf_path.startswith(tmpdir) and base.startswith("tmp_pdfutil_"):
                os.remove(pdf_path)
        except Exception:
            pass

    return text_out
