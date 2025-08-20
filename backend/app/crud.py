# backend/app/crud.py

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text

from .models import Paper, Author, PaperAuthor, Keyword, PaperKeyword

# ---- yardımcılar -------------------------------------------------------------

def _to_float_list(v) -> Optional[List[float]]:
    if not v:
        return None
    try:
        return [float(x) for x in v]
    except Exception:
        return None

def _cast_vector_literal(emb: List[float], dim: int = 768) -> str:
    # pgvector literal formatı: "[0.1,0.2,...]"
    return "[" + ",".join(str(float(x)) for x in emb) + "]"

def get_or_create_author(db: Session, name: str) -> Author:
    name = (name or "").strip()
    a = db.query(Author).filter(Author.name == name).one_or_none()
    if a:
        return a
    a = Author(name=name)
    db.add(a)
    db.flush()
    return a

def get_or_create_keyword(db: Session, term: str) -> Keyword:
    term = (term or "").strip()
    k = db.query(Keyword).filter(Keyword.term == term).one_or_none()
    if k:
        return k
    k = Keyword(term=term)
    db.add(k)
    db.flush()
    return k

# ---- çekirdek CRUD ----------------------------------------------------------

def add_paper_record(db: Session, rec: Dict[str, Any]) -> Optional[Paper]:
    """
    DOI varsa DOI, yoksa url_pdf üzerinden tekilleştirir.
    Özet/embedding varsa günceller. pgvector (embedding_v) de doldurulur.
    """
    # normalizasyon
    doi = (rec.get("doi") or "").strip() or None
    url_pdf = (rec.get("url_pdf") or "").strip() or None
    title = (rec.get("title") or "").strip() or None
    abstract = (rec.get("abstract") or None)
    source = (rec.get("source") or None)
    venue = (rec.get("venue") or None)
    year = rec.get("year")
    summary = (rec.get("summary") or None)
    emb_list = _to_float_list(rec.get("embedding"))
    authors_in = rec.get("authors") or []
    keywords_in = rec.get("keywords") or []

    # mevcut kayıt var mı?
    p = None
    if doi:
        p = db.query(Paper).filter(Paper.doi == doi).one_or_none()
    if (not p) and url_pdf:
        p = db.query(Paper).filter(Paper.url_pdf == url_pdf).one_or_none()

    # varsa güncelle (idempotent)
    if p:
        changed = False
        if title and p.title != title:
            p.title = title; changed = True
        if abstract and p.abstract != abstract:
            p.abstract = abstract; changed = True
        if source and p.source != source:
            p.source = source; changed = True
        if venue and p.venue != venue:
            p.venue = venue; changed = True
        if isinstance(year, int) and p.year != year:
            p.year = year; changed = True
        if summary and p.summary != summary:
            p.summary = summary; changed = True
        if emb_list:
            p.embedding = emb_list; changed = True

        db.add(p)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return p

        # authors/keywords ekle (eksik olanları ekle, var olanı koru)
        existing_authors = {pa.author.name for pa in p.authors}
        for idx, name in enumerate(authors_in):
            name = (name or "").strip()
            if not name or name in existing_authors:
                continue
            a = get_or_create_author(db, name)
            db.add(PaperAuthor(paper_id=p.id, author_id=a.id, author_order=idx + 1))
        existing_keywords = {pk.keyword.term for pk in p.keywords}
        for term in keywords_in:
            term = (term or "").strip()
            if not term or term in existing_keywords:
                continue
            k = get_or_create_keyword(db, term)
            db.add(PaperKeyword(paper_id=p.id, keyword_id=k.id))

        # embedding_v (pgvector) doldur/güncelle
        if emb_list:
            vec = _cast_vector_literal(emb_list)
            db.execute(
                text("UPDATE papers SET embedding_v = CAST(:vec AS vector(768)) WHERE id = :rid"),
                {"vec": vec, "rid": p.id}
            )
        return p

    # yoksa yeni oluştur
    p = Paper(
        title=title,
        abstract=abstract,
        doi=doi,
        url_pdf=url_pdf,
        source=source,
        year=year,
        venue=venue,
        summary=summary,
        embedding=emb_list
    )
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # yarış durumu: başka bir işlem önce eklediyse
        p = None
        if doi:
            p = db.query(Paper).filter(Paper.doi == doi).one_or_none()
        if (not p) and url_pdf:
            p = db.query(Paper).filter(Paper.url_pdf == url_pdf).one_or_none()
        return p

    # authors
    for idx, name in enumerate(authors_in):
        name = (name or "").strip()
        if not name:
            continue
        a = get_or_create_author(db, name)
        db.add(PaperAuthor(paper_id=p.id, author_id=a.id, author_order=idx + 1))

    # keywords
    for term in keywords_in:
        term = (term or "").strip()
        if not term:
            continue
        k = get_or_create_keyword(db, term)
        db.add(PaperKeyword(paper_id=p.id, keyword_id=k.id))

    db.flush()

    # embedding_v (pgvector) doldur
    if emb_list:
        vec = _cast_vector_literal(emb_list)
        db.execute(
            text("UPDATE papers SET embedding_v = CAST(:vec AS vector(768)) WHERE id = :rid"),
            {"vec": vec, "rid": p.id}
        )

    return p

# ---- read tarafı ------------------------------------------------------------

def list_papers(db: Session, limit: int = 50):
    rows = db.query(Paper).limit(limit).all()
    out = []
    for p in rows:
        out.append({
            "db_id": p.id,
            "title": p.title,
            "authors": [pa.author.name for pa in p.authors],
            "year": p.year,
            "source": p.source,
            "venue": p.venue,
            "url_pdf": p.url_pdf
        })
    return out

def all_papers_for_graph(db: Session):
    # küçük/orta veri için yeterli; büyürse sayfalama/filtre düşünülür
    return db.query(Paper).all()

def fetch_all_embeddings(db: Session):
    # (fallback için) Python tarafında benzerlik gerektiğinde kullanılır
    rows = db.query(Paper.id, Paper.embedding).all()
    return [(rid, emb) for rid, emb in rows if emb]
