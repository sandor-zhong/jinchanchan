'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors = {0:'#9cba9e',1:'#a6af9a',2:'#589c7b',3:'#5b91bc',4:'#a98cbe',5:'#c19c54'};
const storage = {
  get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Browsing still works when storage is disabled. */ } }
};
const storedFavorites = storage.get('yimo-favorites', []);
const state = {data:null, maps:{}, results:[], favorites:new Set(Array.isArray(storedFavorites) ? storedFavorites : []),
  favoriteMode:false, augments:[], heroes:{}, components:[], owned:[], contested:[], picker:null, toastTimer:null, lastLineup:null};

function portrait(hero, extra = '') {
  return `<span class="portrait ${extra}" style="--cost-color:${colors[hero.cost] || colors[1]}"><span class="fallback">${esc(hero.name.slice(0,1))}</span><img src="${esc(hero.icon)}" alt="${esc(hero.name)}" loading="lazy"></span>`;
}
function itemIcon(id, size = '') {
  const item = state.maps.items[id];
  return item ? `<img class="item-icon ${size}" src="${esc(item.icon)}" alt="${esc(item.name)}" title="${esc(item.name)}" loading="lazy">` : '';
}
function tags(traits) { return traits.map(t => `<span class="tag">${t.count || ''}${esc(t.name)}</span>`).join(''); }
function toast(message) {
  clearTimeout(state.toastTimer); $('#toast').textContent = message; $('#toast').hidden = false;
  state.toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 3300);
}
function openDialog(title, content) {
  $('#modal-title').textContent = title; $('#modal-body').innerHTML = content;
  if (!$('#modal').open) $('#modal').showModal();
  $('#modal').scrollTop = 0;
  $('#modal-body').scrollTop = 0;
}
function showView(view, updateHash = true) {
  if (!['handbook','recommend','heroes','augments','items','sources','rankings'].includes(view)) view='handbook';
  $$('.view').forEach(section => { section.hidden = section.id !== `view-${view}`; });
  $$('.nav-button').forEach(button => button.classList.toggle('active', button.dataset.view === view));
  $('#hero-banner').hidden = view !== 'handbook';
  if (updateHash) history.replaceState(null, '', `#${view}`);
  if (view === 'heroes') renderHeroes();
  if (view === 'items') renderItems();
  if (view === 'sources') renderSources();
  if (view === 'handbook') renderHandbook();
  if (view === 'augments') renderAugments();
  if (view === 'rankings') renderRankings();
  if (view === 'recommend' && !state.results.length && !$('#recommend-button').disabled) recommend();
}
function currentRequest() {
  return {portal_id:$('#portal').value || null, augment_ids:[...state.augments], hero_counts:{...state.heroes},
    component_ids:[...state.components], owned_item_ids:[...state.owned], contested_hero_ids:[...state.contested],
    level:Number($('#player-level').value), hp:Number($('#player-hp').value), gold:Number($('#player-gold').value),
    preferred_style:$('#style').value, limit:8};
}
function renderSelections() {
  $('#augment-count').textContent = `${state.augments.length} / 3`;
  $('#selected-augments').innerHTML = state.augments.map(id => {
    const a = state.maps.augments[id];
    return `<div class="selection-chip"><img src="${esc(a.icon)}" alt=""><span class="name">${esc(a.name)}</span><button type="button" class="chip-button" data-action="remove-augment" data-id="${id}" aria-label="移除${esc(a.name)}">×</button></div>`;
  }).join('');
  $('#selected-heroes').innerHTML = Object.entries(state.heroes).map(([id,count]) => {
    const h = state.maps.heroes[id];
    return `<div class="selection-chip"><img src="${esc(h.icon)}" alt=""><span class="name">${esc(h.name)}</span><button type="button" class="chip-button" data-action="hero-minus" data-id="${id}" aria-label="减少${esc(h.name)}张数">−</button><span class="counter">${count}</span><button type="button" class="chip-button" data-action="hero-plus" data-id="${id}" aria-label="增加${esc(h.name)}张数">＋</button></div>`;
  }).join('');
  const counts = state.components.reduce((a,id) => (a[id]=(a[id]||0)+1,a),{});
  $('#component-picker').innerHTML = state.data.items.filter(i => i.type === '基础装备').map(i => `<button type="button" class="component-button" data-action="add-component" data-id="${i.id}" title="添加${esc(i.name)}" aria-label="添加${esc(i.name)}，现有${counts[i.id]||0}件"><img src="${esc(i.icon)}" alt="${esc(i.name)}">${counts[i.id] ? `<span class="badge">${counts[i.id]}</span>` : ''}</button>`).join('');
  $('#selected-components').innerHTML = Object.entries(counts).map(([id,count]) => `<span class="selection-chip"><span>${esc(state.maps.items[id].name)} ×${count}</span><button type="button" class="chip-button" data-action="remove-component" data-id="${id}" aria-label="减少一件${esc(state.maps.items[id].name)}">−</button></span>`).join('');
  const ownedCounts = state.owned.reduce((a,id) => (a[id]=(a[id]||0)+1,a),{});
  $('#selected-owned').innerHTML = Object.entries(ownedCounts).map(([id,count]) => `<span class="selection-chip">${itemIcon(id)}<span>${esc(state.maps.items[id].name)}${count>1 ? ` ×${count}` : ''}</span><button type="button" class="chip-button" data-action="remove-owned" data-id="${id}" aria-label="移除一件${esc(state.maps.items[id].name)}">−</button></span>`).join('');
  $('#selected-contested').innerHTML = state.contested.map(id => `<span class="selection-chip">${esc(state.maps.heroes[id].name)}<button type="button" class="chip-button" data-action="remove-contested" data-id="${id}" aria-label="移除同行${esc(state.maps.heroes[id].name)}">×</button></span>`).join('');
  updatePortalDescription();
}
function updatePortalDescription() {
  $('#portal-description').textContent = state.maps.portals[$('#portal').value]?.description || '选择对局中的城邦或开局奇遇。';
}
function saveConditions() { storage.set('yimo-conditions', currentRequest()); }
function restoreConditions() {
  const r = storage.get('yimo-conditions', {});
  const selectIds = (values, map, max) => Array.isArray(values) ? values.filter(id => map[id]).slice(0,max) : [];
  state.augments = [...new Set(selectIds(r.augment_ids, state.maps.augments, 3))];
  state.heroes = Object.fromEntries(Object.entries(r.hero_counts || {}).filter(([id,n]) => state.maps.heroes[id] && !state.maps.heroes[id].summon && Number.isInteger(n) && n>=1 && n<=9).slice(0,25));
  state.components = selectIds(r.component_ids, state.maps.items,40).filter(id => state.maps.items[id].type==='基础装备');
  state.owned = selectIds(r.owned_item_ids, state.maps.items,20).filter(id => state.maps.items[id].type!=='基础装备');
  state.contested = [...new Set(selectIds(r.contested_hero_ids, state.maps.heroes,20))];
  $('#portal').value = state.maps.portals[r.portal_id] ? r.portal_id : '';
  for (const [field,key,min,max,fallback] of [['player-level','level',3,10,7],['player-hp','hp',1,115,80],['player-gold','gold',0,999,50]]) {
    $("#"+field).value = Number.isInteger(r[key]) && r[key]>=min && r[key]<=max ? r[key] : fallback;
  }
  $('#style').value = ['auto','reroll','level'].includes(r.preferred_style) ? r.preferred_style : 'auto';
}
function resetConditions() {
  state.augments=[]; state.heroes={}; state.components=[]; state.owned=[]; state.contested=[];
  $('#portal').value=''; $('#player-level').value=7; $('#player-hp').value=80; $('#player-gold').value=50; $('#style').value='auto';
  state.favoriteMode=false; $('#favorites-toggle').classList.remove('active'); $('#favorites-toggle').setAttribute('aria-pressed','false');
  renderSelections(); saveConditions(); recommend();
}
async function recommend() {
  const button = $('#recommend-button'); if (button.disabled) return;
  button.disabled = true; button.innerHTML = '正在推演… <span>◌</span>';
  saveConditions();
  try {
    const response = await fetch('/api/v1/recommend', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(currentRequest()),signal:AbortSignal.timeout(15000)});
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '请检查输入条件和数值范围。');
    state.results=payload.results;
    $('#result-notes').textContent=payload.notes.join(' ');
    renderResults();
  } catch (error) {
    const message = navigator.onLine ? (error.message || '推荐暂时失败，请重试。') : '当前离线，无法重新计算推荐。英雄和装备资料仍可浏览。';
    toast(message);
    $('#result-notes').textContent = `推荐未更新：${message} ${state.results.length ? '下方仍为上一次成功计算的结果。' : ''}`;
    if (!state.results.length) $('#results').innerHTML='<div class="empty-state"><h2>暂时无法推演</h2><p>检查网络后点击「为我推荐」重试，或先浏览英雄与装备资料。</p></div>';
  } finally { button.disabled=false; button.innerHTML='为我推荐 <span>↗</span>'; }
}
function card(result, position) {
  const l=result.lineup;
  const carry=state.maps.heroes[l.carry_ids[0]];
  const carryUnit=l.units.find(u=>u.hero_id===l.carry_ids[0]);
  const reasons=result.breakdown?.filter(b=>b.points>0 && b.factor!=='基础').slice(0,2) || [];
  return `<article class="lineup-card"><div class="card-top"><div class="card-title"><span class="rank">${String(position+1).padStart(2,'0')}</span><button class="card-title-button" data-action="lineup" data-id="${l.id}"><h3>${esc(l.name)}</h3></button></div>${result.score!=null ? `<div class="score"><b>${result.score}</b><small>匹配分</small></div>` : ''}</div>
    <div class="card-tags"><span class="tag gold">${l.style==='reroll' ? '追三星' : '运营'} · ${l.target_level}人口</span>${tags(l.traits.slice(0,3))}${result.conditions?.length ? '<span class="tag warning">需确认成型条件</span>' : ''}</div>
    <div class="roster">${l.units.map(u=>{const h=state.maps.heroes[u.hero_id];return `<div class="unit-tile ${u.carry?'carry':''}"><button data-action="hero" data-id="${h.id}" aria-label="查看${esc(h.name)}">${portrait(h)}</button><small>${esc(h.name)}</small></div>`;}).join('')}</div>
    <div class="reasons">${reasons.length ? reasons.map(b=>`<span class="reason">${esc(b.reason)}</span>`).join('') : '<span>官网候选阵容 · 结合来牌与装备选择</span>'}</div>
    <div class="card-bottom"><div class="core-build">${carry ? `<span>${esc(carry.name)}</span>` : ''}${(carryUnit?.item_ids||[]).map(id=>`<button class="chip-button" data-action="item" data-id="${id}" aria-label="查看${esc(state.maps.items[id].name)}">${itemIcon(id)}</button>`).join('')}</div><div class="card-actions"><button class="icon-button favorite ${state.favorites.has(l.id)?'saved':''}" data-action="favorite" data-id="${l.id}" aria-label="${state.favorites.has(l.id)?'取消收藏':'收藏'}${esc(l.name)}" aria-pressed="${state.favorites.has(l.id)}">${state.favorites.has(l.id)?'★':'☆'}</button><button class="details-button" data-action="lineup" data-id="${l.id}">查看阵容 ↗</button></div></div></article>`;
}
function renderResults() {
  const candidates = state.favoriteMode ? state.data.lineups.filter(l=>state.favorites.has(l.id)) : $('#lineup-scope').value==='all' ? state.data.lineups : null;
  let rows = candidates ? candidates.map(l=>state.results.find(r=>r.lineup.id===l.id)||{lineup:l}) : state.results;
  const query = $('#lineup-search').value.trim();
  if(query) rows=rows.filter(({lineup:l})=>l.full_name.includes(query)||l.units.some(u=>state.maps.heroes[u.hero_id].name.includes(query)));
  $('#result-count').textContent=`${rows.length} 套${state.favoriteMode?'收藏':''}`;
  $('#results').innerHTML = rows.length ? rows.map(card).join('') : query ? '<div class="empty-state"><h2>没有匹配的阵容</h2><p>试试其他英雄或羁绊，或切换到「全部官网阵容」。</p></div>' : '<div class="empty-state"><h2>画卷尚待落笔</h2><p>点击阵容右下角的 ☆ 收藏喜欢的阵容。</p></div>';
}
function toggleFavorite(id) {
  if(state.favorites.has(id)) state.favorites.delete(id); else state.favorites.add(id);
  storage.set('yimo-favorites',[...state.favorites]); renderResults();
  if ($('#modal').open && state.lastLineup===id) showLineup(id);
}
const aliases={'羊刀':'鬼索','青龙刀':'朔极','无尽':'无尽之刃','法爆':'珠光护手','饮血':'饮血剑','水银':'水银','轻语':'最后的轻语','大天使':'大天使之杖','帽子':'灭世者','狂徒':'狂徒铠甲','反甲':'棘刺背心','龙牙':'巨龙之爪'};
function itemMatches(item,q) { const translated=aliases[q.toLowerCase()]||q; return !q || item.name.includes(translated) || item.description.includes(translated); }
function canCraft(item) {
  const counts=state.components.reduce((a,id)=>(a[id]=(a[id]||0)+1,a),{});
  return item.components.length>0 && item.components.every(id=>{counts[id]=(counts[id]||0)-1;return counts[id]>=0;});
}
function recipe(item) { return item.components.length ? item.components.map(itemIcon).join('<span>＋</span>') : `<span>${esc(item.type==='基础装备'?'基础装备':'无法通过常规散件合成')}</span>`; }
function showPicker(kind) {
  state.picker={kind,q:'',tier:''};
  const titles={augments:'选择强化符文',heroes:'添加当前来牌',owned:'添加已有成装 / 纹章',contested:'标记同行主 C'};
  openDialog(titles[kind],`<div class="picker-toolbar"><input id="picker-search" type="search" placeholder="输入名字搜索" aria-label="搜索选项">${kind==='augments'?'<select id="picker-tier" aria-label="符文等级"><option value="">全部等级</option><option value="1">白银</option><option value="2">黄金</option><option value="3">棱彩</option></select>':''}</div><div id="picker-options" class="picker-list"></div><div class="picker-footer"><span id="picker-help"></span><button class="primary" data-action="close-modal">选择完成</button></div>`);
  renderPicker(); $('#picker-search').focus();
}
function renderPicker() {
  if(!state.picker) return;
  const {kind,q,tier}=state.picker;
  let rows=kind==='augments'?state.data.augments:kind==='owned'?state.data.items.filter(i=>!['基础装备','-1'].includes(i.type)):state.data.heroes.filter(h=>!h.summon && !h.form);
  rows=rows.filter(x=>(kind==='owned'?itemMatches(x,q):x.name.includes(q)) && (!tier || x.tier===Number(tier)));
  $('#picker-options').innerHTML=rows.map(x=>{
    const selected=kind==='augments'?state.augments.includes(x.id):kind==='heroes'?!!state.heroes[x.id]:kind==='contested'?state.contested.includes(x.id):state.owned.includes(x.id);
    const sub=kind==='augments'?['','白银','黄金','棱彩'][x.tier]:kind==='owned'?x.type:`${x.cost}费 · ${x.traits.map(t=>t.name).join(' ')}`;
    return `<button class="picker-entry ${selected?'active':''}" data-action="pick-entry" data-id="${x.id}" title="${esc(x.description||x.name)}"><img src="${esc(x.icon)}" alt=""><span><strong>${esc(x.name)}</strong><small>${esc(sub)}</small></span>${selected?'<span class="selected-marker">✓</span>':''}</button>`;
  }).join('')||'<div class="empty-state">没有匹配的资料</div>';
  $('#picker-help').textContent=kind==='augments'?`已选择 ${state.augments.length} / 3。再次点击可取消。`:kind==='owned'?'每次点击添加 1 件，相同装备可重复添加。':kind==='heroes'?'点击添加 1 张；张数可在条件面板调整。':'再次点击可取消同行标记。';
}
function pickEntry(id) {
  const kind=state.picker?.kind;
  if(kind==='augments') {
    if(state.augments.includes(id)) state.augments=state.augments.filter(a=>a!==id);
    else if(state.augments.length<3) state.augments.push(id); else return toast('最多选择 3 个强化符文。');
  } else if(kind==='heroes') {
    if(!state.heroes[id] && Object.keys(state.heroes).length>=25) return toast('最多添加 25 位英雄。');
    state.heroes[id]=Math.min(9,(state.heroes[id]||0)+1);
    toast(`${state.maps.heroes[id].name} · 共 ${state.heroes[id]} 张`);
  } else if(kind==='owned') {
    if(state.owned.length>=20) return toast('最多添加 20 件成装。');
    state.owned.push(id); toast(`已添加${state.maps.items[id].name}`);
  } else if(kind==='contested') {
    if(state.contested.includes(id)) state.contested=state.contested.filter(h=>h!==id);
    else if(state.contested.length<20) state.contested.push(id); else return toast('最多标记 20 位同行英雄。');
  }
  renderPicker(); renderSelections(); saveConditions();
}
function showTrait(id) {
  const t=state.maps.traits[id];
  const members=state.data.heroes.filter(h=>!h.form && h.traits.some(x=>x.id===id));
  openDialog(t.name,`<div class="detail-section"><p>${esc(t.description)}</p>${t.levels.map(l=>`<div class="build-row"><strong>${l.count}</strong><span>${esc(l.effect)}</span></div>`).join('')}</div><div class="detail-section"><h3>羁绊英雄</h3><div class="trait-list">${members.map(h=>`<button class="trait-button" data-action="hero" data-id="${h.id}">${h.cost}费 ${esc(h.name)}</button>`).join('')}</div></div>`);
}
function renderSources() {
  const meta=state.meta, counts=meta.counts;
  $('#source-content').innerHTML=`<div class="source-grid"><article class="info-card sources-wide"><span class="eyebrow">OFFICIAL DATA SNAPSHOT</span><h3>${esc(meta.name)}</h3><p>资料版本 ${esc(meta.version)} · 官网数据更新 ${esc(meta.data_updated_at)}<br>本地同步 ${esc(new Date(meta.synced_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}))}（北京时间）</p><div class="stats-strip">${[['heroes','弈子 / 形态 / 召唤物'],['lineups','官网阵容'],['augments','强化符文'],['portals','城邦 / 开局奇遇']].map(([k,label])=>`<div><b>${counts[k]}</b><small>${label}</small></div>`).join('')}</div><p>${esc(meta.recommendation_note)}</p><div class="warning-box">${esc(meta.coverage_note)}${meta.stale?'<br>此快照超过 7 天未同步，请维护者核对官网更新。':''}</div></article>
    ${meta.mechanics.map(m=>`<article class="info-card"><span class="eyebrow">SEASON MECHANIC</span><h3>${esc(m.name)}</h3><p>${esc(m.description)}</p><a href="${esc(m.source_url)}" target="_blank" rel="noopener">金铲铲官方说明 ↗</a></article>`).join('')}
    <article class="info-card sources-wide"><h3>羁绊图鉴</h3><p>点击查看当前返场版羁绊效果与英雄。</p><div class="trait-list">${state.data.traits.map(t=>`<button class="trait-button" data-action="trait" data-id="${t.id}">${esc(t.name)}</button>`).join('')}</div></article>
    <article class="info-card sources-wide"><h3>城邦与开局奇遇</h3><p>以下为官网当前公开资料中收录的条目。</p><div class="portal-list">${state.data.portals.map(p=>`<div class="portal-card"><h4>${esc(p.name)}</h4><p>${esc(p.description)}</p></div>`).join('')}</div></article>
    <article class="info-card sources-wide"><h3>资料来源</h3><p>使用官网页面引用的腾讯公开 JSON，更新命令会校验赛季和数据关联后替换快照。</p>${meta.sources.map(s=>`<div class="source-item"><div><strong>${esc(s.title)}</strong><p>${esc(s.publisher)}${s.updated_at?' · '+esc(s.updated_at):''}</p></div><a href="${esc(s.url)}" target="_blank" rel="noopener">查看原始资料 ↗</a></div>`).join('')}</article></div>`;
}
function connectionStatus() {
  $('#connection-status').hidden=navigator.onLine;
  $('#connection-status').textContent='当前处于离线状态，显示已缓存资料。恢复网络后可重新计算推荐。';
}

