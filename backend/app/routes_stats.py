from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db

router = APIRouter(prefix="/stats", tags=["stats"])

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

@router.get("/keywords")
def keyword_stats(
    limit: int = Query(50, ge=5, le=500),
    min_count: int = Query(2, ge=1),
    title: str | None = None,
    author: str | None = None,
    source: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    db: Session = Depends(get_db),
):
    params = {
        "title": f"%{title}%" if title else None,
        "author": f"%{author}%" if author else None,
        "source": f"%{source}%" if source else None,
        "min_year": min_year, "max_year": max_year,
        "limit": limit, "min_count": min_count
    }
    include_author = author is not None
    cte = _filtered_cte_sql(include_author)

    sql = text(cte + """
    , kw_counts AS (
      SELECT k.term AS kw, COUNT(*)::int AS cnt
      FROM paper_keywords pk
      JOIN filtered f ON f.id = pk.paper_id
      JOIN keywords k ON k.id = pk.keyword_id
      GROUP BY k.term
    )
    SELECT
      (SELECT COUNT(*) FROM filtered)               AS paper_count,
      (SELECT COUNT(*) FROM filtered WHERE url_pdf IS NOT NULL) AS pdf_count,
      (SELECT COUNT(DISTINCT k.term)
         FROM paper_keywords pk
         JOIN filtered f ON f.id = pk.paper_id
         JOIN keywords k ON k.id = pk.keyword_id)   AS unique_keywords,
      COALESCE(json_agg(json_build_object('kw', kw, 'count', cnt)
               ORDER BY cnt DESC LIMIT :limit)
               FILTER (WHERE cnt >= :min_count), '[]'::json) AS items
    FROM kw_counts
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

@router.get("/cooccurrence")
def keyword_cooccurrence(
    limit_pairs: int = Query(200, ge=10, le=2000),
    min_pair_count: int = Query(3, ge=2),
    title: str | None = None,
    author: str | None = None,
    source: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    db: Session = Depends(get_db),
):
    params = {
        "title": f"%{title}%" if title else None,
        "author": f"%{author}%" if author else None,
        "source": f"%{source}%" if source else None,
        "min_year": min_year, "max_year": max_year,
        "limit_pairs": limit_pairs, "min_pair_count": min_pair_count
    }
    include_author = author is not None
    cte = _filtered_cte_sql(include_author)

    sql = text(cte + """
    SELECT k1.term AS kw1, k2.term AS kw2, COUNT(*)::int AS cnt
    FROM paper_keywords pk1
    JOIN paper_keywords pk2
      ON pk1.paper_id = pk2.paper_id AND pk1.keyword_id < pk2.keyword_id
    JOIN keywords k1 ON k1.id = pk1.keyword_id
    JOIN keywords k2 ON k2.id = pk2.keyword_id
    JOIN filtered f ON f.id = pk1.paper_id
    GROUP BY k1.term, k2.term
    HAVING COUNT(*) >= :min_pair_count
    ORDER BY cnt DESC
    LIMIT :limit_pairs
    """)
    rows = db.execute(sql, params).mappings().all()
    return {"pairs": rows}
