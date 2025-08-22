# app/llm.py
import re
import json
import requests
from typing import Iterable, List
from .config import settings

# --------- Boilerplate desenleri ----------
_KW_PREFACE = re.compile(
    r"""^\s*
        here\s+(are|is)\s+(the\s+)?         
        \d*\s*                                
        (concise\s+)?(topic\s+)?keywords     
        (\s+(extracted\s+)?from\s+the\s+text)?
        \s*:\s*                                
    """,
    re.IGNORECASE | re.VERBOSE,
)

_KW_BOILERPLATE = re.compile(
    r"""^
        here\s+(are|is)\s+(the\s+)?\d*\s*
        (concise\s+)?(topic\s+)?keywords
        (\s+(extracted\s+)?from\s+the\s+text)?
        \s*:?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SUMM_BOILERPLATE = re.compile(
    r"""^\s*
        here\s+is\s+(a\s+)?summary\s+of\s+the\s+text
        (\s+in\s+approximately\s+\d+\s+words)?\s*:\s*
    """,
    re.IGNORECASE | re.VERBOSE,
)

# --------- Yardımcı HTTP çağrıları ----------
def _post_ollama_generate(prompt: str, model: str = "llama3", timeout: int = 180) -> str:
    try:
        r = requests.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        try:
            if r.content:
                j = r.json()
                return (j.get("response") or "").strip()
            return ""
        except Exception:
            return (r.text or "").strip()
    except Exception:
        return ""

def _post_ollama_embed(text: str, model: str = "nomic-embed-text", timeout: int = 120) -> List[float]:
    try:
        r = requests.post(
            f"{settings.ollama_url}/api/embeddings",
            json={"model": model, "prompt": text[:8000]},
            timeout=timeout,
        )
        j = r.json()
        emb = j.get("embedding")
        return emb if isinstance(emb, list) else []
    except Exception:
        return []

# --------- Sanitizers ----------
def sanitize_keywords(kws: Iterable) -> List[str]:
    """
    LLM çıktısından gerçek etiketleri süzer:
    - baştaki boilerplate'i at
    - gereksiz önekleri kes
    - çok uzun/gürültülü tokenları çıkar
    """
    if isinstance(kws, (str, bytes)):
        s = _KW_PREFACE.sub("", str(kws))
        s = re.sub(r'^\s*(keywords?|key\s*words?)\s*:\s*', '', s, flags=re.I)
        parts = [p.strip() for p in re.split(r'[,\n\r;]+', s) if p.strip()]
    else:
        parts = [str(x).strip() for x in (kws or []) if str(x).strip()]

    out: List[str] = []
    for k in parts:
        k = re.sub(r'^\s*comma[-\s]?separated\s*:\s*', '', k, flags=re.I)
        k = re.sub(r'^\s*(keywords?|key\s*words?)\s*:\s*', '', k, flags=re.I)
        k = re.sub(r'^\s*[\-\*\d]+[\.\)\-]?\s*', '', k).strip(" '\"`·•-").strip()
        if not k:
            continue
        if _KW_BOILERPLATE.match(k):
            continue
        if len(k) > 64:
            continue
        out.append(k.lower())

    seen, clean = set(), []
    for k in out:
        if k not in seen:
            seen.add(k); clean.append(k)
    return clean[:20]

def sanitize_summary(text: str) -> str:
    if not text:
        return ""
    s = str(text)
    s = _SUMM_BOILERPLATE.sub("", s)
    s = re.sub(r'^\s*(summary|özet)\s*:\s*', '', s, flags=re.I)
    return s.strip()

# --------- LLM destekli normalizasyonlar ----------
_BAD_CONTEXT_WORDS = [
    # EN
    "job", "jobs", "career", "careers", "recruitment", "curriculum", "course",
    "syllabus", "program",
    # TR
    "iş", "kariyer", "ilan", "müfredat", "ders", "programı",
]

def _normalize_topic_with_llm(topic: str) -> str:
    """
    Yazım hatalarını düzelt, yalın konu döndür (fazladan metin yok).
    LLM boş/garip dönerse orijinali kullan.
    """
    t = (topic or "").strip()
    if not t:
        return ""
    prompt = (
        "Fix typos in the topic and return ONLY the corrected short phrase, "
        "no quotes and no extra text.\n"
        f"Topic: {t}"
    )
    fixed = _post_ollama_generate(prompt, model="llama3", timeout=30).strip()
    fixed = re.sub(r'[\r\n]+', ' ', fixed).strip().strip('"').strip("'")
    return fixed or t

def _drop_bad_context(q: str) -> bool:
    """Sorguda işe/ilan/müfredat vb. kelimeler varsa ele."""
    low = q.lower()
    return any(w in low for w in _BAD_CONTEXT_WORDS)

# --------- Public API ----------
def expand_queries(topic: str, n: int = 8) -> list[str]:
    """
    Akademik odaklı ve genel API'lerle uyumlu (booleansız) kısa sorgular üretir.
    - Konuyu typo-fix ile normalize eder.
    - Çok kelimeli ifadeyi tırnak içine alır.
    - Akademik pivotlar ekler (survey/review/methodology/algorithm/architecture/evaluation/…).
    - İş/ilan/müfredat bağlamlarını LLM tarafında kaçınır, sonra güvenlik için post-filter uygular.
    - Deterministik fallback'lerle her zaman n adet döndürür.
    """
    base = _normalize_topic_with_llm(topic)
    if not base:
        return []

    phrase = f"\"{base}\"" if " " in base else base

    # LLM'den çeşit iste; BOOLEANSIZ ve kısa tut.
    prompt = (
        "You are an academic search assistant for open-access literature (arXiv, OpenAlex, Crossref, DergiPark).\n"
        f"Expand the base phrase into exactly {n} SHORT queries focused on scholarly works.\n"
        "Rules:\n"
        " - Use double quotes around multiword phrases.\n"
        " - Do NOT use boolean operators (AND/OR/NOT or minus signs).\n"
        " - Add 1–3 academic pivots such as: survey, review, methodology, algorithm, architecture, evaluation, "
        "performance, optimization, applications, deep learning, machine learning, systems.\n"
        " - Avoid non-academic contexts (jobs, careers, courses, curriculum, syllabus, programs, recruitment).\n"
        "Return ONLY the queries, one per line. No numbering, no extra text.\n\n"
        f"Base phrase: {phrase}\n"
    )
    text = _post_ollama_generate(prompt, model="llama3", timeout=120)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Olası numara/madde işaretlerini temizle
    lines = [re.sub(r'^\s*[\-\*\d]+[\.\)\-]?\s*', '', l).strip() for l in lines]
    # Çok kısa olanları ele, kötü bağlamlıları düş
    lines = [l for l in lines if len(l) > 2 and not _drop_bad_context(l)]

    # Deterministik, API-dostu daraltıcı fallback'ler
    fallback = [
        f'{phrase} survey',
        f'{phrase} review',
        f'{phrase} methodology',
        f'{phrase} algorithm',
        f'{phrase} architecture',
        f'{phrase} evaluation',
        f'{phrase} "case study"',
        f'{phrase} "state of the art"',
        f'{phrase} applications',
        f'{phrase} performance',
    ]

    # Birleştir, uniq sırayı koru
    seen, out = set(), []
    for q in (lines + fallback):
        qn = q.strip()
        if not qn or qn in seen:
            continue
        seen.add(qn)
        out.append(qn)
        if len(out) >= n:
            break

    return out[:n]

def summarize(text: str, max_words: int = 120) -> str:
    prompt = (
        "Summarize the following academic text in approximately "
        f"{max_words} words.\n"
        "Output plain sentences only. Do NOT add any preface, headings, or meta text.\n\n"
        f"{text[:6000]}"
    )
    resp = _post_ollama_generate(prompt, model="llama3", timeout=180)
    return sanitize_summary(resp)

def keywords(text: str, k: int = 10) -> list[str]:
    prompt = (
        f"Extract {k} concise topic keywords from the text.\n"
        "Return ONLY a comma-separated list (no bullets, no numbering, no leading sentence).\n\n"
        f"{text[:6000]}"
    )
    resp = _post_ollama_generate(prompt, model="llama3", timeout=120)
    raw_parts = [w.strip() for w in resp.split(",")] if ("," in resp) else resp.splitlines()
    return sanitize_keywords(raw_parts)

def embed(text: str) -> list[float]:
    clean = (text or "").strip()[:8000]
    return _post_ollama_embed(clean, model="nomic-embed-text", timeout=120)