document.addEventListener('error', event=>{if(event.target.tagName==='IMG') event.target.hidden=true;},true);
document.addEventListener('click', async event=>{
  const view=event.target.closest('[data-view]');
  if(view && state.data) { showView(view.dataset.view); window.scrollTo({top:0,behavior:'auto'}); return; }
  const button=event.target.closest('[data-action]'); if(!button) return;
  const {action,id,star}=button.dataset;
  if(action==='reload') return location.reload();
  if(action==='close-modal') { $('#modal').close(); state.picker=null; return; }
  if(!state.data) return;
  if(action==='reset') return resetConditions();
  if(action.startsWith('pick-') && action!=='pick-entry') return showPicker(action.slice(5));
  if(action==='pick-entry') return pickEntry(id);
  if(action==='hero') return showHero(id);
  if(action==='hero-star') return showHero(id,Number(star));
  if(action==='item') return showItem(id);
  if(action==='lineup') return showLineup(id);
  if(action==='trait') return showTrait(id);
  if(action==='augment-detail') return showAugment(id);
  if(action==='favorite') return toggleFavorite(id);
  if(action==='toggle-favorites') {
    state.favoriteMode=!state.favoriteMode; button.classList.toggle('active',state.favoriteMode);button.setAttribute('aria-pressed',state.favoriteMode);renderResults(); return;
  }
  if(action==='share') {
    const url=new URL(location.href);url.hash=`lineup/${id}`;
    try { await navigator.clipboard.writeText(url.href);toast('阵容链接已复制。'); } catch { openDialog('阵容分享链接',`<p class="muted">复制下面的链接，即可分享此阵容。</p><input aria-label="阵容链接" readonly value="${esc(url.href)}">`); }
    return;
  }
  if(!['add-component','remove-component','remove-owned','remove-augment','remove-contested','hero-plus','hero-minus','add-from-detail','add-augment-detail'].includes(action)) return;
  if(action==='add-component') { if(state.components.length>=40) return toast('最多添加 40 件散件。');state.components.push(id); }
  if(action==='remove-component') state.components.splice(state.components.indexOf(id),1);
  if(action==='remove-owned') state.owned.splice(state.owned.indexOf(id),1);
  if(action==='remove-augment') state.augments=state.augments.filter(a=>a!==id);
  if(action==='remove-contested') state.contested=state.contested.filter(h=>h!==id);
  if(action==='hero-plus') state.heroes[id]=Math.min(9,state.heroes[id]+1);
  if(action==='hero-minus') {state.heroes[id]--;if(!state.heroes[id]) delete state.heroes[id];}
  if(action==='add-from-detail') {
    if(state.maps.items[id].type==='基础装备') { if(state.components.length>=40) return toast('最多添加 40 件散件。');state.components.push(id); }
    else { if(state.owned.length>=20) return toast('最多添加 20 件成装。');state.owned.push(id); }
    toast(`已添加${state.maps.items[id].name}`);
  }
  if(action==='add-augment-detail') {
    if(state.augments.includes(id)) return toast('已选入此强化符文。');
    if(state.augments.length>=3) return toast('最多选择 3 个强化符文。');
    state.augments.push(id);toast('已选入当前海克斯。');
  }
  renderSelections();saveConditions();
});
document.addEventListener('input',event=>{
  if(event.target.id==='lineup-search') renderResults();
  if(event.target.id==='hero-search') renderHeroes();
  if(event.target.id==='item-search') renderItems();
  if(event.target.id==='picker-search' && state.picker) {state.picker.q=event.target.value.trim();renderPicker();}
});
document.addEventListener('change',event=>{
  if(event.target.id==='lineup-scope') renderResults();
  if(['hero-cost','hero-trait'].includes(event.target.id)) renderHeroes();
  if(['item-type','craftable-only'].includes(event.target.id)) renderItems();
  if(event.target.id==='picker-tier' && state.picker) {state.picker.tier=event.target.value;renderPicker();}
  if(event.target.closest('#recommend-form')) { updatePortalDescription(); saveConditions(); }
});
$('#recommend-form').addEventListener('submit',event=>{event.preventDefault();recommend();});
$('#modal').addEventListener('click',event=>{if(event.target===$('#modal')) {const box=$('#modal').getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom) $('#modal').close();}});
$('#modal').addEventListener('close',()=>{state.picker=null;});
window.addEventListener('online',connectionStatus);window.addEventListener('offline',connectionStatus);
window.addEventListener('hashchange',()=>{if(state.data) handleRoute();});
function handleRoute() {
  const hash=location.hash.slice(1), match=/^lineup\/(\d+)$/.exec(hash);
  const heroMatch=/^hero\/(\d+)$/.exec(hash);
  if(heroMatch) { showHero(heroMatch[1]); }
  else if(match) {showView('handbook',false);showLineup(match[1]);} else showView(hash||'handbook',false);
}
async function init() {
  try {
    const responses=await Promise.all([fetch('/api/v1/catalog',{signal:AbortSignal.timeout(20000)}),fetch('/api/v1/meta',{signal:AbortSignal.timeout(20000)}),fetch('/api/v1/guidebook',{signal:AbortSignal.timeout(20000)})]);
    if(responses.some(r=>!r.ok)) throw new Error('服务器未能返回资料，请检查服务状态。');
    [state.data,state.meta,state.reference]=await Promise.all(responses.map(r=>r.json()));
    for(const key of ['heroes','items','augments','traits','portals']) state.maps[key]=Object.fromEntries(state.data[key].map(x=>[x.id,x]));
    $('#portal').innerHTML='<option value="">暂未选择</option>'+state.data.portals.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
    $('#hero-trait').innerHTML='<option value="">全部羁绊</option>'+state.data.traits.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');
    $('#item-type').innerHTML='<option value="">全部可见装备</option>'+[...new Set(state.data.items.map(i=>i.type))].filter(t=>t!=='-1').map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('');
    $('#data-version').textContent=`官网数据 ${state.meta.version} · 更新 ${state.meta.data_updated_at.slice(0,10)}`;
    initReference();
    $('#loading').hidden=true; restoreConditions(); renderSelections(); handleRoute(); connectionStatus();
    if(state.meta.stale) toast('资料快照超过 7 天未同步，可在赛季资料页查看更新时间。');
    if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
  } catch(error) {
    $('#loading').hidden=true;$('#fatal-error').hidden=false;$('#fatal-message').textContent=error.message||'请检查网络后重试。';
  }
}
init();
