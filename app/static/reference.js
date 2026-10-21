'use strict';
state.heroId = storage.get('yimo-last-hero','11205');
state.studyStar = 1;
state.heroTable = false;
state.heroSort = {key:'cost',direction:1};
state.augmentLimit = 36;
state.lineupTab = 'overview';

function initReference() {
  const augmentOptions=state.data.augments.map(a=>`<option value="${a.id}">${esc(a.name)}</option>`).join('');
  $('#book-augment').innerHTML='<option value="">按海克斯查阵容</option>'+augmentOptions;
  $('#augment-lineup').innerHTML='<option value="">按阵容查海克斯</option>'+state.data.lineups.map(l=>`<option value="${l.id}">${esc(l.name)}</option>`).join('');
  $('#augment-category').innerHTML='<option value="">全部类型</option>'+[...new Set(Object.values(state.reference.augments).map(a=>a.category))].map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
  if(!state.maps.heroes[state.heroId]) state.heroId='11205';
}
function relationBadge(row) { return `<span class="evidence-badge ${row.basis==='mechanic_inference'?'inferred':''}">${esc(row.label)}</span>`; }
function renderHandbook() {
  const q=$('#book-search').value.trim(), style=$('#book-style').value, augment=$('#book-augment').value;
  let rows=state.data.lineups.filter(l=>{
    const p=state.reference.lineups[l.id];
    return (!q||l.full_name.includes(q)||l.units.some(u=>state.maps.heroes[u.hero_id].name.includes(q))) && (!style||p.route_type===style) && (!augment||p.augment_matches.some(a=>a.augment_id===augment));
  });
  rows.sort((a,b)=>Number(Boolean(a.unavailable_requirements?.length))-Number(Boolean(b.unavailable_requirements?.length)));
  if(augment) rows.sort((a,b)=>state.reference.lineups[b.id].augment_matches.find(x=>x.augment_id===augment).weight-state.reference.lineups[a.id].augment_matches.find(x=>x.augment_id===augment).weight);
  $('#book-count').textContent=`${rows.length} 套官网方案（含不同作者与构筑变体） · 条件与运营归纳属于学习参考`;
  $('#book-grid').innerHTML=rows.map(l=>{
    const p=state.reference.lineups[l.id], h=state.maps.heroes[l.carry_ids[0]], match=p.augment_matches.find(a=>a.augment_id===augment);
    return `<article class="book-card"><div class="book-card-top"><button data-action="lineup" data-id="${l.id}" class="book-title"><h3>${esc(l.name)}</h3><span>${esc(p.style_label)} · 学习负担${esc(p.difficulty)}</span></button><button class="icon-button favorite ${state.favorites.has(l.id)?'saved':''}" data-action="favorite" data-id="${l.id}" aria-label="收藏${esc(l.name)}">${state.favorites.has(l.id)?'★':'☆'}</button></div><div class="card-tags">${tags(l.traits.slice(0,3))}${p.prerequisites.length?'<span class="tag warning">有前置条件</span>':''}${match?relationBadge(match):''}</div><p class="book-win">${esc(p.win_condition)}</p><div class="book-levels"><span>常见搜牌窗口 <b>${p.roll_level} 人口</b></span><span>最终参考 <b>${p.final_level} 人口</b></span></div><div class="roster">${l.units.map(u=>{const hero=state.maps.heroes[u.hero_id];return `<div class="unit-tile ${u.carry?'carry':''}"><button data-action="hero" data-id="${hero.id}" aria-label="学习${esc(hero.name)}">${portrait(hero)}</button><small>${esc(hero.name)}</small></div>`;}).join('')}</div><div class="book-runes"><span>官网优选</span>${l.augment_ids.map(id=>`<button class="rune-pill" data-action="augment-detail" data-id="${id}">${esc(state.maps.augments[id].name)}</button>`).join('')}</div><div class="card-bottom"><small class="muted">${esc(l.author)}</small><button class="details-button" data-action="lineup" data-id="${l.id}">适用条件 · 运营 · 出装 ↗</button></div></article>`;
  }).join('')||'<div class="empty-state">没有匹配的阵容。试试其他名字或移除筛选。</div>';
}
function heroRows() {
  const q=$('#hero-search').value.trim(), cost=$('#hero-cost').value, trait=$('#hero-trait').value;
  return state.data.heroes.filter(h=>(!q||h.name.includes(q)||h.traits.some(t=>t.name.includes(q)))&&(cost===''||h.cost===Number(cost))&&(!trait||h.traits.some(t=>t.id===trait)));
}
function starData(hero, star=state.studyStar) { return hero.stars.find(s=>s.star===Number(star))||hero.stars[0]||{star:1,hp:hero.stats.hp,attack:hero.stats.attack,skill:hero.skill_description}; }
function heroStats(hero) {
  const variant=starData(hero);
  return {cost:hero.cost,hp:variant.hp,attack:variant.attack,attack_speed:hero.stats.attack_speed,armor:hero.stats.armor,magic_resist:hero.stats.magic_resist,range:hero.stats.range,mana:hero.stats.mana,
    attack_dps:Math.round(variant.attack*hero.stats.attack_speed*100)/100,actual_star:variant.star};
}
function renderHeroes() {
  if(!state.reference) return;
  const rows=heroRows();state.heroFiltered=rows.map(h=>h.id);
  if(!rows.some(h=>h.id===state.heroId)) state.heroId=rows[0]?.id;
  $('#hero-list-count').textContent=`${rows.length} 个弈子条目`;
  $('#hero-list').innerHTML=rows.map(h=>`<button class="hero-index-entry ${h.id===state.heroId?'selected':''}" role="option" aria-selected="${h.id===state.heroId}" data-action="study-hero" data-id="${h.id}">${portrait(h)}<span><strong>${esc(h.name)}</strong><small>${h.summon?'召唤物':h.cost+'费'}${h.form?' · 形态':''} · ${h.traits.map(t=>esc(t.name)).join(' / ')}</small></span></button>`).join('');
  $('#hero-study-layout').hidden=state.heroTable;
  $('#hero-table-panel').hidden=!state.heroTable;
  renderHeroStudy();
  if(state.heroTable) renderHeroTable();
}
function selectStudyHero(id) {
  if(!state.maps.heroes[id]) return;
  state.heroId=id;storage.set('yimo-last-hero',id);
  $$('#hero-list .hero-index-entry').forEach(b=>{b.classList.toggle('selected',b.dataset.id===id);b.setAttribute('aria-selected',b.dataset.id===id);});
  renderHeroStudy();$('#hero-detail').scrollTop=0;
  history.replaceState(null,'',`#hero/${id}`);
  if(matchMedia('(max-width:560px)').matches && $('#hero-detail').getBoundingClientRect().top<100) $('#hero-detail').scrollIntoView({block:'start'});
  $(`#hero-list [data-id="${id}"]`)?.scrollIntoView({block:'nearest',inline:'nearest'});
}
function showHero(id,star) {
  if(!state.maps.heroes[id]) return toast('没有找到这条棋子资料。');
  if($('#modal').open) $('#modal').close();
  if(star) { state.studyStar=Number(star);$('#study-star').value=star; }
  if(!heroRows().some(h=>h.id===id)) {$('#hero-search').value='';$('#hero-cost').value='';$('#hero-trait').value='';}
  state.heroId=id;state.heroTable=false;showView('heroes',false);selectStudyHero(id);
}
function stepHero(direction) {
  if(!state.heroFiltered?.length) return;
  const ids=state.heroFiltered,pos=ids.indexOf(state.heroId);
  selectStudyHero(ids[(pos+direction+ids.length)%ids.length]);
}
function renderHeroStudy() {
  const h=state.maps.heroes[state.heroId], root=$('#hero-detail');
  if(!h) {root.innerHTML='<div class="empty-state">没有符合筛选条件的棋子。</div>';return;}
  const s=heroStats(h), variant=starData(h), ref=state.reference.heroes[h.id], position=state.heroFiltered.indexOf(h.id)+1;
  const values=[['生命值',s.hp],['攻击力',s.attack],['护甲',s.armor],['魔抗',s.magic_resist],['攻速',s.attack_speed],['攻击距离',s.range],['法力值',s.mana],['裸普攻DPS',s.attack_dps]];
  root.innerHTML=`<div class="study-nav"><button class="outline-button" data-action="hero-previous">← 上一位</button><span>${position} / ${state.heroFiltered.length}</span><button class="outline-button" data-action="hero-next">下一位 →</button></div><div class="hero-study-body"><div class="detail-hero-head">${portrait(h)}<div><h3>${esc(h.name)}</h3><div class="card-tags">${tags(h.traits)}</div><p>${h.summon?'召唤物':h.cost+'费弈子'}${h.form?' · 形态':''} · ${variant.star}星数据</p></div><button class="outline-button compare-trigger" data-action="compare-heroes">棋子对比 ⇄</button></div><div class="quick-switch"><label for="hero-quick-select">快速跳转</label><select id="hero-quick-select" aria-label="快速跳转棋子">${state.heroFiltered.map(id=>`<option value="${id}" ${id===h.id?'selected':''}>${state.maps.heroes[id].cost}费 · ${esc(state.maps.heroes[id].name)}${state.maps.heroes[id].form?' · 形态':state.maps.heroes[id].summon?' · 召唤物':''}</option>`).join('')}</select><div class="stars">${[1,2,3].map(n=>`<button class="star-button ${state.studyStar===n?'active':''}" data-action="study-star" data-star="${n}">${'★'.repeat(n)}</button>`).join('')}</div></div>${variant.star!==state.studyStar?'<div class="study-tip">官网未单列此单位所选星级的数据，当前显示其已有星级记录。</div>':''}<div class="stat-grid">${values.map(([label,value])=>`<div class="stat-cell"><small>${label}</small><strong>${esc(value)}</strong></div>`).join('')}</div><p class="data-caption">裸普攻DPS = 攻击力 × 攻速，不含技能、暴击、装备和羁绊，不能作为整体强度排名。</p><div class="hero-role-strip"><span class="tag gold">${esc(ref.role)}</span><span class="tag">${esc(ref.damage_type)}</span>${ref.utility_tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div><p class="data-caption">${esc(ref.role_basis)}</p><section class="study-section"><span class="eyebrow">OFFICIAL ABILITY</span><h3>${esc(h.skill_name||'技能描述')}</h3><p class="skill-text">${esc(variant.skill||h.skill_description)}</p>${h.skill_values.filter(Boolean).length?`<details><summary>技能各星级数值</summary><p>${h.skill_values.map(esc).join('<br>')}</p></details>`:''}</section><section class="study-section"><h3>怎么理解这个棋子</h3>${ref.equipment_principles.map((p,i)=>`<p class="numbered-note"><span>${i+1}</span>${esc(p)}</p>`).join('')}<span class="analysis-note">以上为基于技能和官网阵容的学习归纳。</span></section><section class="study-section"><h3>参考出装 · 按阵容看组合</h3><p class="data-caption">完整组合来自官网阵容；不把出现次数当作胜率或最佳装备证明。</p>${ref.builds.length?ref.builds.slice(0,8).map(b=>`<div class="study-build"><div>${h.name==='霞与洛'?`<span class="tag">${esc(b.form_name)}</span>`:''}${b.item_ids.map(id=>`<button class="equipment-link" data-action="item" data-id="${id}" aria-label="查看${esc(state.maps.items[id].name)}">${itemIcon(id)}<small>${esc(state.maps.items[id].name)}</small></button>`).join('')}</div><button class="text-button" data-action="lineup" data-id="${b.lineup_id}">${esc(b.lineup_name)} ↗</button></div>`).join(''):'<p>当前官网阵容库没有给出独立出装组合，不补造“最优三件套”。</p>'}</section>${ref.common_items.length?`<section class="study-section"><h3>这些装备分别解决什么问题</h3>${ref.common_items.slice(0,5).map(i=>`<div class="equipment-explanation"><button data-action="item" data-id="${i.item_id}" class="equipment-name">${itemIcon(i.item_id)}${esc(state.maps.items[i.item_id].name)}</button><p>${i.reasons.map(esc).join(' ')}</p></div>`).join('')}</section>`:''}<section class="study-section"><h3>出现在哪些阵容</h3><div class="trait-list">${ref.lineups.map(l=>`<button class="trait-button" data-action="lineup" data-id="${l.lineup_id}">${esc(l.name)}${l.carry?' · 主C标记':''}</button>`).join('')||'<span class="muted">当前方案未使用此单位</span>'}</div></section><a class="source-link" href="${esc(state.meta.sources.find(x=>x.id===h.source_id).url)}" target="_blank" rel="noopener">查看官网英雄数据 ↗</a></div>`;
}
const attributeColumns=[['cost','费用'],['hp','生命值'],['attack','攻击力'],['attack_speed','攻速'],['armor','护甲'],['magic_resist','魔抗'],['range','射程'],['mana','法力'],['attack_dps','裸普攻DPS']];
function renderHeroTable() {
  const {key,direction}=state.heroSort;
  const rows=heroRows().sort((a,b)=>{const x=heroStats(a)[key],y=heroStats(b)[key];return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*direction;});
  $('#hero-table-panel').innerHTML=`<p class="data-caption">点击列名排序，点击棋子回到固定详情。目标星级：${state.studyStar}星；“实际星级”可识别缺少该星级资料的条目。</p><table class="attribute-table"><thead><tr><th>棋子</th><th>实际星级</th>${attributeColumns.map(([k,label])=>`<th><button data-action="sort-heroes" data-key="${k}">${label}${key===k?(direction>0?' ↑':' ↓'):''}</button></th>`).join('')}</tr></thead><tbody>${rows.map(h=>{const s=heroStats(h);return `<tr><th><button data-action="study-from-table" data-id="${h.id}">${esc(h.name)}</button></th><td>${s.actual_star}星</td>${attributeColumns.map(([k])=>`<td>${esc(s[k])}</td>`).join('')}</tr>`;}).join('')}</tbody></table>`;
}
function showHeroComparison(ids) {
  const list=state.heroFiltered?.length?state.heroFiltered:state.data.heroes.map(h=>h.id),current=state.heroId||list[0];
  ids=ids||[current,list[(list.indexOf(current)+1)%list.length]];
  state.comparedHeroes=ids;
  const selected=ids.filter(id=>state.maps.heroes[id]);
  const labels=[['actual_star','实际数据星级'],...attributeColumns];
  openDialog('棋子属性对比',`<div class="comparison-controls">${[0,1,2].map(i=>`<label>棋子 ${i+1}<select class="compare-select" data-slot="${i}" aria-label="对比棋子${i+1}">${i===2?'<option value="">不添加第三位</option>':''}${state.data.heroes.map(h=>`<option value="${h.id}" ${ids[i]===h.id?'selected':''}>${h.cost}费 · ${esc(h.name)}${h.form?' · 形态':h.summon?' · 召唤物':''}</option>`).join('')}</select></label>`).join('')}</div><p class="data-caption">按图鉴所选${state.studyStar}星比较；缺少星级数据的单位会标注实际星级。面板和技能机制需要结合看。</p><div class="attribute-table-wrap"><table class="attribute-table compare-table"><thead><tr><th>属性</th>${selected.map(id=>`<th>${esc(state.maps.heroes[id].name)}</th>`).join('')}</tr></thead><tbody>${labels.map(([key,label])=>`<tr><th>${label}</th>${selected.map(id=>`<td>${esc(heroStats(state.maps.heroes[id])[key])}</td>`).join('')}</tr>`).join('')}<tr><th>伤害类型</th>${selected.map(id=>`<td>${esc(state.reference.heroes[id].damage_type)}</td>`).join('')}</tr><tr><th>技能</th>${selected.map(id=>`<td class="comparison-skill"><strong>${esc(state.maps.heroes[id].skill_name)}</strong><p>${esc(starData(state.maps.heroes[id]).skill)}</p></td>`).join('')}</tr></tbody></table></div>`);
  if(!ids[2]) $('#modal .compare-select[data-slot="2"]').value='';
}
function renderAugments(reset=false) {
  if(reset) state.augmentLimit=36;
  const q=$('#augment-search').value.trim(),tier=$('#augment-tier-filter').value,category=$('#augment-category').value,lineup=$('#augment-lineup').value;
  const rows=state.data.augments.filter(a=>{const r=state.reference.augments[a.id];return (!q||a.name.includes(q)||a.description.includes(q))&&(!tier||a.tier===Number(tier))&&(!category||r.category===category)&&(!lineup||r.lineups.some(l=>l.lineup_id===lineup));});
  if(lineup) rows.sort((a,b)=>state.reference.augments[b.id].lineups.find(l=>l.lineup_id===lineup).weight-state.reference.augments[a.id].lineups.find(l=>l.lineup_id===lineup).weight);
  $('#augment-list-count').textContent=`${rows.length} 个符文 · 点击查看适配阵容、搭配理由与限制`;
  $('#augment-grid').innerHTML=rows.slice(0,state.augmentLimit).map(a=>{const r=state.reference.augments[a.id],official=r.lineups.filter(l=>l.basis!=='mechanic_inference').length,match=r.lineups.find(l=>l.lineup_id===lineup);return `<button class="augment-card" data-action="augment-detail" data-id="${a.id}"><div class="item-card-header"><img src="${esc(a.icon)}" alt=""><div><h3>${esc(a.name)}</h3><span class="tag gold">${['','白银','黄金','棱彩'][a.tier]}</span> <span class="tag">${esc(r.category)}</span></div></div><p>${esc(a.description)}</p><div class="augment-card-foot">${match?relationBadge(match):official?`<span class="evidence-badge">${official} 套官网攻略明确关联</span>`:'<span class="analysis-note">查看机制与适配条件</span>'}<span>搭配理由 ↗</span></div></button>`;}).join('')||'<div class="empty-state">没有符合条件的海克斯。</div>';
  $('#augment-more').hidden=rows.length<=state.augmentLimit;
  $('#augment-more').textContent=`再展开 ${Math.min(36,Math.max(0,rows.length-state.augmentLimit))} 个`;
}
function showAugment(id) {
  const a=state.maps.augments[id],r=state.reference.augments[id];if(!a) return;
  const official=r.lineups.filter(l=>l.basis!=='mechanic_inference'),inferred=r.lineups.filter(l=>l.basis==='mechanic_inference');
  const rows=values=>values.map(m=>`<div class="rune-match"><div>${relationBadge(m)}<button class="text-button" data-action="lineup" data-id="${m.lineup_id}">${esc(state.data.lineups.find(l=>l.id===m.lineup_id).name)} ↗</button></div><p>${esc(m.reason)}</p></div>`).join('');
  openDialog(a.name,`<div class="item-card-header"><img src="${esc(a.icon)}" alt=""><div><h3>${esc(a.name)}</h3><span class="tag gold">${['','白银','黄金','棱彩'][a.tier]}</span> <span class="tag">${esc(r.category)}</span></div></div><section class="study-section"><h3>官网效果</h3><p class="skill-text">${esc(a.description)}</p></section>${r.cautions.length?`<section class="study-section"><h3>选择前看这些条件</h3>${r.cautions.map(c=>`<div class="warning-box">${esc(c)}</div>`).join('')}</section>`:''}<section class="study-section"><h3>官网攻略明确关联</h3>${rows(official)||'<p class="muted">当前44套官网方案没有明确将此符文列为优选或备选。</p>'}</section>${inferred.length?`<section class="study-section"><h3>机制层面的搭配参考</h3><p class="data-caption">以下是基于描述与构筑路线的分析，不是官网推荐或胜率统计。</p>${rows(inferred.slice(0,12))}${inferred.length>12?`<button class="outline-button" data-action="filter-book-augment" data-id="${id}">查看全部 ${inferred.length} 套关联方案 ↗</button>`:''}</section>`:''}<div class="study-tip">没有出现某套阵容，不代表绝对不能选；先看触发条件、队伍缺口和能否兑现收益。</div><a class="source-link" href="${esc(state.meta.sources.find(s=>s.id===a.source_id).url)}" target="_blank" rel="noopener">查看官网符文数据 ↗</a>`);
}
function boardMarkup(lineup) {
  const cells=[];for(let row=1;row<=4;row++) for(let col=1;col<=7;col++) {const u=lineup.units.find(x=>x.row===row&&x.col===col),h=u?state.maps.heroes[u.hero_id]:null;cells.push(`<div class="board-cell">${h?`<button data-action="hero" data-id="${h.id}" aria-label="学习${esc(h.name)}"><img src="${esc(h.icon)}" alt=""><span>${esc(h.name)}</span></button>`:''}</div>`);}
  return `<p class="board-caption">上方为前排 · 点棋子进入固定图鉴</p><div class="board">${cells.join('')}</div><p class="board-caption">官网参考站位；绘境与对手会改变合适的位置。</p>`;
}
function showLineup(id,tab='overview') {
  const l=state.data.lineups.find(l=>l.id===id),p=state.reference.lineups[id];if(!l||!p) return;
  state.lastLineup=id;state.lineupTab=tab;
  let content='';
  if(tab==='overview') content=`<p class="guide-lead">${esc(p.win_condition)}</p>${p.prerequisites.map(c=>`<div class="warning-box">${esc(c.text)} ${c.kind==='augment'?c.ids.map(a=>`<button class="text-button" data-action="augment-detail" data-id="${a}">${esc(state.maps.augments[a].name)}</button>`).join(' / '):c.kind==='emblem'?c.ids.map(i=>esc(state.maps.items[i].name)).join(' / '):''}</div>`).join('')}<div class="condition-columns"><section><h3>这些情况下值得考虑</h3>${p.choose_when.map(t=>`<p>✓ ${esc(t)}</p>`).join('')}</section><section><h3>这些情况下别硬冲</h3>${p.avoid_when.map(t=>`<p>↘ ${esc(t)}</p>`).join('')}</section></div><section class="study-section"><h3>运营节奏怎么理解</h3><p class="data-caption">常见搜牌窗口 ${p.roll_level}人口，与最终 ${p.final_level}人口站位分开理解。${esc(p.roll_level_note)}</p><div class="milestones">${p.milestones.map((m,i)=>`<div><span>${i+1}</span><section><h4>${esc(m.phase)}</h4><small>${esc(m.condition)}</small><p>${esc(m.action)}</p></section></div>`).join('')}</div></section><section class="study-section"><h3>过渡与转阵原则</h3>${p.transition_principles.map(t=>`<p>${esc(t)}</p>`).join('')}</section><details class="official-guide"><summary>展开官网原攻略：前期与搜牌</summary><p>${esc(l.guides.early)}</p><p>${esc(l.guides.rolling)}</p><p>${esc(l.guides.matchups)}</p></details>`;
  if(tab==='equipment') content=`${boardMarkup(l)}<section class="study-section"><h3>核心装备的作用</h3>${p.equipment.map(u=>`<div class="lineup-equipment"><button class="hero-inline" data-action="hero" data-id="${u.hero_id}">${portrait(state.maps.heroes[u.hero_id])}<span>${esc(state.maps.heroes[u.hero_id].name)}<small>${esc(u.role)}</small></span></button>${u.items.map(i=>`<div class="equipment-explanation"><button class="equipment-name" data-action="item" data-id="${i.item_id}">${itemIcon(i.item_id)}${esc(state.maps.items[i.item_id].name)}</button><p>${i.reasons.map(esc).join(' ')}</p></div>`).join('')}<button class="text-button" data-action="hero" data-id="${u.hero_id}">查看该棋子在其他阵容中的出装组合 ↗</button></div>`).join('')}</section><details class="official-guide"><summary>展开官网原攻略：出装与站位</summary><p>${esc(l.guides.equipment)}</p><p>${esc(l.guides.positioning)}</p></details>`;
  if(tab==='augments') {
    const group=(basis,title)=>{const matches=p.augment_matches.filter(m=>m.basis===basis);return `<section class="study-section"><h3>${title}</h3>${matches.map(m=>`<div class="rune-match"><div><button class="rune-title" data-action="augment-detail" data-id="${m.augment_id}"><img src="${esc(state.maps.augments[m.augment_id].icon)}" alt="">${esc(state.maps.augments[m.augment_id].name)}</button>${relationBadge(m)}</div><p>${esc(m.reason)}</p><p class="rune-effect">${esc(state.maps.augments[m.augment_id].description)}</p></div>`).join('')||'<p class="muted">官网没有单列这一组。</p>'}</section>`;};
    content=`<div class="study-tip">优选／备选来自官网攻略，搭配理由是基于效果的学习分析。先检查专属／转职条件，再补队伍缺口，不需要凑齐三个指定符文。</div>${group('official_primary','官网优选')}${group('official_alternate','官网备选')}<button class="outline-button" data-action="filter-augments-lineup" data-id="${id}">在海克斯图鉴查看全部关联与机制参考 ↗</button><details class="official-guide"><summary>展开官网原攻略：符文说明</summary><p>${esc(l.guides.augments)}</p></details>`;
  }
  openDialog(l.name,`<div class="card-tags"><span class="tag gold">${esc(p.style_label)}</span>${tags(l.traits)}</div><div class="guide-tabs" role="tablist" aria-label="阵容学习栏目">${[['overview','选阵与运营'],['equipment','装备与站位'],['augments','海克斯搭配']].map(([key,label])=>`<button role="tab" aria-selected="${tab===key}" class="${tab===key?'active':''}" data-action="guide-tab" data-id="${id}" data-tab="${key}">${label}</button>`).join('')}</div>${content}<div class="analysis-note guide-provenance">${p.notes.map(esc).join(' ')}<br>官网作者 ${esc(l.author)} · 发布 ${esc(l.published_at)} · 原建立 ${esc(l.original_created_at)}</div><div class="card-actions"><button class="outline-button" data-action="favorite" data-id="${id}">${state.favorites.has(id)?'★ 已收藏':'☆ 收藏方案'}</button><button class="outline-button" data-action="share" data-id="${id}">复制链接</button><a class="source-link" href="${esc(l.source_url)}" target="_blank" rel="noopener">官网原阵容 ↗</a></div>`);
}
async function renderRankings() {
  $('#ranking-content').innerHTML='<div class="loading"><span class="spinner"></span>核对统计来源…</div>';
  try {
    const response=await fetch(`/api/v1/rankings?metric=${encodeURIComponent($('#ranking-metric').value)}&min_samples=${$('#ranking-min-samples').value}`,{signal:AbortSignal.timeout(10000)});
    if(!response.ok) throw new Error('统计接口暂不可用');
    const payload=await response.json();
    $('#ranking-content').innerHTML=`<div class="study-tip">${esc(payload.message)}</div><div class="statistics-definitions">${payload.definitions.map(d=>`<article class="info-card"><h3>${esc(d.name)}</h3><p>${esc(d.meaning)}</p></article>`).join('')}</div>${payload.source?`<article class="info-card"><h3>${esc(payload.source.source_name)}</h3><p>${esc(payload.source.rank_scope)} · ${esc(payload.source.region)} · ${esc(payload.source.period_start)} 至 ${esc(payload.source.period_end)}</p><p>${esc(payload.source.lineup_definition)}</p><a href="${esc(payload.source.source_url)}" target="_blank" rel="noopener">统计来源 ↗</a>${payload.status==='stale'?'<div class="warning-box">统计结束时间超过7天，仅作为历史数据参考。</div>':''}</article>`:''}${payload.rows.length?`<div class="attribute-table-wrap"><table class="attribute-table"><thead><tr><th>阵容</th><th>样本</th><th>前四率</th><th>登顶率</th><th>平均名次</th></tr></thead><tbody>${payload.rows.map(r=>`<tr><th><button data-action="lineup" data-id="${r.lineup_id}">${esc(state.data.lineups.find(l=>l.id===r.lineup_id)?.name||r.lineup_id)}</button></th><td>${r.sample_count}</td><td>${(r.top4_rate*100).toFixed(1)}%</td><td>${(r.first_rate*100).toFixed(1)}%</td><td>${r.average_placement.toFixed(2)}</td></tr>`).join('')}</tbody></table></div>`:payload.source?'<div class="empty-state">当前最低样本筛选下没有足够数据。</div>':''}${payload.source_checks?`<article class="info-card"><h3>目前的数据核验情况</h3>${payload.source_checks.map(s=>`<div class="source-item"><div><strong>${esc(s.name)}</strong><p>${esc(s.result)}</p></div><a href="${esc(s.url)}" target="_blank" rel="noopener">查看来源 ↗</a></div>`).join('')}<p>目前不提供没有来源支持的百分比。阵容学习手册和海克斯关系仍可独立查阅。</p></article>`:''}<p class="data-caption">${esc(payload.note)}</p>`;
  } catch(error) {$('#ranking-content').innerHTML=`<div class="empty-state">${esc(error.message)}，联网后可重试。</div>`;}
}
function showFundamentals() {openDialog('什么时候做什么 · 运营判断速查',state.reference.fundamentals.map(f=>`<section class="study-section"><h3>${esc(f.title)}</h3><div class="study-tip">适用情况：${esc(f.if)}</div><p>${esc(f.then)}</p></section>`).join('')+'<p class="analysis-note">这些是条件式学习原则，不能代替每局对来牌、对手和版本的判断。</p>');}

