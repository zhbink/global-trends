(() => {
  'use strict';
  const REGIONS = { west: { name: '欧美', color: 'var(--west)', flag: '🌎' }, jp: { name: '日本', color: 'var(--jp)', flag: '🇯🇵' }, kr: { name: '韩国', color: 'var(--kr)', flag: '🇰🇷' } };
  const CATS = ['娱乐/追星', '游戏/动漫', '体育', '科技/AI', '社会', '生活方式', '梗'];
  const state = { index: null, issue: null, date: null, region: 'all', cat: 'all', mode: localStorage.getItem('gt-mode') || 'zh', open: new Set() };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = n => n == null ? '—' : n >= 1e8 ? (n / 1e8).toFixed(1).replace(/\.0$/, '') + '亿' : n >= 1e4 ? (n / 1e4).toFixed(1).replace(/\.0$/, '') + '万' : String(n);
  const pad = n => String(n).padStart(2, '0');
  const timeStr = iso => { if (!iso) return ''; const d = new Date(iso); return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const hue = s => { let h = 0; for (const c of String(s)) h = (h * 31 + c.codePointAt(0)) % 360; return h; };

  // Display helpers: strip reply @-prefix, turn t.co links into small anchors, split 【译注】 notes out
  function cleanOrig(t) {
    t = String(t || '').replace(/^(@\w+\s+)+/, '');
    return esc(t).replace(/https:\/\/t\.co\/\w+/g, u => `<a href="${u}" target="_blank" rel="noopener" class="lbl">链接</a>`).trim();
  }
  function splitZh(z) {
    const notes = []; let main = String(z || '').replace(/【(译注|原文被截断)[：:]?([^】]*)】/g, (m, k, v) => { notes.push(k === '译注' ? v.trim() : '原文被 X 接口截断，仅翻译可见部分' + (v ? '：' + v : '')); return ''; });
    return { main: esc(main.trim()), notes };
  }
  function textBlock(o) {
    const orig = cleanOrig(o.text);
    const sameAsOrig = !o.text_zh || o.text_zh === o.text;
    if (sameAsOrig) return `<div class="txt">${orig}</div>`;
    const z = splitZh(o.text_zh);
    const notes = z.notes.map(n => `<span class="yz">译注：${esc(n)}</span>`).join('');
    if (state.mode === 'orig') return `<div class="txt"><span class="lbl">原文</span>${orig}</div>`;
    if (state.mode === 'both') return `<div class="txt"><span class="lbl">译</span>${z.main}${notes}<span class="orig"><span class="lbl">原文</span>${orig}</span></div>`;
    return `<div class="txt">${z.main}${notes}</div>`;
  }
  function who(a, iso, big) {
    const name = a.name || a.username, h = hue(a.username);
    return `<div class="who"><span class="avatar" style="background:hsl(${h} 55% 52%)">${esc([...name][0] || '?')}</span>
      <span class="name">${esc(name)}</span><span class="handle">@${esc(a.username)}</span>
      ${big && a.followers ? `<span class="fol">${fmt(a.followers)} 粉丝</span>` : ''}<span class="time">· ${timeStr(iso)}</span></div>`;
  }

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    if (p.get('date')) state.date = p.get('date');
    if (p.get('region') && (p.get('region') === 'all' || REGIONS[p.get('region')])) state.region = p.get('region');
    if (p.get('cat')) state.cat = p.get('cat');
  }
  function writeHash() {
    const p = new URLSearchParams(); p.set('date', state.date);
    if (state.region !== 'all') p.set('region', state.region);
    if (state.cat !== 'all') p.set('cat', state.cat);
    history.replaceState(null, '', '#' + p.toString());
  }

  async function loadJSON(u) { const r = await fetch(u, { cache: 'no-cache' }); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }

  async function init() {
    readHash();
    try { state.index = await loadJSON('data/index.json'); }
    catch (e) { $('#topics').innerHTML = `<div class="empty">无法加载数据索引：${esc(e.message)}</div>`; return; }
    const dates = state.index.issues.map(i => i.date);
    if (!dates.includes(state.date)) state.date = state.index.latest || dates[0];
    const sel = $('#dateSelect');
    sel.innerHTML = state.index.issues.map(i => `<option value="${i.date}">${i.date} · ${i.topic_count}题</option>`).join('');
    sel.onchange = () => go(sel.value);
    $('#prevDate').onclick = () => { const i = dates.indexOf(state.date); if (i < dates.length - 1) go(dates[i + 1]); };
    $('#nextDate').onclick = () => { const i = dates.indexOf(state.date); if (i > 0) go(dates[i - 1]); };
    document.querySelectorAll('#langMode button').forEach(b => {
      b.classList.toggle('on', b.dataset.mode === state.mode);
      b.onclick = () => { state.mode = b.dataset.mode; localStorage.setItem('gt-mode', state.mode); document.querySelectorAll('#langMode button').forEach(x => x.classList.toggle('on', x === b)); renderTopics(); };
    });
    await go(state.date);
  }

  async function go(date) {
    state.date = date; state.open.clear();
    const dates = state.index.issues.map(i => i.date), i = dates.indexOf(date);
    $('#dateSelect').value = date; $('#prevDate').disabled = i >= dates.length - 1; $('#nextDate').disabled = i <= 0;
    $('#topics').innerHTML = '<div class="loading">加载中…</div>';
    try { state.issue = await loadJSON(`data/${date}.json`); }
    catch (e) { $('#topics').innerHTML = `<div class="empty">无法加载 ${esc(date)} 的数据：${esc(e.message)}</div>`; return; }
    if (state.cat !== 'all' && !CATS.includes(state.cat)) state.cat = 'all';
    renderOverview(); renderFilters(); renderTopics(); renderLimits(); writeHash();
  }

  function renderOverview() {
    const d = state.issue, T = d.topics;
    const nP = T.reduce((a, t) => a + t.posts.length, 0), nR = T.reduce((a, t) => a + t.posts.reduce((b, p) => b + p.replies.length, 0), 0);
    const tr = d.trends_snapshot || {};
    const trNames = { US: '美国', UK: '英国', JP: '日本', KR: '韩国', WORLD: '全球' };
    const trHtml = Object.keys(tr).length ? `<div class="trendbox"><details><summary>X 趋势榜快照</summary>${Object.entries(tr).map(([k, v]) => `<div class="tl"><b>${trNames[k] || k}</b>：${esc((v || []).slice(0, 12).join(' · '))}</div>`).join('')}</details></div>` : '';
    $('#overview').innerHTML = `
      <div class="card obs"><h2>今日观察</h2><ol>${(d.observations_zh || []).map(o => `<li>${esc(o)}</li>`).join('')}</ol></div>
      <div class="card stats"><h2>本期概况</h2>
        <div class="statgrid"><div class="stat"><b>${T.length}</b><span>话题</span></div><div class="stat"><b>${nP}</b><span>热帖</span></div><div class="stat"><b>${nR}</b><span>热评</span></div></div>
        <div class="meta-line">统计窗口：${timeStr(d.window.start)} → ${timeStr(d.window.end)}（本地时间）<br>X 接口调用：${d.meta?.x_api_calls ?? '—'} 次 · 生成于 ${timeStr(d.generated_at)}</div>
        ${trHtml}
      </div>`;
  }

  function filtered() {
    return state.issue.topics.filter(t => (state.region === 'all' || t.region === state.region) && (state.cat === 'all' || t.categories.includes(state.cat)));
  }

  function renderFilters() {
    const T = state.issue.topics;
    const inCat = t => state.cat === 'all' || t.categories.includes(state.cat);
    const tabs = [['all', '全部']].concat(Object.entries(REGIONS).map(([k, v]) => [k, v.name]));
    $('#regionTabs').innerHTML = tabs.map(([k, n]) => `<button role="tab" data-r="${k}" class="${state.region === k ? 'on' : ''}">${n}<span class="n">${T.filter(t => (k === 'all' || t.region === k) && inCat(t)).length}</span></button>`).join('');
    $('#regionTabs').querySelectorAll('button').forEach(b => b.onclick = () => { state.region = b.dataset.r; renderFilters(); renderTopics(); writeHash(); });
    const inReg = t => state.region === 'all' || t.region === state.region;
    const cats = ['all', ...CATS.filter(c => T.some(t => t.categories.includes(c)))];
    $('#catChips').innerHTML = cats.map(c => (n => `<button class="chip ${state.cat === c ? 'on' : ''} ${n ? '' : 'zero'}" data-c="${esc(c)}">${c === 'all' ? '全部分类' : esc(c)} <small>${n}</small></button>`)(T.filter(t => inReg(t) && (c === 'all' || t.categories.includes(c))).length)).join('');
    $('#catChips').querySelectorAll('button').forEach(b => b.onclick = () => { state.cat = b.dataset.c; renderFilters(); renderTopics(); writeHash(); });
  }

  function renderPost(p, tid, pi) {
    const m = p.metrics, key = `${tid}:${pi}`, open = state.open.has(key);
    const reps = p.replies.map(r => `<div class="reply">${who(r.author, r.created_at)}${textBlock(r)}<div class="metrics"><span>♥ ${fmt(r.likes)}</span><a href="${esc(r.url)}" target="_blank" rel="noopener">在 X 查看 ↗</a></div></div>`).join('');
    const rnote = p.replies_note_zh ? `<div class="note">${esc(p.replies_note_zh)}</div>` : '';
    return `<article class="post">${who(p.author, p.created_at, true)}${textBlock(p)}
      ${p.note_zh ? `<div class="note">${esc(p.note_zh)}</div>` : ''}
      <div class="metrics"><span title="点赞">♥ ${fmt(m.likes)}</span><span title="转帖">⟲ ${fmt(m.reposts)}</span><span title="回复">💬 ${fmt(m.replies)}</span>${m.views != null ? `<span title="浏览">👁 ${fmt(m.views)}</span>` : ''}<a href="${esc(p.url)}" target="_blank" rel="noopener">在 X 查看 ↗</a></div>
      ${p.replies.length ? `<button class="rbtn ${open ? 'on' : ''}" data-k="${key}">${open ? '收起热评' : `查看 ${p.replies.length} 条热评`}</button><div class="replies ${open ? 'show' : ''}">${reps}${rnote}</div>` : rnote || '<div class="note">本帖未取到可用热评。</div>'}
    </article>`;
  }

  function renderTopic(t, max) {
    const R = REGIONS[t.region] || { name: t.region, color: 'var(--accent)' }, open = state.open.has(t.id);
    const pc = t.heat?.post_count, w = pc && max ? Math.max(4, Math.round(pc / max * 100)) : 0;
    return `<article class="card topic ${open ? 'open' : ''}" id="${esc(t.id)}" style="--rc:${R.color}">
      <div class="topic-main"><div class="rank">${String(t.rank).padStart(2, '0')}</div><div>
        <div class="tags"><span class="tag region">${R.flag || ''} ${R.name}</span>${t.categories.map(c => `<span class="tag">${esc(c)}</span>`).join('')}</div>
        <h3>${esc(t.title_zh)}</h3>
        <p>${esc(t.summary_zh)}</p>
        <p class="why"><b>年轻人为什么在聊：</b>${esc(t.why_youth_zh)}</p>
        <div class="heat" title="统计查询：${esc(t.heat?.query)}"><span>热度</span><div class="bar"><i style="width:${w}%"></i></div><span class="num">${fmt(pc)}</span><span>条帖子/24h</span></div>
        <div class="kw">${(t.keywords || []).map(k => `<span>${esc(String(k).replace(/^#/, ''))}</span>`).join('')}</div>
        ${t.note_zh ? `<div class="note">${esc(t.note_zh)}</div>` : ''}
      </div></div>
      <button class="expand" data-t="${esc(t.id)}">${open ? '收起热帖' : `展开 ${t.posts.length} 条热帖`} <span class="chev">⌄</span></button>
      <div class="posts ${state.mode === 'both' ? 'both' : ''}">${open ? t.posts.map((p, i) => renderPost(p, t.id, i)).join('') : ''}</div>
    </article>`;
  }

  function renderTopics() {
    const list = filtered(), box = $('#topics');
    if (!list.length) { box.innerHTML = '<div class="empty">该筛选条件下没有话题。</div>'; return; }
    const max = Math.max(...state.issue.topics.map(t => t.heat?.post_count || 0));
    const groups = state.region === 'all' ? Object.keys(REGIONS) : [state.region];
    box.innerHTML = groups.map(g => {
      const ts = list.filter(t => t.region === g); if (!ts.length) return '';
      return `<div class="region-head"><span class="dot" style="background:${REGIONS[g].color}"></span><h2>${REGIONS[g].name}</h2><small>${ts.length} 个话题</small></div>${ts.map(t => renderTopic(t, max)).join('')}`;
    }).join('');
    box.querySelectorAll('.expand').forEach(b => b.onclick = () => { const id = b.dataset.t; state.open.has(id) ? state.open.delete(id) : state.open.add(id); rerenderTopic(id, max); });
    bindReplies(box);
  }
  function rerenderTopic(id, max) {
    const t = state.issue.topics.find(x => x.id === id), el = document.getElementById(id);
    const tmp = document.createElement('div'); tmp.innerHTML = renderTopic(t, max); const nu = tmp.firstElementChild; el.replaceWith(nu);
    nu.querySelector('.expand').onclick = () => { state.open.has(id) ? state.open.delete(id) : state.open.add(id); rerenderTopic(id, max); };
    bindReplies(nu);
  }
  function bindReplies(root) {
    root.querySelectorAll('.rbtn').forEach(b => b.onclick = () => {
      const k = b.dataset.k, box = b.nextElementSibling, on = !state.open.has(k);
      on ? state.open.add(k) : state.open.delete(k);
      box.classList.toggle('show', on); b.classList.toggle('on', on);
      b.textContent = on ? '收起热评' : `查看 ${box.querySelectorAll('.reply').length} 条热评`;
    });
  }
  function renderLimits() {
    const L = state.issue.meta?.limitations_zh; if (!L?.length) return;
    $('#limits').innerHTML = L.map(x => `<li>${esc(x)}</li>`).join('') + '<li>数据仅来自 X 平台接口，未使用其他来源；无法取得的内容宁缺毋滥，不做补写。</li>';
  }
  window.addEventListener('hashchange', () => { const before = state.date; readHash(); if (state.date !== before) go(state.date); else { renderFilters(); renderTopics(); } });
  init();
})();
