# backend/app/ui.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MAM Literatür Bulucu</title>
<style>
  :root { --bg:#f8f9fa; --card:#fff; --txt:#343a40; --muted:#666; --line:#ddd; --pri:#0b57d0; --priH:#0849b1;}
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; background: var(--bg); color: var(--txt); }

  /* HEADER */
  header#brand{
    display:flex; align-items:center; gap:14px;
    background: var(--card); border:1px solid var(--line);
    padding:12px 16px; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,.04);
    margin-bottom:14px;
  }
  #brand img{
    width: 52px; height: 52px; object-fit: contain;
    padding: 6px; background:#fff; border-radius:10px; border:1px solid var(--line);
  }
  #brand h1{ font-size:1.4rem; margin:0; letter-spacing:.2px; }
  #brand .tag{ color:var(--muted); font-size:.9rem; margin-top:2px; }

  /* TOP BAR */
  #top { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  input, button, select { padding: 8px; border-radius: 6px; border: 1px solid #ccc; background:#fff; }
  button { background-color: var(--pri); color: white; border: none; cursor: pointer; }
  button:hover { background-color: var(--priH); }
  button[disabled] { opacity: .6; cursor: not-allowed; }
  #status { margin-top: 10px; font-style: italic; color: #555; min-height: 22px; }
  
  /* Görselleştirme alanı */
  #graph { width: 100%; min-height: 240px; border: 1px solid var(--line); margin-top: 16px; background: var(--card); border-radius: 6px; padding: 12px; }

  /* Tablo */
  table { border-collapse: collapse; width: 100%; margin-top: 16px; background: var(--card); }
  th, td { border: 1px solid var(--line); padding: 6px; text-align: left; vertical-align: middle; }
  th { background: #f1f3f5; }
  tr:hover { background: #f8f9fa; }
  #pager { margin-top: 8px; display:flex; gap:8px; align-items:center; }
  #pager button { padding:6px 10px; }
  #empty { padding: 16px; color: var(--muted); display:none; }

  /* seçim & indirme butonları */
  th.sel, td.sel { width: 1%; text-align:center; }
  th.action, td.action { width: 1%; white-space: nowrap; text-align: right; }
  .btn-sm { padding:6px 10px; border-radius:6px; }
  .btn-ghost { background:#eef3ff; color:#0b57d0; border:1px solid #cfe; }
  .btn-ghost:hover { background:#dbe7ff; }
  .btn-plain { background:#fff; color:#0b57d0; border:1px solid #cfe; }
  .btn-plain:hover { background:#f7fbff; }

  /* Modal */
  .modal-backdrop { display:none; position:fixed; inset:0; background:rgba(0,0,0,.4); align-items:center; justify-content:center; z-index: 999; }
  .modal { width: min(960px, 96vw); max-height: 90vh; overflow:auto; background:var(--card); border-radius:10px; box-shadow:0 10px 30px rgba(0,0,0,.25); padding:16px; }
  .modal h3 { margin-top:0; }
  .muted { color:var(--muted); font-size:.9em; }
  .chip { display:inline-block; background:#e9ecef; border-radius:12px; padding:2px 8px; margin:2px; font-size:.85em; }
  .close-btn { float:right; background:#dc3545; }
  .close-btn:hover { background:#bb2d3b; }
  .sec { margin-top:12px; }
  .hr { height:1px; background:#eee; margin:12px 0; }

  /* KPI ve görselleştirme stilleri */
  .kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 12px}
  .kpi{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
  .kpi .v{font-size:22px;font-weight:700;display:block}
  .cloud{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline}
  .tag{padding:4px 10px;border-radius:999px;background:#eef;border:1px solid #dde;line-height:1}
  .bar{display:flex;align-items:center;gap:8px}
  .bar .w{height:10px;background:#cfe;flex:1;border-radius:8px}
  .bar .w>div{height:100%;background:#9fd;border-radius:8px}
  .ctrl{display:flex;flex-direction:column;gap:4px}
  .ctrl label{font-size:.8rem;color:var(--muted);margin-left:2px}

  /* İndirme araç çubuğu */
  #dlbar { display:flex; gap:8px; align-items:center; justify-content:flex-end; margin-top:8px; flex-wrap: wrap; }

  /* =========================
     Loader (hourglass) STYLES
     ========================= */

  /* Loader yerleşimi */
  .loader{display:flex;justify-content:center;align-items:center;margin:12px 0}
  .hourglass{--dur:2s;width:80px;height:80px;display:block}

  /* Animasyon atamaları (düz CSS) */
  .hourglass__glare-top,
  .hourglass__glare-bottom,
  .hourglass__model,
  .hourglass__motion-thick,
  .hourglass__motion-medium,
  .hourglass__motion-thin,
  .hourglass__sand-drop,
  .hourglass__sand-fill,
  .hourglass__sand-grain-left,
  .hourglass__sand-grain-right,
  .hourglass__sand-line-left,
  .hourglass__sand-line-right{
    animation-duration:var(--dur);
    animation-timing-function:cubic-bezier(0.83,0,0.17,1);
    animation-iteration-count:infinite;
  }

  /* Hangi elemana hangi animasyon */
  .hourglass__glare-top{animation-name:glare-top}
  .hourglass__glare-bottom{animation-name:glare-bottom}
  .hourglass__model{animation-name:hourglass-flip;transform-origin:12.25px 16.75px}
  .hourglass__motion-thick,
  .hourglass__motion-medium,
  .hourglass__motion-thin{transform-origin:26px 26px}
  .hourglass__motion-thick{animation-name:motion-thick}
  .hourglass__motion-medium{animation-name:motion-medium}
  .hourglass__motion-thin{animation-name:motion-thin}
  .hourglass__sand-drop{animation-name:sand-drop}
  .hourglass__sand-fill{animation-name:sand-fill}
  .hourglass__sand-grain-left{animation-name:sand-grain-left}
  .hourglass__sand-grain-right{animation-name:sand-grain-right}
  .hourglass__sand-line-left{animation-name:sand-line-left}
  .hourglass__sand-line-right{animation-name:sand-line-right}

  /* Keyframes (SCSS’teki ease değerlerini sabitlerle değiştirdim) */
  @keyframes hourglass-flip{from{transform:translate(13.75px,9.25px) rotate(-180deg)}24%,to{transform:translate(13.75px,9.25px) rotate(0)}}
  @keyframes glare-top{from{stroke:hsla(0,0%,100%,0)}24%,to{stroke:hsl(0,0%,100%)}}
  @keyframes glare-bottom{from{stroke:hsl(0,0%,100%)}24%,to{stroke:hsla(0,0%,100%,0)}}
  @keyframes motion-thick{
    from{animation-timing-function:cubic-bezier(0.33,0,0.67,0);stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(.67turn)}
    20%{animation-timing-function:cubic-bezier(0.33,1,0.67,1);stroke:hsl(0,0%,100%);stroke-dashoffset:141.11;transform:rotate(1turn)}
    40%,to{stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(1.33turn)}
  }
  @keyframes motion-medium{
    from,8%{animation-timing-function:cubic-bezier(0.33,0,0.67,0);stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(.5turn)}
    20%{animation-timing-function:cubic-bezier(0.33,1,0.67,1);stroke:hsl(0,0%,100%);stroke-dashoffset:147.53;transform:rotate(.83turn)}
    32%,to{stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(1.17turn)}
  }
  @keyframes motion-thin{
    from,4%{animation-timing-function:cubic-bezier(0.33,0,0.67,0);stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(.33turn)}
    24%{animation-timing-function:cubic-bezier(0.33,1,0.67,1);stroke:hsl(0,0%,100%);stroke-dashoffset:134.7;transform:rotate(.67turn)}
    44%,to{stroke:hsla(0,0%,100%,0);stroke-dashoffset:153.94;transform:rotate(1turn)}
  }
  @keyframes sand-drop{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:1}70%,to{stroke-dashoffset:-107}}
  @keyframes sand-fill{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:55}70%,to{stroke-dashoffset:-54}}
  @keyframes sand-grain-left{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:29}70%,to{stroke-dashoffset:-22}}
  @keyframes sand-grain-right{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:27}70%,to{stroke-dashoffset:-24}}
  @keyframes sand-line-left{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:53}70%,to{stroke-dashoffset:-55}}
  @keyframes sand-line-right{from,10%{animation-timing-function:cubic-bezier(.12,0,.39,0);stroke-dashoffset:14}70%,to{stroke-dashoffset:-24.5}}
</style>
</head>
<body>

  <!-- HEADER -->
  <header id="brand">
    <img src="/static/logo.png?v=2" alt="MAM Logo" onerror="this.style.opacity=.3">
    <div>
      <h1>MAM Literatür Bulucu</h1>
      <div class="tag">Akademik kaynakları tek yerden tarayın</div>
    </div>
  </header>

  <!-- TOP BAR -->
  <div id="top">
    <input id="q" placeholder="Araştırma konusu" style="flex:1;">
    <div class="ctrl" style="width:110px">
      <label for="n">Maks. PDF</label>
      <input id="n" type="number" value="8" min="2" max="50">
    </div>
    <button id="run">Ara & Topla</button>
    <button id="exportCsv">Export CSV</button>
    <button id="exportBib">Export BibTeX</button>
  </div>

  <!-- Filtre barı -->
  <div id="filters" style="display:flex; gap:8px; flex-wrap:wrap; margin: 8px 0 4px;">
    <input id="fq" placeholder="Başlıkta ara" title="Başlıkta arayın">
    <input id="fauthor" placeholder="Yazar" title="Yazar adında arayın">
    <input id="fsource" placeholder="Kaynak (örn: OpenAlex)" title="Kaynak filtreleyin">
    <input id="fy1" type="number" placeholder="Yıl ≥" style="width:110px;">
    <input id="fy2" type="number" placeholder="Yıl ≤" style="width:110px;">
    <select id="fsort" title="Sırala">
      <option value="year_desc" selected>Yıl (Azalan)</option>
      <option value="year_asc">Yıl (Artan)</option>
      <option value="ingested_desc">Yüklenme Sırası (Yeni→Eski)</option>
      <option value="ingested_asc">Yüklenme Sırası (Eski→Yeni)</option>
    </select>
    <button id="apply">Filtrele</button>
    <button id="reset">Sıfırla</button>
  </div>

  <!-- Görselleştirme kontrolleri -->
  <div id="vizbar" style="display:flex; gap:8px; flex-wrap:wrap; margin: 8px 0;">
    <div class="ctrl" style="min-width:220px">
      <label for="vizType">Görselleştirme</label>
      <select id="vizType" title="Görselleştirme türü">
        <option value="cloud" selected>Anahtar Kelime Bulutu</option>
        <option value="bar">Top Anahtar Kelimeler (Bar)</option>
      </select>
    </div>
    <div class="ctrl" style="width:110px">
      <label for="kwTopN">Top N</label>
      <input id="kwTopN" type="number" value="50" min="10" max="500" title="Gösterilecek en çok geçen N kelime">
    </div>
    <div class="ctrl" style="width:140px">
      <label for="kwMinCount">Min Frekans</label>
      <input id="kwMinCount" type="number" value="2" min="1" title="Bir kelimenin dahil olması için gereken minimum makale sayısı">
    </div>
    <div class="ctrl" style="align-self:flex-end">
      <label style="visibility:hidden">.</label>
      <button id="btnStats">Görüntüle</button>
    </div>
  </div>

  <div id="status"></div>

  <!-- LOADER: #status’un hemen altında -->
  <div id="loader" class="loader" aria-live="polite" style="display:none">
    <!-- Hourglass SVG -->
    <svg class="hourglass" viewBox="0 0 56 56" width="56" height="56" role="img" aria-label="Yükleniyor">
      <clipPath id="sand-mound-top">
        <path d="M 14.613 13.087 C 15.814 12.059 19.3 8.039 20.3 6.539 C 21.5 4.789 21.5 2.039 21.5 2.039 L 3 2.039 C 3 2.039 3 4.789 4.2 6.539 C 5.2 8.039 8.686 12.059 9.887 13.087 C 11 14.039 12.25 14.039 12.25 14.039 C 12.25 14.039 13.5 14.039 14.613 13.087 Z" />
      </clipPath>
      <clipPath id="sand-mound-bottom">
        <path d="M 14.613 20.452 C 15.814 21.48 19.3 25.5 20.3 27 C 21.5 28.75 21.5 31.5 21.5 31.5 L 3 31.5 C 3 31.5 3 28.75 4.2 27 C 5.2 25.5 8.686 21.48 9.887 20.452 C 11 19.5 12.25 19.5 12.25 19.5 C 12.25 19.5 13.5 19.5 14.613 20.452 Z" />
      </clipPath>
      <g transform="translate(2,2)">
        <g fill="none" stroke="hsl(0,0%,100%)" stroke-dasharray="153.94 153.94" stroke-dashoffset="153.94" stroke-linecap="round" transform="rotate(-90,26,26)">
          <circle class="hourglass__motion-thick" stroke-width="2.5" cx="26" cy="26" r="24.5" transform="rotate(0,26,26)" />
          <circle class="hourglass__motion-medium" stroke-width="1.75" cx="26" cy="26" r="24.5" transform="rotate(90,26,26)" />
          <circle class="hourglass__motion-thin" stroke-width="1" cx="26" cy="26" r="24.5" transform="rotate(180,26,26)" />
        </g>
        <g class="hourglass__model" transform="translate(13.75,9.25)">
          <path fill="hsl(var(--hue),90%,85%)" d="M 1.5 2 L 23 2 C 23 2 22.5 8.5 19 12 C 16 15.5 13.5 13.5 13.5 16.75 C 13.5 20 16 18 19 21.5 C 22.5 25 23 31.5 23 31.5 L 1.5 31.5 C 1.5 31.5 2 25 5.5 21.5 C 8.5 18 11 20 11 16.75 C 11 13.5 8.5 15.5 5.5 12 C 2 8.5 1.5 2 1.5 2 Z" />
          <g stroke="hsl(35,90%,90%)" stroke-linecap="round">
            <line class="hourglass__sand-grain-left" stroke-width="1" stroke-dasharray="0.25 33.75" x1="12" y1="15.75" x2="12" y2="20.75" />
            <line class="hourglass__sand-grain-right" stroke-width="1" stroke-dasharray="0.25 33.75" x1="12.5" y1="16.75" x2="12.5" y2="21.75" />
            <line class="hourglass__sand-drop" stroke-width="1" stroke-dasharray="0.5 107.5" x1="12.25" y1="18" x2="12.25" y2="31.5" />
            <line class="hourglass__sand-fill" stroke-width="1.5" stroke-dasharray="54 54" x1="12.25" y1="14.75" x2="12.25" y2="31.5" />
            <line class="hourglass__sand-line-left" stroke="hsl(35,90%,83%)" stroke-width="1" stroke-dasharray="1 107" x1="12" y1="16" x2="12" y2="31.5" />
            <line class="hourglass__sand-line-right" stroke="hsl(35,90%,83%)" stroke-width="1" stroke-dasharray="12 96" x1="12.5" y1="16" x2="12.5" y2="31.5" />
            <g fill="hsl(35,90%,90%)" stroke-width="0">
              <path clip-path="url(#sand-mound-top)" d="M 12.25 15 L 15.392 13.486 C 21.737 11.168 22.5 2 22.5 2 L 2 2.013 C 2 2.013 2.753 11.046 9.009 13.438 L 12.25 15 Z" />
              <path clip-path="url(#sand-mound-bottom)" d="M 12.25 18.5 L 15.392 20.014 C 21.737 22.332 22.5 31.5 22.5 31.5 L 2 31.487 C 2 31.487 2.753 22.454 9.009 20.062 Z" />
            </g>
          </g>
          <g fill="none" opacity="0.7" stroke-linecap="round" stroke-width="2">
            <path class="hourglass__glare-top" stroke="hsl(0,0%,100%)" d="M 19.437 3.421 C 19.437 3.421 19.671 6.454 17.914 8.846 C 16.157 11.238 14.5 11.5 14.5 11.5" />
            <path class="hourglass__glare-bottom" stroke="hsla(0,0%,100%,0)" d="M 19.437 3.421 C 19.437 3.421 19.671 6.454 17.914 8.846 C 16.157 11.238 14.5 11.5 14.5 11.5" transform="rotate(180,12.25,16.75)" />
          </g>
          <rect fill="hsl(var(--hue),90%,50%)" width="24.5" height="2" />
          <rect fill="hsl(var(--hue),90%,57.5%)" rx="0.5" ry="0.5" x="2.5" y="0.5" width="19.5" height="1" />
          <rect fill="hsl(var(--hue),90%,50%)" y="31.5" width="24.5" height="2" />
          <rect fill="hsl(var(--hue),90%,57.5%)" rx="0.5" ry="0.5" x="2.5" y="32" width="19.5" height="1" />
        </g>
      </g>
    </svg>
  </div>

  <div id="graph"></div>

  <!-- Liste üstü indirme araç çubuğu -->
  <div id="dlbar">
    <button id="selectAllPage" class="btn-sm btn-plain">Tümünü Seç (Sayfa)</button>
    <button id="clearSel" class="btn-sm btn-plain">Seçimi Temizle</button>
    <button id="dlSelectedBrowser" class="btn-sm btn-ghost">Seçilenleri İndir (Tarayıcı)</button>
    <button id="dlSelectedBg" class="btn-sm btn-ghost">Seçilenleri Arkaplanda İndir</button>
    <button id="dlAll" class="btn-sm btn-ghost">Tümünü İndir (Arkaplan)</button>
    <a id="zipLink" class="btn-sm btn-ghost" href="/export/pdfs.zip" target="_blank" rel="noopener">İndirilenleri ZIP</a>
  </div>

  <h3>📄 Makale Listesi</h3>
  <table id="tbl" aria-label="Makale listesi">
    <thead>
      <tr>
        <th class="sel">Seç</th>
        <th>Başlık</th>
        <th>Yazarlar</th>
        <th>Yıl</th>
        <th>Kaynak</th>
        <th class="action">İndir</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
  <div id="empty">Hiç kayıt bulunamadı. Filtreleri temizlemeyi deneyin.</div>
  <div id="pager"></div>

  <!-- Modal -->
  <div id="modalWrap" class="modal-backdrop">
    <div class="modal" role="dialog" aria-modal="true">
      <button class="close-btn" id="closeModal" aria-label="Kapat">Kapat</button>
      <h3 id="mTitle"></h3>
      <div class="muted" id="mMeta"></div>
      <div class="sec" id="mLinks"></div>
      <div class="sec"><strong>Özet (summary):</strong><div id="mSummary"></div></div>
      <div class="sec"><strong>Abstract:</strong><div id="mAbstract" style="white-space:pre-wrap;"></div></div>
      <div class="sec"><strong>Anahtar Kelimeler:</strong><div id="mKeywords"></div></div>
      <div class="hr"></div>
      <div class="sec"><strong>Benzer Makaleler:</strong>
        <table style="width:100%; margin-top:8px;">
          <thead><tr><th>Skor</th><th>Başlık</th><th>Yazarlar</th><th>Yıl</th><th>PDF</th></tr></thead>
          <tbody id="mSimBody"></tbody>
        </table>
        <div id="mSimEmpty" class="muted" style="margin-top:6px; display:none;">Benzer kayıt bulunamadı.</div>
      </div>
    </div>
  </div>

<script>
  let gPage = 1, gPageSize = 20;
  let fetching = false;
  const selected = new Set(); // seçili id'ler (sayfalar arası korunur)

  const $ = (id)=>document.getElementById(id);
  function qs(params){ const p = new URLSearchParams(params); return p.toString(); }

  function readFilters(){
    return {
      q: $('fq').value.trim(),
      author: $('fauthor').value.trim(),
      source: $('fsource').value.trim(),
      year_from: $('fy1').value,
      year_to: $('fy2').value,
      sort: $('fsort').value
    };
  }

  function applyToParams(base){
    const f = readFilters();
    const params = {...base};
    if(f.q) params.q = f.q;
    if(f.author) params.author = f.author;
    if(f.source) params.source = f.source;
    if(f.year_from) params.year_from = f.year_from;
    if(f.year_to) params.year_to = f.year_to;
    if(f.sort){
      const [by, dir] = f.sort.split('_'); // "ingested_desc"
      params.sort_by = by;
      params.sort_dir = dir;
    }
    return params;
  }

  function downloadViaProxy(paperId){
    const a = document.createElement('a');
    a.href = `/pdf/proxy/${paperId}`;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function showEmptyIfNeeded(items){
    $('empty').style.display = items.length ? 'none' : 'block';
  }

  // ---------- MODAL ----------
  function showModal(show){
    const el = $('modalWrap');
    el.style.display = show ? 'flex' : 'none';
    document.body.style.overflow = show ? 'hidden' : 'auto';
  }
  $('closeModal').onclick = ()=> showModal(false);
  window.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') showModal(false); });

  async function openDetails(dbId){
    const res = await fetch(`/paper/${dbId}`);
    const d = await res.json();
    if(d.error){ alert('Kayıt bulunamadı'); return; }

    $('mTitle').textContent = d.title || '(Başlık yok)';
    const meta = [];
    if((d.authors||[]).length) meta.push(d.authors.join(', '));
    if(d.year) meta.push(d.year);
    if(d.venue) meta.push(d.venue);
    if(d.source) meta.push(d.source);
    $('mMeta').textContent = meta.join(' • ');

    let links = '';
    if(d.doi){ links += `<a href="https://doi.org/${d.doi}" target="_blank" rel="noopener">DOI</a> `; }
    if(d.url_pdf){ links += `<a href="${d.url_pdf}" target="_blank" rel="noopener">Kaynak PDF</a> `; }
    links += ` <a href="/pdf/proxy/${dbId}">İndir (proxy)</a>`;
    $('mLinks').innerHTML = links || '<span class="muted">Bağlantı yok</span>';

    $('mSummary').textContent = d.summary || '(özet yok)';
    $('mAbstract').textContent = d.abstract || '(abstract yok)';

    const kw = $('mKeywords'); kw.innerHTML = '';
    (d.keywords||[]).forEach(k=>{
      const span = document.createElement('span'); span.className='chip'; span.textContent=k; kw.appendChild(span);
    });

    // Benzerler
    const simRes = await fetch(`/similar?db_id=${dbId}&topk=5`);
    const sim = await simRes.json();
    const sb = $('mSimBody'); sb.innerHTML = '';
    const empty = $('mSimEmpty');
    const arr = sim.neighbors || [];
    if(!arr.length){
      empty.style.display = 'block';
    }else{
      empty.style.display = 'none';
      arr.forEach(x=>{
        const tr = document.createElement('tr');
        const score = (x.score != null) ? (Math.round(x.score * 100) + '%') : '';
        tr.innerHTML = `
          <td>${score}</td>
          <td>${x.title || ''}</td>
          <td>${(x.authors || []).join(', ')}</td>
          <td>${x.year || ''}</td>
          <td>${x.url_pdf ? `<a href="${x.url_pdf}" target="_blank" rel="noopener">PDF</a>` : ''}</td>
        `;
        sb.appendChild(tr);
      });
    }

    showModal(true);
  }

  // ---------- GÖRSELLEŞTİRME (stats/keywords) ----------
  function collectStatsQuery(){
    const f = readFilters();
    const p = new URLSearchParams();
    if (f.q) p.set('title', f.q);
    if (f.author) p.set('author', f.author);
    if (f.source) p.set('source', f.source);
    if (f.year_from) p.set('min_year', f.year_from);
    if (f.year_to) p.set('max_year', f.year_to);
    p.set('limit', $('kwTopN').value || 50);
    p.set('min_count', $('kwMinCount').value || 2);
    return p.toString();
  }

  async function loadKeywordStats(){
    const res = await fetch('/stats/keywords?' + collectStatsQuery());
    if(!res.ok) throw new Error('İstatistik alınamadı');
    return await res.json();
  }

  function renderKPIs(host, s){
    host.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi"><span>Toplam Kayıt</span><span class="v">${s.paper_count}</span></div>
        <div class="kpi"><span>PDF’li Makale</span><span class="v">${s.pdf_count}</span></div>
        <div class="kpi"><span>Benzersiz Anahtar Kelime</span><span class="v">${s.unique_keywords}</span></div>
        <div class="kpi"><span>Gösterilen Kelime</span><span class="v">${s.keyword_stats.length}</span></div>
      </div>`;
  }

  function renderCloud(s){
    const graph = $('graph');
    graph.innerHTML = `<div id="kpis"></div><div class="cloud" id="cloud"></div>`;
    renderKPIs($('kpis'), s);

    const max = Math.max(...s.keyword_stats.map(d=>d.count), 1);
    const min = Math.min(...s.keyword_stats.map(d=>d.count), max);
    const cloud = $('cloud');

    s.keyword_stats.forEach(d=>{
      const size = Math.round(12 + (d.count - min)/(max - min || 1) * 30); // 12–42px
      const el = document.createElement('span');
      el.className = 'tag';
      el.style.fontSize = size+'px';
      el.textContent = d.kw;
      el.title = `${d.kw} • ${d.count}`;
      cloud.appendChild(el);
    });
  }

  function renderBars(s){
    const graph = $('graph');
    graph.innerHTML = `<div id="kpis"></div><div id="bars" style="display:grid;gap:8px"></div>`;
    renderKPIs($('kpis'), s);
    const max = Math.max(...s.keyword_stats.map(d=>d.count), 1);
    const bars = $('bars');

    s.keyword_stats.forEach(d=>{
      const row = document.createElement('div');
      row.className = 'bar';
      row.innerHTML = `
        <div style="width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="\${d.kw}">\${d.kw}</div>
        <div class="w"><div style="width:\${(d.count/max*100).toFixed(0)}%"></div></div>
        <div style="width:48px;text-align:right">\${d.count}</div>`;
      bars.appendChild(row);
    });
  }

  async function renderViz(){
    try{
      const s = await loadKeywordStats();
      const t = $('vizType').value;
      if (t==='bar') renderBars(s);
      else renderCloud(s);
    }catch(err){
      $('graph').innerHTML = '<div class="muted">İstatistik alınamadı.</div>';
      console.error(err);
    }
  }

  // ---------- LİSTE ----------
  async function refreshList(page=1){
    gPage = page;
    const params = applyToParams({page:gPage, page_size:gPageSize});
    const res = await fetch('/papers?' + qs(params));
    const data = await res.json();
    const items = data.items || [];
    const tb = document.querySelector('#tbl tbody');
    tb.innerHTML = '';
    showEmptyIfNeeded(items);

    items.forEach(p=>{
      const tr = document.createElement('tr');
      tr.dataset.id = p.db_id;

      // checkbox
      const tdSel = document.createElement('td'); tdSel.className = 'sel';
      const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = selected.has(p.db_id);
      cb.dataset.id = p.db_id;
      cb.addEventListener('click', (e)=>{ e.stopPropagation(); if(cb.checked) selected.add(p.db_id); else selected.delete(p.db_id); });
      tdSel.appendChild(cb);

      // hücreler
      const tdTitle = document.createElement('td'); tdTitle.textContent = p.title || '';
      const tdAuthors = document.createElement('td'); tdAuthors.textContent = (p.authors || []).join(', ');
      const tdYear = document.createElement('td'); tdYear.textContent = p.year || '';
      const tdSource = document.createElement('td'); tdSource.textContent = p.source || '';

      // aksiyonlar
      const tdAction = document.createElement('td'); tdAction.className = 'action';
      const btnDl = document.createElement('button');
      btnDl.className = 'btn-sm'; btnDl.textContent = '📥 İndir';
      btnDl.addEventListener('click', (e)=>{ e.stopPropagation(); downloadViaProxy(p.db_id); });

      const btnSave = document.createElement('button');
      btnSave.className = 'btn-sm btn-plain'; btnSave.textContent = '💾 Sunucuya Kaydet';
      btnSave.title = 'Sunucuda dosyayı sakla (zip için kullanışlı)';
      btnSave.addEventListener('click', async (e)=>{
        e.stopPropagation(); btnSave.disabled = true; btnSave.textContent = 'Kaydediliyor...';
        try{
          const r = await fetch(`/download/${p.db_id}`, { method:'POST' });
          if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail || 'İndirme hatası'); }
          btnSave.textContent = 'Kaydedildi';
        }catch(err){
          btnSave.disabled = false; btnSave.textContent = '💾 Sunucuya Kaydet';
          $('status').innerText = String(err);
        }
      });

      tdAction.append(btnDl, document.createTextNode(' '), btnSave);

      tr.append(tdSel, tdTitle, tdAuthors, tdYear, tdSource, tdAction);
      tr.style.cursor = 'pointer';
      tr.title = 'Detay ve benzerleri görmek için tıklayın';
      tr.addEventListener('click', ()=> openDetails(p.db_id));
      tb.appendChild(tr);
    });

    renderPager(data.total || 0, data.page || 1, data.page_size || gPageSize);
  }

  function renderPager(total, page, pageSize){
    const pager = $('pager');
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    pager.innerHTML = '';
    const info = document.createElement('span');
    info.textContent = `Toplam ${total} kayıt — Sayfa ${page}/${pageCount}`;
    const prev = document.createElement('button');
    prev.textContent = 'Önceki'; prev.disabled = page <= 1; prev.onclick = ()=> refreshList(page - 1);
    const next = document.createElement('button');
    next.textContent = 'Sonraki'; next.disabled = page >= pageCount; next.onclick = ()=> refreshList(page + 1);
    pager.append(info, prev, next);

    window.onkeydown = (e)=>{
      if (e.key === 'ArrowLeft' && page > 1) { refreshList(page-1); }
      if (e.key === 'ArrowRight' && page < pageCount) { refreshList(page+1); }
    };
  }

  // ---------- STATE/BUTTONS ----------
  function setBusy(busy){
    fetching = busy;
    $('run').disabled = busy;
    $('status').innerText = busy ? 'Aranıyor, PDF indiriliyor...' : '';
    $('loader').style.display = busy ? 'flex' : 'none';   // loader görünürlüğü
  }

  $('run').onclick = async ()=>{
    const topic = $('q').value.trim();
    const n = parseInt(($('n').value || '8'), 10);
    if(!topic || fetching) return;

    document.querySelector('#tbl tbody').innerHTML = '';
    $('empty').style.display = 'none';
    $('graph').innerHTML = '';
    $('status').innerText = '';

    setBusy(true);
    try{
      await fetch('/search/run',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({topic,max_results:n})
      });
      await refreshList(1);
      await renderViz();
      $('status').innerText = 'Tamamlandı.';
    }catch(e){
      $('status').innerText = 'Hata: ' + e;
    } finally {
      setBusy(false);
    }
  };

  $('q').addEventListener('keydown', (e)=>{ if(e.key==='Enter') $('run').click(); });
  ['fq','fauthor','fsource','fy1','fy2'].forEach(id=>{
    $(id).addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ $('apply').click(); }});
  });

  $('apply').onclick = ()=>{ refreshList(1); renderViz(); };
  $('reset').onclick = ()=>{
    ['fq','fauthor','fsource','fy1','fy2'].forEach(id=> $(id).value = '');
    $('fsort').value = 'year_desc';
    refreshList(1);
    renderViz();
  };
  $('fsort').addEventListener('change', ()=>{ refreshList(1); renderViz(); });

  function buildExportUrl(base){
    const params = applyToParams({});
    const q = new URLSearchParams(params).toString();
    return q ? `${base}?${q}` : base;
  }
  $('exportCsv').onclick = ()=> window.location = buildExportUrl('/export/csv');
  $('exportBib').onclick = ()=> window.location = buildExportUrl('/export/bibtex');

  // Liste üstü indirme araç çubuğu
  $('dlAll').onclick = async ()=>{
    setBusy(true); // loader'ı göster
    try{
      const r = await fetch('/download/batch', { method:'POST' });
      const j = await r.json().catch(()=> ({}));
      if(r.ok){
        $('status').innerText = `Arkaplana alındı. Sıra: ${j.queued||0}`;
      }else{
        $('status').innerText = j.detail || 'Batch indirme hatası';
      }
    }catch(e){
      $('status').innerText = 'Batch indirme hatası';
    } finally {
      setBusy(false); // loader'ı gizle
    }
  };

  $('selectAllPage').onclick = ()=>{
    document.querySelectorAll('#tbl tbody tr').forEach(tr=>{
      const id = Number(tr.dataset.id);
      const cb = tr.querySelector('input[type=checkbox]');
      if (cb) { cb.checked = true; selected.add(id); }
    });
  };
  $('clearSel').onclick = ()=>{
    selected.clear();
    document.querySelectorAll('#tbl tbody input[type=checkbox]').forEach(cb=> cb.checked = false);
  };

  $('dlSelectedBrowser').onclick = async ()=>{
    if(!selected.size){ $('status').innerText = 'Seçim yok.'; return; }
    $('status').innerText = 'Seçilenler indiriliyor (tarayıcı)...';
    const ids = Array.from(selected);
    for (let i=0;i<ids.length;i++){
      downloadViaProxy(ids[i]);
      await new Promise(r=> setTimeout(r, 250));
    }
    $('status').innerText = 'Seçilenler indirildi (başlatıldı).';
  };

  $('dlSelectedBg').onclick = async ()=>{
    if(!selected.size){ $('status').innerText = 'Seçim yok.'; return; }
    setBusy(true); // istersen seçili arkaplan için de göster
    const ids = Array.from(selected).join(',');
    try{
      const r = await fetch('/download/batch?'+new URLSearchParams({ids}), { method:'POST' });
      const j = await r.json().catch(()=> ({}));
      if(r.ok){
        $('status').innerText = `Arkaplana alındı. Sıra: ${j.queued||0}`;
      }else{
        $('status').innerText = j.detail || 'Batch indirme hatası';
      }
    }catch(e){
      $('status').innerText = 'Batch indirme hatası';
    } finally {
      setBusy(false);
    }
  };

  // Görselleştirme butonları
  $('btnStats').onclick = renderViz;
  $('vizType').addEventListener('change', renderViz);
  $('kwTopN').addEventListener('change', renderViz);
  $('kwMinCount').addEventListener('change', renderViz);

  // İlk yükleme
  (async function firstLoad(){ await refreshList(1); await renderViz(); })();
</script>
</body>
</html>
"""

@router.get("/ui", response_class=HTMLResponse)
def ui():
    return HTML