document.addEventListener('click',event=>{
  const b=event.target.closest('[data-action]');if(!b||!state.reference) return;
  const {action,id,star,tab,key}=b.dataset;
  if(action==='study-hero') selectStudyHero(id);
  if(action==='hero-previous') stepHero(-1);
  if(action==='hero-next') stepHero(1);
  if(action==='study-star') {state.studyStar=Number(star);$('#study-star').value=star;renderHeroStudy();}
  if(action==='compare-heroes') showHeroComparison();
  if(action==='toggle-hero-table') {state.heroTable=!state.heroTable;renderHeroes();}
  if(action==='sort-heroes') {state.heroSort={key,direction:state.heroSort.key===key?-state.heroSort.direction:-1};renderHeroTable();}
  if(action==='study-from-table') {state.heroTable=false;state.heroId=id;renderHeroes();selectStudyHero(id);}
  if(action==='guide-tab') showLineup(id,tab);
  if(action==='fundamentals') showFundamentals();
  if(action==='more-augments') {state.augmentLimit+=36;renderAugments();}
  if(action==='filter-book-augment') {$('#modal').close();$('#book-search').value='';$('#book-style').value='';$('#book-augment').value=id;showView('handbook');}
  if(action==='filter-augments-lineup') {$('#modal').close();$('#augment-search').value='';$('#augment-tier-filter').value='';$('#augment-category').value='';$('#augment-lineup').value=id;renderAugments(true);showView('augments');}
  if(action==='reference-more') openDialog('更多资料与工具',`<div class="more-tools">${[['sources','资料版本与来源','查看羁绊、城邦和官方来源'],['rankings','胜率与数据口径','核验版本、样本与统计来源'],['recommend','条件匹配工具','可选工具，不需要持续同步对局']].map(([view,title,description])=>`<button data-view="${view}" data-action="close-more"><strong>${title}</strong><small>${description}</small><span>↗</span></button>`).join('')}</div>`);
  if(action==='close-more') $('#modal').close();
  if(action==='favorite') renderHandbook();
});
document.addEventListener('input',event=>{
  if(event.target.id==='book-search') renderHandbook();
  if(event.target.id==='augment-search') renderAugments(true);
});
document.addEventListener('change',event=>{
  const id=event.target.id;
  if(['book-style','book-augment'].includes(id)) renderHandbook();
  if(['augment-tier-filter','augment-category','augment-lineup'].includes(id)) renderAugments(true);
  if(id==='study-star') {state.studyStar=Number(event.target.value);renderHeroes();}
  if(id==='hero-quick-select') selectStudyHero(event.target.value);
  if(event.target.classList.contains('compare-select')) {const ids=[...state.comparedHeroes];ids[Number(event.target.dataset.slot)]=event.target.value;showHeroComparison(ids);}
  if(['ranking-metric','ranking-min-samples'].includes(id)) renderRankings();
});
document.addEventListener('keydown',event=>{
  if($('#view-heroes').hidden||$('#modal').open||event.target.closest('input,select,textarea')||state.heroTable) return;
  if(event.key==='ArrowLeft'||event.key==='ArrowRight') {event.preventDefault();stepHero(event.key==='ArrowLeft'?-1:1);}
});
