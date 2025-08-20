from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>MAM Literatür Bulucu</title>
<style>
  :root { --bg:#f8f9fa; --card:#fff; --txt:#343a40; --muted:#666; --line:#ddd; --pri:#007bff; --priH:#0056b3;}
  * { box-sizing: border-box; }
  body { font-family: system-ui, Arial; margin: 20px; background: var(--bg); color: var(--txt); }

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

  #top { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  input, button, select { padding: 8px; border-radius: 6px; border: 1px solid #ccc; }
  button { background-color: var(--pri); color: white; border: none; cursor: pointer; }
  button:hover { background-color: var(--priH); }
  button[disabled] { opacity: .6; cursor: not-allowed; }
  #status { margin-top: 10px; font-style: italic; color: #555; min-height: 22px; }

  /* Görselleştirme alanı */
  #graph { width: 100%; min-height: 240px; border: 1px solid var(--line); margin-top: 16px; background: var(--card); border-radius: 6px; padding: 12px; }

  table { border-collapse: collapse; width: 100%; margin-top: 16px; background: var(--card); }
  th, td { border: 1px solid var(--line); padding: 6px; text-align: left; }
  th { background: #f1f3f5; }
  tr:hover { background: #f8f9fa; }
  #pager { margin-top: 8px; display:flex; gap:8px; align-items:center; }
  #pager button { padding:6px 10px; }
  #empty { padding: 16px; color: var(--muted); }

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
    <input id="fq" placeholder="Başlıkta ara">
    <input id="fauthor" placeholder="Yazar">
    <input id="fsource" placeholder="Kaynak (örn: OpenAlex)">
    <input id="fy1" type="number" placeholder="Yıl ≥" style="width:110px;">
    <input id="fy2" type="number" placeholder="Yıl ≤" style="width:110px;">
    <!-- SIRALAMA -->
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
    <label style="visibility:hidden"> </label>
    <button id="btnStats">Görüntüle</button>
  </div>
</div>


  <div id="status"></div>

  <div id="graph"></div>

  <h3>📄 Makale Listesi</h3>
  <table id="tbl">
    <thead>
      <tr><th>Başlık</th><th>Yazarlar</th><th>Yıl</th><th>Kaynak</th><th>PDF</th></tr>
    </thead>
    <tbody></tbody>
  </table>
  <div id="empty" style="display:none;">Hiç kayıt bulunamadı. Filtreleri temizlemeyi deneyin.</div>
  <div id="pager"></div>

  <!-- Modal -->
  <div id="modalWrap" class="modal-backdrop">
    <div class="modal" role="dialog" aria-modal="true">
      <button class="close-btn" id="closeModal">Kapat</button>
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

  function qs(params){ const p = new URLSearchParams(params); return p.toString(); }

  function readFilters(){
    return {
      q: document.getElementById('fq').value.trim(),
      author: document.getElementById('fauthor').value.trim(),
      source: document.getElementById('fsource').value.trim(),
      year_from: document.getElementById('fy1').value,
      year_to: document.getElementById('fy2').value,
      sort: document.getElementById('fsort').value
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

  // ---------- LISTE ----------
  async function refreshList(page=1){
    gPage = page;
    const params = applyToParams({page:gPage, page_size:gPageSize});
    const res = await fetch('/papers?' + qs(params));
    const data = await res.json();
    const items = data.items || [];
    const tb = document.querySelector('#tbl tbody');
    tb.innerHTML = '';
    document.getElementById('empty').style.display = items.length ? 'none' : 'block';
    items.forEach(p=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${p.title || ''}</td>
        <td>${(p.authors || []).join(', ')}</td>
        <td>${p.year || ''}</td>
        <td>${p.source || ''}</td>
        <td>${p.url_pdf ? `<a href="${p.url_pdf}" target="_blank" rel="noopener">PDF</a>` : ''}</td>
      `;
      tr.style.cursor = 'pointer';
      tr.title = 'Detay ve benzerleri görmek için tıklayın';
      tr.addEventListener('click', ()=> openDetails(p.db_id));
      tb.appendChild(tr);
    });
    renderPager(data.total || 0, data.page || 1, data.page_size || gPageSize);
  }

  function renderPager(total, page, pageSize){
    const pager = document.getElementById('pager');
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

  // ---------- MODAL ----------
  function showModal(show){
    const el = document.getElementById('modalWrap');
    el.style.display = show ? 'flex' : 'none';
    document.body.style.overflow = show ? 'hidden' : 'auto';
  }
  document.getElementById('closeModal').onclick = ()=> showModal(false);
  window.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') showModal(false); });

  async function openDetails(dbId){
    const res = await fetch(`/paper/${dbId}`);
    const d = await res.json();
    if(d.error){ alert('Kayıt bulunamadı'); return; }

    document.getElementById('mTitle').textContent = d.title || '(Başlık yok)';
    const meta = [];
    if((d.authors||[]).length) meta.push(d.authors.join(', '));
    if(d.year) meta.push(d.year);
    if(d.venue) meta.push(d.venue);
    if(d.source) meta.push(d.source);
    document.getElementById('mMeta').textContent = meta.join(' • ');

    let links = '';
    if(d.doi){ links += `<a href="https://doi.org/${d.doi}" target="_blank" rel="noopener">DOI</a> `; }
    if(d.url_pdf){ links += `<a href="${d.url_pdf}" target="_blank" rel="noopener">PDF</a> `; }
    document.getElementById('mLinks').innerHTML = links || '<span class="muted">Bağlantı yok</span>';

    document.getElementById('mSummary').textContent = d.summary || '(özet yok)';
    document.getElementById('mAbstract').textContent = d.abstract || '(abstract yok)';

    const kw = document.getElementById('mKeywords'); kw.innerHTML = '';
    (d.keywords||[]).forEach(k=>{
      const span = document.createElement('span'); span.className='chip'; span.textContent=k; kw.appendChild(span);
    });

    // Benzer makaleler — modal içi
    const simRes = await fetch(`/similar?db_id=${dbId}&topk=5`);
    const sim = await simRes.json();
    const sb = document.getElementById('mSimBody'); sb.innerHTML = '';
    const empty = document.getElementById('mSimEmpty');
    const arr = sim.neighbors || [];
    if(!arr.length){
      empty.style.display = 'block';
    }else{
      empty.style.display = 'none';
      arr.forEach(x=>{
        const tr = document.createElement('tr');
        const score = (x.score != null) ? Number(x.score).toFixed(4) : '';
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
    p.set('limit', document.getElementById('kwTopN').value || 50);
    p.set('min_count', document.getElementById('kwMinCount').value || 2);
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
    const graph = document.getElementById('graph');
    graph.innerHTML = `<div id="kpis"></div><div class="cloud" id="cloud"></div>`;
    renderKPIs(document.getElementById('kpis'), s);

    const max = Math.max(...s.keyword_stats.map(d=>d.count), 1);
    const min = Math.min(...s.keyword_stats.map(d=>d.count), max);
    const cloud = document.getElementById('cloud');

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
    const graph = document.getElementById('graph');
    graph.innerHTML = `<div id="kpis"></div><div id="bars" style="display:grid;gap:8px"></div>`;
    renderKPIs(document.getElementById('kpis'), s);
    const max = Math.max(...s.keyword_stats.map(d=>d.count), 1);
    const bars = document.getElementById('bars');

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
      const t = document.getElementById('vizType').value;
      if (t==='bar') renderBars(s);
      else renderCloud(s); // default cloud
    }catch(err){
      document.getElementById('graph').innerHTML = '<div class="muted">İstatistik alınamadı.</div>';
      console.error(err);
    }
  }

  // ---------- STATE/BUTTONS ----------
  function setBusy(busy){
    fetching = busy;
    document.getElementById('run').disabled = busy;
    document.getElementById('status').innerText = busy ? 'Aranıyor, PDF indiriliyor...' : '';
  }

  document.getElementById('run').onclick = async ()=>{
    const topic = document.getElementById('q').value.trim();
    const n = parseInt(document.getElementById('n').value || '8');
    if(!topic || fetching) return;

    // görünümü temizle
    document.querySelector('#tbl tbody').innerHTML = '';
    document.getElementById('empty').style.display = 'none';
    document.getElementById('graph').innerHTML = '';
    document.getElementById('status').innerText = '';

    setBusy(true);
    try{
      await fetch('/search/run',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({topic,max_results:n})
      });
      await refreshList(1);
      await renderViz();
      document.getElementById('status').innerText = 'Tamamlandı.';
    }catch(e){
      document.getElementById('status').innerText = 'Hata: ' + e;
    } finally {
      setBusy(false);
    }
  };

  document.getElementById('q').addEventListener('keydown', (e)=>{ if(e.key==='Enter') document.getElementById('run').click(); });
  ['fq','fauthor','fsource','fy1','fy2'].forEach(id=>{
    document.getElementById(id).addEventListener('keydown', (e)=>{
      if(e.key==='Enter'){ document.getElementById('apply').click(); }
    });
  });

  document.getElementById('apply').onclick = ()=>{ refreshList(1); renderViz(); };
  document.getElementById('reset').onclick = ()=>{
    ['fq','fauthor','fsource','fy1','fy2'].forEach(id=> document.getElementById(id).value = '');
    document.getElementById('fsort').value = 'year_desc';
    refreshList(1);
    renderViz();
  };
  document.getElementById('fsort').addEventListener('change', ()=>{ refreshList(1); renderViz(); });

  function buildExportUrl(base){
    const params = applyToParams({});
    const q = new URLSearchParams(params).toString();
    return q ? `${base}?${q}` : base;
  }
  document.getElementById('exportCsv').onclick = ()=> window.location = buildExportUrl('/export/csv');
  document.getElementById('exportBib').onclick = ()=> window.location = buildExportUrl('/export/bibtex');

  // Görselleştirme butonları
  document.getElementById('btnStats').onclick = renderViz;
  document.getElementById('vizType').addEventListener('change', renderViz);
  document.getElementById('kwTopN').addEventListener('change', renderViz);
  document.getElementById('kwMinCount').addEventListener('change', renderViz);

  // İlk yükleme
  refreshList(1);
  renderViz();
</script>

</body>
</html>
"""

@router.get("/ui", response_class=HTMLResponse)
def ui():
    return HTML
