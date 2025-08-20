# app/llm.py
import re
import json
import requests
from typing import Iterable, List
from .config import settings

# --------- Boilerplate desenleri ----------
# "here are the 10 concise keywords from the text", "here are 10 concise keywords extracted from the text", vb.
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

# "Here is a summary of the text in approximately 120 words:" ve varyantları
_SUMM_BOILERPLATE = re.compile(
    r"""^\s*
        here\s+is\s+(a\s+)?summary\s+of\s+the\s+text
        (\s+in\s+approximately\s+\d+\s+words)?\s*:\s*
    """,
    re.IGNORECASE | re.VERBOSE,
)

# --------- Yardımcılar ----------
def _post_ollama_generate(prompt: str, model: str = "llama3", timeout: int = 180) -> str:
    try:
        r = requests.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        # Ollama çoğunlukla {"response": "..."} döner
        try:
            return r.json().get("response", "") if r.content else ""
        except Exception:
            return r.text or ""
    except Exception:
        return ""

def _post_ollama_embed(text: str, model: str = "nomic-embed-text", timeout: int = 120) -> List[float]:
    r = requests.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": model, "prompt": text[:8000]},
        timeout=timeout,
    )
    return r.json()["embedding"]

# --------- Sanitizers ----------
def sanitize_keywords(kws: Iterable) -> List[str]:
    """
    LLM çıktısından gerçek etiketleri süzer:
    - baştaki 'here are ... keywords:' önsözünü komple atar
    - 'comma-separated:' / 'keywords:' öneklerini keser
    - boilerplate cümleleri ve uzun/gürültülü tokenları çıkarır
    """
    # Metinse önce preface'i atıp sonra parçala
    if isinstance(kws, (str, bytes)):
        s = _KW_PREFACE.sub("", str(kws))
        s = re.sub(r'^\s*(keywords?|key\s*words?)\s*:\s*', '', s, flags=re.I)
        parts = [p.strip() for p in re.split(r'[,\n\r;]+', s) if p.strip()]
    else:
        parts = [str(x).strip() for x in (kws or []) if str(x).strip()]

    out: List[str] = []
    for k in parts:
        # 'comma-separated:' gibi önekleri at
        k = re.sub(r'^\s*comma[-\s]?separated\s*:\s*', '', k, flags=re.I)
        k = re.sub(r'^\s*(keywords?|key\s*words?)\s*:\s*', '', k, flags=re.I)
        # madde/numara kırp
        k = re.sub(r'^\s*[\-\*\d]+[\.\)\-]?\s*', '', k).strip(" '\"`·•-").strip()
        if not k: 
            continue
        # tek başına boilerplate satırıysa alma
        if _KW_BOILERPLATE.match(k):
            continue
        # aşırı uzun/gürültülü olanları at
        if len(k) > 64:
            continue
        out.append(k.lower())

    # uniq sırayı koru
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
    # "Summary:" / "Özet:" gibi yalın başlıkları da kırp (opsiyonel)
    s = re.sub(r'^\s*(summary|özet)\s*:\s*', '', s, flags=re.I)
    return s.strip()

# --------- Public API (kendi kodunun kullanacağı) ----------
def expand_queries(topic: str, n: int = 8) -> list[str]:
    # LLM'e "sadece satır satır sorgular" talimatı
    prompt = (
        f"You are an academic search assistant.\n"
        f"Expand the topic into exactly {n} precise search queries targeting open-access PDFs (arXiv/OpenAlex).\n"
        f"Use synonyms/boolean operators when helpful.\n"
        f"Topic: {topic}\n"
        f"Return ONLY the queries, one per line. No numbering, bullets, or extra text."
    )
    text = _post_ollama_generate(prompt, model="llama3", timeout=120)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # yine de numaralandırdıysa temizle
    lines = [re.sub(r'^\s*[\-\*\d]+[\.\)\-]?\s*', '', l).strip() for l in lines]
    # aşırı kısa satırları ele
    lines = [l for l in lines if len(l) > 2]
    return lines[:n]

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
    # İlk tercih: virgüller; yoksa satır bazlı, ardından sanitize
    raw_parts = [w.strip() for w in resp.split(",")] if ("," in resp) else resp.splitlines()
    return sanitize_keywords(raw_parts)

def embed(text: str) -> list[float]:
    # Özet/başlık gibi kısa ve temiz bir girdi kullanmak iyi sonuç verir
    clean = text.strip()[:8000]
    return _post_ollama_embed(clean, model="nomic-embed-text", timeout=120)
