# backend/app/main.py
import csv
import io
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
import asyncio
from pathlib import Path
from typing import List, Optional, Union, Any, Dict
from urllib.parse import quote

import httpx
import fitz  # PyMuPDF
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .crud import (
    add_paper_record,
    all_papers_for_graph,
    get_paper,
    iter_candidate_papers_for_download,
    set_pdf_path,
)
from .db import SessionLocal, get_db
from .llm import embed, expand_queries, keywords, sanitize_keywords, sanitize_summary, summarize
from .models import Author, Paper, PaperAuthor
# Not: Arama sırasında artık diske yazmayacağız; sadece explicit indirme için kullanacağız
from .pdfutil import download_pdf_to_dir
from .sources import search_openalex_async
from .sources_arxiv import search_arxiv_async
from .sources_crossref import search_crossref_async
from .sources_dergipark import search_dergipark_async
from .ui import router as ui_router

# === Abstract normalizasyonu ===
import html

app = FastAPI(title="Literature Discovery (PostgreSQL)")

# --- Static files (logo, vs.) ---
ROOT_DIR = Path(__file__).resolve().parents[1]  # backend/
STATIC_DIR = ROOT_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# UI router
app.include_router(ui_router)

# -------------------- Abstract Normalizasyonu (OpenAlex/Crossref/arXiv/DergiPark) --------------------
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)          # JATS/XML/HTML etiketlerini sök
    s = html.unescape(s)              # HTML entity çöz
    s = _WS_RE.sub(" ", s).strip()    # whitespace normalize
    return s

def _meaningful(s: str, minlen: int = 20) -> str:
    s = (s or "").strip()
    return s if len(s) >= minlen else ""

def _openalex_decode_abstract(inv_idx: Dict[str, Any]) -> str:
    try:
        pos2tok: Dict[int, str] = {}
        for tok, poss in (inv_idx or {}).items():
            for p in poss or []:
                pos2tok[int(p)] = tok
        if not pos2tok:
            return ""
        out = " ".join(pos2tok[i] for i in range(min(pos2tok), max(pos2tok)+1) if i in pos2tok)
        return _strip_html(out)
    except Exception:
        return ""

def _pick_abstract(rec: Dict[str, Any]) -> str:
    # 0) Halihazırda gelen abstract
    cur = _meaningful(_strip_html(rec.get("abstract", "")))
    if cur:
        return cur

    source = (rec.get("source") or "").lower()

    # 1) OpenAlex inverted index
    inv = rec.get("abstract_inverted_index") or rec.get("openalex_abstract_inverted_index")
    if isinstance(inv, dict):
        out = _meaningful(_openalex_decode_abstract(inv))
        if out:
            return out

    # 2) arXiv
    arxiv_sum = rec.get("summary") or rec.get("arxiv_summary")
    if ("arxiv" in source) or arxiv_sum:
        out = _meaningful(_strip_html(arxiv_sum or ""))
        if out:
            return out

    # 3) DergiPark
    dp_cand = (
        rec.get("abstract_en")
        or rec.get("en_abstract")
        or rec.get("abstract_tr")
        or rec.get("tr_abstract")
        or rec.get("abstract")
        or rec.get("oz")
        or rec.get("ozet")
        or rec.get("description")
    )
    if ("dergipark" in source) or dp_cand:
        out = _meaningful(_strip_html(dp_cand or ""))
        if out:
            return out

    # 4) Crossref (JATS/XML stringi)
    if ("crossref" in source) and rec.get("abstract"):
        out = _meaningful(_strip_html(rec["abstract"]))
        if out:
            return out

    # 5) Genel fallback
    for key in ("summary", "description"):
        if rec.get(key):
            out = _meaningful(_strip_html(rec[key]))
            if out:
                return out

    return ""

