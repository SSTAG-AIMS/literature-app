# backend/app/main.py

from fastapi import FastAPI, Depends, Query, APIRouter
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio, io, csv
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text, select, func
from pathlib import Path

from .config import settings
from .llm import (
    expand_queries,
    summarize,
    keywords,
    embed,
    sanitize_keywords,
    sanitize_summary,
)
from .sources import search_openalex_async
from .sources_dergipark import search_dergipark_async
from .sources_arxiv import search_arxiv_async
from .sources_crossref import search_crossref_async
from .pdfutil import download_pdf, extract_text
from .db import get_db
from .crud import add_paper_record, all_papers_for_graph
from .models import Paper, Author, PaperAuthor
from .ui import router as ui_router


app = FastAPI(title="Literature Discovery (PostgreSQL)")

# --- Static files (logo vs.) ---
ROOT_DIR = Path(__file__).resolve().parents[1]   # backend/
STATIC_DIR = ROOT_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# UI router
app.include_router(ui_router)

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

    # Tüm kaynaklar otomatik
    registered = [
        ("openalex",  search_openalex_async),
        ("dergipark", search_dergipark_async),
        ("arxiv",     search_arxiv_async),
        ("crossref",  search_crossref_async),
    ]

    # Alt-sorgu x kaynak başına limit
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
            # Şimdilik PDF zorunlu; PDF yoksa atla
            if not rec.get("url_pdf"):
                continue

            pdf = await download_pdf(rec["url_pdf"])
            if not pdf:
                continue
            try:
                text_content = extract_text(pdf)
            except Exception:
                text_content = rec.get("abstract", "") or rec["title"]

            base = text_content or rec.get("abstract", "") or rec["title"]

            # ---- LLM ----
            s = summarize(base)
            kws = keywords(base)

            # ---- Sanitization (kritik) ----
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
    # yeni: sıralama
    sort_by: str = Query("year", description="year | ingested"),
    sort_dir: str = Query("desc", description="asc | desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
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

    total = db.execute(
        stmt.with_only_columns(func.count(func.distinct(Paper.id)))
    ).scalar_one()

    # ---- SIRALAMA ----
    sort_by  = sort_by if sort_by in ("year", "ingested") else "year"
    sort_dir = sort_dir if sort_dir in ("asc", "desc") else "desc"

    if sort_by == "ingested":
        # Yüklenme sırası: Paper.id (desc = yeni→eski)
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
        items.append({
            "db_id": p.id,
            "title": p.title,
            "authors": [pa.author.name for pa in p.authors],
            "year": p.year,
            "source": p.source,
            "venue": p.venue,
            "url_pdf": p.url_pdf
        })

    return {"items": items, "page": page, "page_size": page_size, "total": int(total)}

# -------------------- Paper Detail (for modal) --------------------
@app.get("/paper/{paper_id}")
def paper_detail(paper_id: int, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id).one_or_none()
    if not p:
        return {"error": "not_found"}

    # Görünürde de güvenli olsun (eski kayıtlar için)
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
    db: Session = Depends(get_db)
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
        stmt = stmt.order_by(Paper.id.asc() if sort_dir=="asc" else Paper.id.desc())
    else:
        if sort_dir == "asc":
            stmt = stmt.order_by(Paper.year.asc().nullsfirst(), Paper.id.asc())
        else:
            stmt = stmt.order_by(Paper.year.desc().nullslast(), Paper.id.desc())

    rows = db.execute(stmt).unique().scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "authors", "year", "source", "venue", "doi", "url_pdf", "summary", "abstract", "keywords"])
    for p in rows:
        authors = "; ".join([pa.author.name for pa in p.authors])
        keywords_joined = "; ".join(sanitize_keywords([pk.keyword.term for pk in p.keywords]))
        w.writerow([
            p.title, authors, p.year, p.source, p.venue, p.doi, p.url_pdf,
            sanitize_summary(p.summary or ""),
            (p.abstract or "")[:2000],
            keywords_joined
        ])
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="papers.csv"'}
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
    db: Session = Depends(get_db)
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
        stmt = stmt.order_by(Paper.id.asc() if sort_dir=="asc" else Paper.id.desc())
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
        title = (p.title or "").replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")
        venue = (p.venue or "").replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")
        doi = (p.doi or "").strip()
        url = (p.url_pdf or "").strip()
        authors = " and ".join((pa.author.name or "").replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")
                               for pa in p.authors)
        year = p.year or ""
        keywords_joined = "; ".join(sanitize_keywords([pk.keyword.term for pk in p.keywords]))
        note = (p.source or "").replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")

        entry = [
            f"@article{{{key}}},",
            f"  title = {{{title}}},",
            f"  author = {{{authors}}},",
            f"  year = {{{year}}},",
            f"  journal = {{{venue}}},"
        ]
        if doi: entry.append(f"  doi = {{{doi}}},")
        if url:
            entry.append(
                "  url = {" +
                url.replace("\\","\\\\").replace("{","\\{").replace("}","\\}") +
                "},"
            )
        if note: entry.append(f"  note = {{{note}}},")
        if keywords_joined:
            k_esc = keywords_joined.replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")
            entry.append(f"  keywords = {{{k_esc}}},")
        entry.append("}\n")
        out.append("\n".join(entry))

    buf = io.StringIO("\n".join(out))
    return StreamingResponse(
        buf, media_type="application/x-bibtex",
        headers={"Content-Disposition": 'attachment; filename=\"papers.bib\"'}
    )

