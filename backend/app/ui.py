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

  /* Progress */
  #progress { display:none; gap:8px; align-items:center; margin:8px 0; }
  #pbar { width:260px; height:10px; background:#e9ecef; border-radius:999px; overflow:hidden; }
  #pbar>div { height:100%; width:0%; background: var(--pri); }
  #pcnt { min-width:42px; text-align:right; font-variant-numeric: tabular-nums; color:#333; }
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

  <!-- PROGRESS -->
  <div id="progress">
    <div id="pbar"><div></div></div>
    <span id="pcnt">0%</span>
    <span id="ptext" class="muted"></span>
    <button id="cancelJob" class="btn-sm btn-plain">İptal</button>
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
  let gSinceId = null;            // <<< Yeni: sadece yeni kayıtlar için alt sınır id
  let pollTimer = null;           // <<< Yeni: progress timer
  let currentJobId = null;        // <<< Yeni: aktif job id
  const selected = new Set();     // seçili id'ler (sayfalar arası korunur)

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
    // <<< Yeni: yalnızca yeni eklenenleri listelemek için
    if (gSinceId != null) params.min_id = gSinceId;
    return params;
  }

async function downloadViaProxy(paperId, ev, fallbackUrl){
  if (ev) { ev.preventDefault(); ev.stopPropagation(); } // çift tetik olmasın
  try{
    const r = await fetch(`/pdf/proxy/${paperId}`);
    if(!r.ok){
      // Sunucu "Direct PDF not available" döndüyse nazik fallback
      const j = await r.json().catch(()=>null);
      if (fallbackUrl) {
        $('status').innerText = 'Doğrudan PDF bulunamadı, kaynak sayfası açılıyor...';
        window.open(fallbackUrl, '_blank', 'noopener');
      } else {
        $('status').innerText = (j?.detail || 'PDF indirilemedi.');
      }
      return;
    }
    // PDF proxy’den geldi → blob indir
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${paperId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=> URL.revokeObjectURL(url), 1000);
  }catch(err){
    $('status').innerText = 'İndirme başarısız: ' + err.message;
    if (fallbackUrl) window.open(fallbackUrl, '_blank', 'noopener');
  }
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
    // <<< Yeni: yalnız yeni eklenenlere göre istatistik
    if (gSinceId != null) p.set('min_id', gSinceId);
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
        <div style="width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${d.kw}">${d.kw}</div>
        <div class="w"><div style="width:${(d.count/max*100).toFixed(0)}%"></div></div>
        <div style="width:48px;text-align:right">${d.count}</div>`;
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
      //btnDl.addEventListener('click', (e)=>{ e.stopPropagation(); downloadViaProxy(p.db_id); });
      btnDl.addEventListener('click', (e)=> downloadViaProxy(p.db_id, e, p.url_pdf));

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

  // ---------- PROGRESS + CANCEL ----------
  function showProgress(show){
    $('progress').style.display = show ? 'flex' : 'none';
  }

  function setProgress(pct, text){
    pct = Math.max(0, Math.min(100, pct|0));
    $('pbar').firstElementChild.style.width = pct + '%';
    $('pcnt').textContent = pct + '%';
    $('ptext').textContent = text || '';
  }

  async function startPoll(jobId){
    currentJobId = jobId;
    showProgress(true);
    setProgress(0, 'Başlatılıyor...');
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(async ()=>{
      try{
        const r = await fetch(`/search/progress/${jobId}`);
        if(!r.ok) throw new Error('progress not found');
        const j = await r.json();

        // sunucu dönerse since_id'yi sabitle (güvence)
        if (j.since_id != null && gSinceId == null) gSinceId = j.since_id;

        let stageText = '';
        if (j.stage === 'fetching') {
          stageText = `Kaynaklardan sonuç toplanıyor (${j.source_done}/${j.source_total})`;
        } else if (j.stage === 'processing') {
          stageText = `Kayıtlar işleniyor (Kaydedilen: ${j.ingested}/${j.target})`;
        } else if (j.stage === 'starting') {
          stageText = 'Başlatılıyor...';
        } else if (j.stage === 'done') {
          stageText = 'Tamamlandı';
        }
        if (j.last_title) stageText += ` • Son: ${j.last_title}`;

        setProgress(j.percent ?? 0, stageText);

        if (j.status === 'done' || j.status === 'error' || j.status === 'cancelled'){
          clearInterval(pollTimer); pollTimer = null; currentJobId = null;
          showProgress(false);
          await refreshList(1);
          await renderViz();
          $('status').innerText = (j.status === 'done') ? 'Tamamlandı.' :
                                  (j.status === 'cancelled') ? 'İptal edildi.' :
                                  'Hata oluştu.';
          setBusy(false);
        }
      }catch(e){
        clearInterval(pollTimer); pollTimer = null; currentJobId = null;
        showProgress(false);
        setBusy(false);
      }
    }, 700);
  }

  $('cancelJob').onclick = async ()=>{
    if (!currentJobId) return;
    try{ await fetch(`/search/cancel/${currentJobId}`, {method:'POST'}); }catch(_){}
  };

  // ---------- STATE/BUTTONS ----------
  function setBusy(busy){
    fetching = busy;
    $('run').disabled = busy;
    $('status').innerText = busy ? 'Aranıyor, PDF indiriliyor...' : '';
  }

  $('run').onclick = async ()=>{
    const topic = $('q').value.trim();
    const n = parseInt(($('n').value || '8'), 10);
    if(!topic || fetching) return;

    // yeni arama: sonuç alanlarını temizle
    document.querySelector('#tbl tbody').innerHTML = '';
    $('empty').style.display = 'none';
    $('graph').innerHTML = '';
    $('status').innerText = '';
    gSinceId = null; // sunucudan gelecek since_id ile set edilecek

    setBusy(true);
    try{
      const r = await fetch('/search/start', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({topic, max_results:n})
      });
      if(!r.ok) throw new Error('Başlatılamadı');
      const { job_id, since_id } = await r.json();
      gSinceId = since_id;            // yeni kayıtlar için alt sınır (yalnız yeni olanlar)
      await startPoll(job_id);
    }catch(e){
      $('status').innerText = 'Hata: ' + e;
      setBusy(false);
      showProgress(false);
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
    // Not: gSinceId'yı koruyoruz; istersen burada null yaparak "tümünü göster"e dönebilirsin.
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
    }
  };

  // Görselleştirme butonları
  $('btnStats').onclick = renderViz;
  $('vizType').addEventListener('change', renderViz);
  $('kwTopN').addEventListener('change', renderViz);
  $('kwMinCount').addEventListener('change', renderViz);

  // İlk yükleme (tüm kayıtlar)
  (async function firstLoad(){ await refreshList(1); await renderViz(); })();
</script>
</body>
</html>
"""

@router.get("/ui", response_class=HTMLResponse)
def ui():
    return HTML