# -------------------- PDF'yi bellekte açıp metin çıkarma (disk'e kaydetmeden) --------------------
async def _fetch_pdf_text(url: str, timeout_s: int = 60) -> str:
    """
    PDF'yi indirir ama diske yazmaz; bellekte açıp metni döndürür.
    Başarısızlıkta "" döner.
    """
    if not url:
        return ""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
            r = await client.get(url)
    except Exception:
        return ""

    if r.status_code != 200 or not r.content:
        return ""

    ctype = (r.headers.get("content-type") or "").lower()
    looks_like_pdf = (r.content[:4] == b"%PDF") or ("pdf" in ctype)
    if not looks_like_pdf:
        # Bazı sunucular content-type'ı yanlış döndürür; yine de dene
        pass

    try:
        with fitz.open(stream=r.content, filetype="pdf") as doc:
            if doc.is_encrypted:
                try:
                    doc.authenticate("")
                except Exception:
                    return ""
            chunks = []
            for page in doc:
                try:
                    chunks.append(page.get_text())
                except Exception:
                    continue
            return "\n".join(chunks)
    except Exception:
        return ""

# -------------------- Health --------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "ollama": settings.ollama_url,
        "db": "postgresql",
        "static_dir": str(STATIC_DIR),
    }

# -------------------- Search & Ingest --------------------
class SearchRunIn(BaseModel):
    topic: str
    max_results: int = 20