# -------------------- Similar (pgvector) --------------------
@app.get("/similar")
def similar(db_id: int = Query(...), topk: int = 5, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT embedding_v, embedding FROM papers WHERE id = :rid"),
        {"rid": db_id}
    ).fetchone()
    if not row:
        return {"query_id": db_id, "neighbors": []}

    emb_v, emb_arr = row
    if emb_v is None and not emb_arr:
        return {"query_id": db_id, "neighbors": []}

    # Sorgu vektörü
    if emb_v is None:
        qvec = "[" + ",".join(str(float(x)) for x in emb_arr) + "]"
    else:
        qvec = str(emb_v) if isinstance(emb_v, str) else "[" + ",".join(str(float(x)) for x in emb_v) + "]"

    rows = db.execute(text("""
        SELECT p.id, p.title, p.year, p.source, p.url_pdf, p.venue,
               (1 - (p.embedding_v <-> CAST(:qvec AS vector(768)))) AS score_approx
        FROM papers p
        WHERE p.id <> :rid AND p.embedding_v IS NOT NULL
        ORDER BY p.embedding_v <-> CAST(:qvec AS vector(768))
        LIMIT :k
    """), {"rid": db_id, "qvec": qvec, "k": topk}).fetchall()

    out = []
    for rid, title, year, source, url_pdf, venue, score in rows:
        authors = [pa.author.name for pa in db.query(Paper).filter(Paper.id == rid).one().authors]
        out.append({
            "db_id": rid,
            "score": round(float(score), 4) if score is not None else None,
            "title": title,
            "authors": authors,
            "year": year,
            "source": source,
            "url_pdf": url_pdf,
            "venue": venue
        })
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
            edges.append({"data": {"id": f"e:pa:{p.id}:{a.id}", "source": pid, "target": aid, "type": "AUTHORED_BY"}})
        for pk in p.keywords:
            k = pk.keyword
            kid = f"k:{k.id}"
            add_node(kid, k.term, "keyword")
            edges.append({"data": {"id": f"e:pk:{p.id}:{k.id}", "source": pid, "target": kid, "type": "MENTIONS"}})

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

# Postgres regex (Python string'inde \\ kaçışları çift yazıldı)
# main.py (stats bölümünde)
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
      "min_year": min_year, "max_year": max_year,
      "limit": limit, "min_count": min_count,
    }
    cte = _filtered_cte_sql(include_author_join=author is not None)

    sql = text(cte + f"""
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
""")
    row = db.execute(sql, params).first()
    items = row.items if row and row.items else []
    maxcnt = max([it["count"] for it in items], default=1)
    for it in items:
        it["weight"] = round(it["count"]/maxcnt, 4)
    return {
        "paper_count": int(row.paper_count) if row else 0,
        "pdf_count": int(row.pdf_count) if row else 0,
        "unique_keywords": int(row.unique_keywords) if row else 0,
        "keyword_stats": items
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
      "min_year": min_year, "max_year": max_year,
      "limit_pairs": limit_pairs, "min_pair_count": min_pair_count,
    }
    cte = _filtered_cte_sql(include_author_join=author is not None)

    sql = text(cte + f"""
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
    """)
    rows = db.execute(sql, params).mappings().all()
    return {"pairs": rows}

# registrasyon
app.include_router(stats_router)
