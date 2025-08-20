import os, httpx, fitz, tempfile

async def download_pdf(url: str) -> str | None:
    if not url:
        return None
    tmpdir = tempfile.gettempdir()
    name = "lit_" + os.path.basename(url.split("?")[0] or "paper.pdf")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    path = os.path.join(tmpdir, name)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(url)
        ct = r.headers.get("content-type","").lower()
        if r.status_code == 200 and ("application/pdf" in ct or ct.endswith("+pdf")):
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    return None

def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = []
    for p in doc:
        text.append(p.get_text())
    return "\n".join(text)