@app.post("/search/run")
async def search_run(inp: SearchRunIn, db: Session = Depends(get_db)):
    qs: List[str] = expand_queries(inp.topic)

    registered = [
        ("openalex", search_openalex_async),
        ("dergipark", search_dergipark_async),
        ("arxiv", search_arxiv_async),
        ("crossref", search_crossref_async),
    ]

    denom = max(1, len(qs) * max(1, len(registered)))
    per_task = max(2, inp.max_results // denom or 2)

    tasks = []
    for q in qs:
        for _name, fn in registered:
            tasks.append(fn(q, limit=per_task))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates: List[dict] = []
    for r in results:
        if isinstance(r, Exception):
            print("SOURCE ERROR:", r)
            continue
        candidates.extend(r)

    processed = 0
    for rec in candidates:
        try:
            # PDF URL yoksa atla (ama diske kaydetme!)
            if not rec.get("url_pdf"):
                continue

            # ---- ABSTRACT NORMALİZASYONU ----
            new_abs = _pick_abstract(rec)
            if new_abs:
                rec["abstract"] = new_abs

            # ---- PDF metnini bellekten oku ----
            text_content = await _fetch_pdf_text(rec["url_pdf"])

            # Bellekten metin çıkmazsa abstract / başlıkla devam et
            base = text_content or rec.get("abstract", "") or rec.get("title") or ""

            # ---- LLM ----
            s = summarize(base)
            kws = keywords(base)

            # ---- Sanitization ----
            s = sanitize_summary(s)
            kws = sanitize_keywords(kws)

            # Embedding özet üzerinden
            emb = embed(s)

            rec.update({"summary": s, "keywords": kws, "embedding": emb})
            add_paper_record(db, rec)
            db.commit()
            processed += 1
            if processed >= inp.max_results:
                break
        except Exception as e:
            db.rollback()
            print("PIPELINE/DB ERROR:", e)

    return {"topic": inp.topic, "queries": qs, "processed": processed}

# -------------------- Papers (filters + pagination + sorting) --------------------
@app.get("/papers")
def papers(
    q: Optional[str] = Query(None, description="Başlıkta arama"),
    author: Optional[str] = Query(None, description="Yazar adı"),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    sort_by: str = Query("year", description="year | ingested"),
    sort_dir: str = Query("desc", description="asc | desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Paper)
    if q:
        stmt = stmt.where(Paper.title.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Paper.source == source)
    if year_from is not None:
        stmt = stmt.where(Paper.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Paper.year <= year_to)
    if author:
        stmt = (
            stmt.join(PaperAuthor, PaperAuthor.paper_id == Paper.id, isouter=True)
            .join(Author, Author.id == PaperAuthor.author_id, isouter=True)
            .where(Author.name.ilike(f"%{author}%"))
        )

    total = db.execute(stmt.with_only_columns(func.count(func.distinct(Paper.id)))).scalar_one()

    sort_by = sort_by if sort_by in ("year", "ingested") else "year"
    sort_dir = sort_dir if sort_dir in ("asc", "desc") else "desc"

    if sort_by == "ingested":
        primary = Paper.id.asc() if sort_dir == "asc" else Paper.id.desc()
        stmt = stmt.order_by(primary)
    else:  # year
        if sort_dir == "asc":
            stmt = stmt.order_by(Paper.year.asc().nullsfirst(), Paper.id.asc())
        else:
            stmt = stmt.order_by(Paper.year.desc().nullslast(), Paper.id.desc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows = db.execute(stmt).unique().scalars().all()
    items = []
    for p in rows:
        items.append(
            {
                "db_id": p.id,
                "title": p.title,
                "authors": [pa.author.name for pa in p.authors],
                "year": p.year,
                "source": p.source,
                "venue": p.venue,
                "url_pdf": p.url_pdf,
                "pdf_path": getattr(p, "pdf_path", None),
            }
        )

    return {"items": items, "page": page, "page_size": page_size, "total": int(total)}

# -------------------- Paper Detail (for modal) --------------------
@app.get("/paper/{paper_id}")
def paper_detail(paper_id: int, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id).one_or_none()
    if not p:
        return {"error": "not_found"}

    safe_summary = sanitize_summary(p.summary or "")
    kw_terms = [pk.keyword.term for pk in p.keywords]
    safe_keywords = sanitize_keywords(kw_terms)

    return {
        "db_id": p.id,
        "title": p.title,
        "authors": [pa.author.name for pa in p.authors],
        "year": p.year,
        "source": p.source,
        "venue": p.venue,
        "url_pdf": p.url_pdf,
        "doi": p.doi,
        "abstract": p.abstract,
        "summary": safe_summary,
        "keywords": safe_keywords,
        "pdf_path": getattr(p, "pdf_path", None),
    }

# -------------------- CSV Export (sorting destekli) --------------------
@app.get("/export/csv")
def export_csv(
    q: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    sort_by: str = Query("year"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    stmt = select(Paper)
    if q:
        stmt = stmt.where(Paper.title.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Paper.source == source)
    if year_from is not None:
        stmt = stmt.where(Paper.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Paper.year <= year_to)
    if author:
        stmt = (
            stmt.join(PaperAuthor, PaperAuthor.paper_id == Paper.id, isouter=True)
            .join(Author, Author.id == PaperAuthor.author_id, isouter=True)
            .where(Author.name.ilike(f"%{author}%"))
        )

    if sort_by == "ingested":
        stmt = stmt.order_by(Paper.id.asc() if sort_dir == "asc" else Paper.id.desc())
    else:
        if sort_dir == "asc":
            stmt = stmt.order_by(Paper.year.asc().nullsfirst(), Paper.id.asc())
        else:
            stmt = stmt.order_by(Paper.year.desc().nullslast(), Paper.id.desc())

    rows = db.execute(stmt).unique().scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["title", "authors", "year", "source", "venue", "doi", "url_pdf", "summary", "abstract", "keywords"]
    )
    for p in rows:
        authors = "; ".join([pa.author.name for pa in p.authors])
        keywords_joined = "; ".join(sanitize_keywords([pk.keyword.term for pk in p.keywords]))
        w.writerow(
            [
                p.title,
                authors,
                p.year,
                p.source,
                p.venue,
                p.doi,
                p.url_pdf,
                sanitize_summary(p.summary or ""),
                (p.abstract or "")[:2000],
                keywords_joined,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="papers.csv"'}
    )

# -------------------- BibTeX Export (sorting destekli) --------------------
@app.get("/export/bibtex")
def export_bibtex(
    q: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    sort_by: str = Query("year"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    stmt = select(Paper)
    if q:
        stmt = stmt.where(Paper.title.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Paper.source == source)
    if year_from is not None:
        stmt = stmt.where(Paper.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Paper.year <= year_to)
    if author:
        stmt = (
            stmt.join(PaperAuthor, PaperAuthor.paper_id == Paper.id, isouter=True)
            .join(Author, Author.id == PaperAuthor.author_id, isouter=True)
            .where(Author.name.ilike(f"%{author}%"))
        )

    if sort_by == "ingested":
        stmt = stmt.order_by(Paper.id.asc() if sort_dir == "asc" else Paper.id.desc())
    else:
        if sort_dir == "asc":
            stmt = stmt.order_by(Paper.year.asc().nullsfirst(), Paper.id.asc())
        else:
            stmt = stmt.order_by(Paper.year.desc().nullslast(), Paper.id.desc())

    rows = db.execute(stmt).unique().scalars().all()

    out = []
    for p in rows:
        key = (p.authors[0].author.name.split()[-1] if p.authors else "paper")
        key = f"{key}{p.year or 'n.d.'}-{p.id}"
        title = (p.title or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
        venue = (p.venue or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
        doi = (p.doi or "").strip()
        url = (p.url_pdf or "").strip()
        authors = " and ".join(
            (pa.author.name or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
            for pa in p.authors
        )
        year = p.year or ""
        keywords_joined = "; ".join(sanitize_keywords([pk.keyword.term for pk in p.keywords]))
        note = (p.source or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")

        entry = [
            f"@article{{{key}}},",
            f"  title = {{{title}}},",
            f"  author = {{{authors}}},",
            f"  year = {{{year}}},",
            f"  journal = {{{venue}}},",
        ]
        if doi:
            entry.append(f"  doi = {{{doi}}},")
        if url:
            entry.append("  url = {" + url.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}") + "},")
        if note:
            entry.append(f"  note = {{{note}}},")
        if keywords_joined:
            k_esc = keywords_joined.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")
            entry.append(f"  keywords = {{{k_esc}}},")
        entry.append("}\n")
        out.append("\n".join(entry))

    buf = io.StringIO("\n".join(out))
    return StreamingResponse(
        buf, media_type="application/x-bibtex", headers={"Content-Disposition": 'attachment; filename="papers.bib"'}
    )

# -------------------- Client-side indirme için: redirect & proxy --------------------
def _safe_http_header_value(s: str) -> str:
    return "".join(ch for ch in s if 32 <= ord(ch) <= 126)

def _safe_ascii_filename(base: str, fallback: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    ascii_ = re.sub(r"[^A-Za-z0-9._\- ]+", "_", ascii_)
    ascii_ = ascii_.strip(" ._-") or fallback
    return (ascii_[:120] or fallback) + ".pdf"

@app.get("/pdf/redirect/{paper_id}")
def pdf_redirect(paper_id: int, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id).one_or_none()
    if not p or not p.url_pdf:
        raise HTTPException(status_code=404, detail="PDF URL not found")
    return RedirectResponse(url=p.url_pdf, status_code=307)

@app.get("/pdf/proxy/{paper_id}")
async def pdf_proxy(paper_id: int, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id).one_or_none()
    if not p or not p.url_pdf:
        raise HTTPException(status_code=404, detail="PDF URL not found")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            r = await client.get(p.url_pdf)
    except Exception:
        raise HTTPException(status_code=502, detail="Upstream fetch failed")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream responded {r.status_code}")

    ctype = (r.headers.get("content-type") or "").lower()
    if not (r.content[:5] == b"%PDF-" or "pdf" in ctype):
        raise HTTPException(status_code=502, detail="Not a PDF")

    raw_title = (p.title or f"paper_{p.id}").replace("/", "_").replace("\\", "_").strip()
    raw_base = f"{p.id}_{raw_title}"[:200]

    ascii_name = _safe_ascii_filename(raw_base, f"paper_{p.id}")
    utf8_name = quote(raw_base + ".pdf", safe="")

    content_disposition = _safe_http_header_value(
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'
    )

    headers = {
        "Content-Disposition": content_disposition,
        "Content-Type": "application/pdf",
        "Cache-Control": "no-store",
    }

    return StreamingResponse(io.BytesIO(r.content), headers=headers, media_type="application/pdf")

# -------------------- Download: tekil / toplu / zip --------------------
@app.post("/download/{paper_id}")
async def download_single_pdf(paper_id: int, db: Session = Depends(get_db)):
    paper = get_paper(db, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if getattr(paper, "pdf_path", None):
        return {"status": "already_downloaded", "pdf_path": paper.pdf_path}
    if not paper.url_pdf:
        raise HTTPException(status_code=400, detail="No pdf_url for this paper")
    out_dir = os.path.join("data", "pdfs")
    os.makedirs(out_dir, exist_ok=True)
    path = await download_pdf_to_dir(paper.url_pdf, out_dir, timeout_s=60)
    if not path:
        raise HTTPException(status_code=502, detail="PDF download failed")
    set_pdf_path(db, paper_id, path)
    return {"status": "ok", "pdf_path": path}

async def _batch_worker(db_session_maker, ids: List[int] | None):
    db = db_session_maker()
    try:
        items = iter_candidate_papers_for_download(db, ids)
        out_dir = os.path.join("data", "pdfs")
        os.makedirs(out_dir, exist_ok=True)
        ok, fail = 0, 0
        for p in items:
            if getattr(p, "pdf_path", None):
                continue
            path = await download_pdf_to_dir(p.url_pdf, out_dir, timeout_s=60)
            if path:
                set_pdf_path(db, p.id, path)
                ok += 1
            else:
                fail += 1
        print(f"[batch-download] ok={ok} fail={fail}")
    finally:
        db.close()

def _parse_ids(ids_param: Optional[Union[str, List[str], List[int]]]) -> Optional[List[int]]:
    if ids_param is None:
        return None
    if isinstance(ids_param, list) and all(isinstance(x, int) for x in ids_param):
        return ids_param or None

    out: List[int] = []

    if isinstance(ids_param, str):
        for part in ids_param.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out or None

    if isinstance(ids_param, list):
        for elem in ids_param:
            if isinstance(elem, str):
                for part in elem.split(","):
                    part = part.strip()
                    if part.isdigit():
                        out.append(int(part))
        return out or None

    return None

@app.post("/download/batch")
async def download_batch(
    background: BackgroundTasks,
    ids: Optional[Union[str, List[str], List[int]]] = Query(default=None),
    db: Session = Depends(get_db),
):
    id_list = _parse_ids(ids)
    total = len(iter_candidate_papers_for_download(db, id_list))
    background.add_task(_batch_worker, SessionLocal, id_list)
    return {"queued": total}

@app.get("/export/pdfs.zip")
def export_pdfs_zip(db: Session = Depends(get_db)):
    papers = db.query(Paper).filter(Paper.pdf_path.isnot(None)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="No downloaded PDFs")

    tmpdir = tempfile.mkdtemp(prefix="pdfzip_")
    zip_path = os.path.join(tmpdir, "papers.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in papers:
            if not p.pdf_path or not os.path.exists(p.pdf_path):
                continue
            title = p.title or f"paper_{p.id}"
            safe = title[:120].replace("/", "_").replace("\\", "_")
            arcname = f"{p.id}_{safe}.pdf"
            z.write(p.pdf_path, arcname)

    def _iterfile():
        with open(zip_path, "rb") as f:
            yield from f
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    return StreamingResponse(
        _iterfile(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="papers.zip"'},
    )

# -------------------- Similar (pgvector varsa) --------------------
@app.get("/similar")
def similar(db_id: int = Query(...), topk: int = 5, db: Session = Depends(get_db)):
    try:
        row = db.execute(text("SELECT embedding_v, embedding FROM papers WHERE id = :rid"), {"rid": db_id}).fetchone()
    except Exception:
        return {"query_id": db_id, "neighbors": []}

    if not row:
        return {"query_id": db_id, "neighbors": []}

    emb_v, emb_arr = row
    if emb_v is None and not emb_arr:
        return {"query_id": db_id, "neighbors": []}

    if emb_v is None:
        try:
            qvec = "[" + ",".join(str(float(x)) for x in emb_arr) + "]"
        except Exception:
            return {"query_id": db_id, "neighbors": []}
    else:
        qvec = str(emb_v) if isinstance(emb_v, str) else "[" + ",".join(str(float(x)) for x in emb_v) + "]"

    try:
        rows = db.execute(
            text(
                """
            SELECT p.id, p.title, p.year, p.source, p.url_pdf, p.venue,
                   (1 - (p.embedding_v <-> CAST(:qvec AS vector(768)))) AS score_approx
            FROM papers p
            WHERE p.id <> :rid AND p.embedding_v IS NOT NULL
            ORDER BY p.embedding_v <-> CAST(:qvec AS vector(768))
            LIMIT :k
        """
            ),
            {"rid": db_id, "qvec": qvec, "k": topk},
        ).fetchall()
    except Exception:
        return {"query_id": db_id, "neighbors": []}

    out = []
    for rid, title, year, source, url_pdf, venue, score in rows:
        authors = [pa.author.name for pa in db.query(Paper).filter(Paper.id == rid).one().authors]
        out.append(
            {
                "db_id": rid,
                "score": round(float(score), 4) if score is not None else None,
                "title": title,
                "authors": authors,
                "year": year,
                "source": source,
                "url_pdf": url_pdf,
                "venue": venue,
            }
        )
    return {"query_id": db_id, "neighbors": out}

# -------------------- Graph (compat) --------------------
@app.get("/graph")
def graph(db: Session = Depends(get_db)):
    papers = all_papers_for_graph(db)
    nodes = {}
    edges = []

    def add_node(key, label, typ, extra=None):
        if key not in nodes:
            data = {"id": key, "label": label, "type": typ}
            if extra:
                data.update(extra)
            nodes[key] = {"data": data}

    for p in papers:
        pid = f"p:{p.id}"
        add_node(pid, p.title or "(no title)", "paper", {"year": p.year, "source": p.source})
        for pa in p.authors:
            a = pa.author
            aid = f"a:{a.id}"
            add_node(aid, a.name, "author")
            edges.append(
                {"data": {"id": f"e:pa:{p.id}:{a.id}", "source": pid, "target": aid, "type": "AUTHORED_BY"}}
            )
        for pk in p.keywords:
            k = pk.keyword
            kid = f"k:{k.id}"
            add_node(kid, k.term, "keyword")
            edges.append(
                {"data": {"id": f"e:pk:{p.id}:{k.id}", "source": pid, "target": kid, "type": "MENTIONS"}}
            )

    return {"nodes": list(nodes.values()), "edges": edges}

# -------------------- Keyword Stats --------------------
stats_router = APIRouter(prefix="/stats", tags=["stats"])

def _filtered_cte_sql(include_author_join: bool) -> str:
    joins = ""
    if include_author_join:
        joins = "JOIN paper_authors pa ON pa.paper_id = p.id JOIN authors a ON a.id = pa.author_id"
    return f"""
    WITH filtered AS (
      SELECT DISTINCT p.id, p.url_pdf
      FROM papers p
      {joins}
      WHERE 1=1
        AND (:title IS NULL OR p.title ILIKE :title)
        AND (:source IS NULL OR p.source ILIKE :source)
        AND (:min_year IS NULL OR p.year >= :min_year)
        AND (:max_year IS NULL OR p.year <= :max_year)
        {"AND (:author IS NULL OR a.name ILIKE :author)" if include_author_join else ""}
    )
    """

_KW_BAD_REGEX = (
    r'^(here\\s+(are|is)\\s+(the\\s+)?\\d*\\s*'
    r'(concise\\s+)?(topic\\s+)?keywords'
    r'(\\s+(extracted\\s+)?from\\s+the\\s+text)?\\s*:?\\s*)$'
)

@stats_router.get("/keywords")
def stats_keywords(
    limit: int = Query(50, ge=5, le=500),
    min_count: int = Query(2, ge=1),
    title: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    params = {
        "title": f"%{title}%" if title else None,
        "author": f"%{author}%" if author else None,
        "source": f"%{source}%" if source else None,
        "min_year": min_year,
        "max_year": max_year,
        "limit": limit,
        "min_count": min_count,
    }
    cte = _filtered_cte_sql(include_author_join=author is not None)

    sql = text(
        cte
        + f"""
, kw_counts AS (
  SELECT k.term AS kw, COUNT(*)::int AS cnt
  FROM paper_keywords pk
  JOIN filtered f ON f.id = pk.paper_id
  JOIN keywords k ON k.id = pk.keyword_id
  WHERE k.term !~* '{_KW_BAD_REGEX}'
  GROUP BY k.term
)
SELECT
  (SELECT COUNT(*) FROM filtered) AS paper_count,
  (SELECT COUNT(*) FROM filtered WHERE url_pdf IS NOT NULL) AS pdf_count,
  (SELECT COUNT(DISTINCT k.term)
     FROM paper_keywords pk
     JOIN filtered f ON f.id = pk.paper_id
     JOIN keywords k ON k.id = pk.keyword_id
     WHERE k.term !~* '{_KW_BAD_REGEX}'
  ) AS unique_keywords,
  (
    SELECT COALESCE(
      json_agg(json_build_object('kw', s.kw, 'count', s.cnt) ORDER BY s.cnt DESC),
      '[]'::json
    )
    FROM (
      SELECT kw, cnt
      FROM kw_counts
      WHERE cnt >= :min_count
      ORDER BY cnt DESC
      LIMIT :limit
    ) AS s
  ) AS items
FROM (SELECT 1) AS one
"""
    )
    row = db.execute(sql, params).first()
    items = row.items if row and row.items else []
    maxcnt = max([it["count"] for it in items], default=1)
    for it in items:
        it["weight"] = round(it["count"] / maxcnt, 4)
    return {
        "paper_count": int(row.paper_count) if row else 0,
        "pdf_count": int(row.pdf_count) if row else 0,
        "unique_keywords": int(row.unique_keywords) if row else 0,
        "keyword_stats": items,
    }

@stats_router.get("/cooccurrence")
def stats_cooccurrence(
    limit_pairs: int = Query(200, ge=10, le=2000),
    min_pair_count: int = Query(3, ge=2),
    title: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    params = {
        "title": f"%{title}%" if title else None,
        "author": f"%{author}%" if author else None,
        "source": f"%{source}%" if source else None,
        "min_year": min_year,
        "max_year": max_year,
        "limit_pairs": limit_pairs,
        "min_pair_count": min_pair_count,
    }
    cte = _filtered_cte_sql(include_author_join=author is not None)

    sql = text(
        cte
        + f"""
    SELECT k1.term AS kw1, k2.term AS kw2, COUNT(*)::int AS cnt
    FROM paper_keywords pk1
    JOIN paper_keywords pk2
      ON pk1.paper_id = pk2.paper_id AND pk1.keyword_id < pk2.keyword_id
    JOIN keywords k1 ON k1.id = pk1.keyword_id
    JOIN keywords k2 ON k2.id = pk2.keyword_id
    JOIN filtered f ON f.id = pk1.paper_id
    WHERE k1.term !~* '{_KW_BAD_REGEX}' AND k2.term !~* '{_KW_BAD_REGEX}'
    GROUP BY k1.term, k2.term
    HAVING COUNT(*) >= :min_pair_count
    ORDER BY cnt DESC
    LIMIT :limit_pairs
    """
    )
    rows = db.execute(sql, params).mappings().all()
    return {"pairs": rows}

# registrasyon
app.include_router(stats_router)
