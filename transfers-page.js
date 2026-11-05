'use strict';
(function(){
const API=window.TribunTransfers,$=id=>document.getElementById(id),C=window.TribunClubData;
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label={GK:'Kaleci',DEF:'Savunma',MID:'Orta saha',ATT:'Hücum'},subs={GK:['GK'],DEF:['CB','LB','RB','LWB','RWB'],MID:['DM','CM','AM','LM','RM'],ATT:['ST','LW','RW','CF']};
const kind={'market-sale':'Pazar satışı','quick-sale':'Hızlı satış','market-buy':'Pazardan alım','scout-buy':'Keşiften alım','offer-buy':'Özel teklif','welcome':'Başlangıç hediyesi','scout':'Keşif görevi','token-purchase':'Token alımı','ad-reward':'Reklam ödülü'};
let view=null,intent=null,working=false,polling=false,offset=0,toastTimer=null,activeTab='market';
const num=n=>Number(n||0).toLocaleString('tr-TR'),money=n=>num(n)+' K';
// K denotes club credit, explicitly shown as an in-game balance in the guide.
const value=p=>p.value||Math.max(100000,Math.round((p.rating/75)**4*8000000*Math.max(.55,1+(25-(p.age??25))*.025)/10000)*10000);
const now=()=>Date.now()/1000+offset;
const when=s=>new Date(s*1000).toLocaleString('tr-TR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
function countdown(s){s=Math.max(0,Math.ceil(s));return [Math.floor(s/3600),Math.floor(s%3600/60),s%60].map(x=>String(x).padStart(2,'0')).join(':');}
const empty=(title,copy,icon='swap')=>`<div class="empty-transfer">${window.TribunUI.icon(icon)}<h3>${escape(title)}</h3><p>${escape(copy)}</p></div>`;
function toast(text){$('toast').textContent=text;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),4000);}
function playerCard(p,options={}){
 const form=p.realForm,listing=view?.listings.find(l=>l.playerId===p.id),owned=p.owned!==false&&Number.isInteger(p.id);
 const sub=p.subposition||p.pos,formText=form?`${form.score}/100`:'Veri yok';
 return `<article class="transfer-card ${options.premium?'premium':''} ${listing?'listed':''}"><div class="player-card-top"><div class="player-id"><img src="${p.dataKind==='catalog'?'assets/ui/player-silhouette.svg':'assets/face'+Math.abs(Number(p.face)||0)%11+'.png'}" alt=""><div><strong>${escape(p.name)}</strong><small>${escape(sub)} · ${p.age??'—'} yaş<br>${escape(p.club||'Moreirense SK')}</small></div></div><div class="player-rating">${num(p.rating)}<small>GÜÇ</small></div></div><div class="card-badges"><span>${escape(label[p.pos]||p.pos)}</span>${p.nationality&&p.nationality!=='ZZ'?`<span>${escape(p.nationality)}</span>`:''}${owned&&view?.starters.includes(p.id)?'<span>İLK 11</span>':''}${listing?'<span>TRANSFER LİSTESİNDE</span>':''}</div><div class="player-details"><span>DEĞER<b>${money(value(p))}</b></span><span>KONDİSYON<b>%${num(p.fitness??95)}</b></span><span>GERÇEK FORM<b>${escape(formText)}</b></span></div><div class="form-source">${form?`${escape(form.provider)} · ${escape(form.asOf)} · son ${num(form.sampleMatches)} maç`:(p.dataKind==='demo'?'Mevcut örnek kadro · gerçek futbolcu verisi değil.':'Gerçek form kaydı bulunmuyor.')}</div>${options.price!==undefined?`<div class="card-price"><small>${options.tokens?'TOKEN BEDELİ':'TRANSFER BEDELİ'}</small><strong class="${options.tokens?'token-price':''}">${options.tokens?num(options.price)+' TOKEN':money(options.price)}</strong></div>`:''}${options.actions||''}</article>`;
}
function button(text,action,id,ghost=false,disabled=false){return `<button type="button" class="button ${ghost?'ghost':'primary'}" data-action="${action}" data-id="${escape(id)}" ${disabled?'disabled':''}>${escape(text)}</button>`;}
function readFilters(form){const o={};for(const [k,v]of new FormData(form)){if(['minAge','maxAge','minRating','maxRating','minForm'].includes(k))o[k]=Number(v);else if(v.trim())o[k]=k==='nationality'?v.trim().toUpperCase():v.trim();}return o;}
function fits(p,c){return(!c.pos||p.pos===c.pos)&&(!c.subposition||p.subposition===c.subposition)&&(!c.league||p.league?.toLocaleLowerCase('tr-TR').includes(c.league.toLocaleLowerCase('tr-TR')))&&(!c.nationality||p.nationality===c.nationality)&&p.rating>=(c.minRating||1)&&(p.age??25)<=(c.maxAge||50)&&(!c.minForm||(p.realForm?.score??-1)>=c.minForm);}
function renderMarket(){
 if(!view)return;$('catalogBadge').textContent=view.catalogCount?num(view.catalogCount)+' FUTBOLCU':'VERİ KAYNAĞI BEKLENİYOR';
 const filtered=view.market.filter(l=>fits(l.player,readFilters($('marketFilters')))),sort=$('marketSort').value;
 filtered.sort((a,b)=>sort==='price'?a.price-b.price:sort==='age'?a.player.age-b.player.age:sort==='form'?(b.player.realForm?.score??-1)-(a.player.realForm?.score??-1):b.player.rating-a.player.rating);
 $('marketCount').textContent=num(filtered.length)+' transfer ilanı';
 $('marketCards').innerHTML=filtered.length?filtered.map(l=>playerCard(l.player,{price:l.price,actions:button('Transferi incele','buy',l.id)})).join(''):empty(view.catalogCount?'Bu filtrelerle ilan bulunamadı.':'Futbolcu havuzu eklenmeye hazır.',view.catalogCount?'Filtreleri genişleterek tekrar dene.':'İsteğin doğrultusunda yeni futbolcu eklenmedi. Tarihli form verisiyle oyuncu kaynağı bağlandığında pazar burada oluşacak.');
}
function renderSales(){
 if(!view)return;const r=view.rules,owned=view.players.filter(p=>p.owned!==false);
 $('listingBadge').textContent=view.listings.length+'/'+r.maxListings;$('saleSlots').textContent=view.listings.length+' / '+r.maxListings+' İLAN';
 $('sellingRules').innerHTML=`<b>Fiyat aralığı: mevcut değerin ${r.minPriceMultiplier}–${r.maxPriceMultiplier.toLocaleString('tr-TR')} katı.</b> Fiyat arttıkça satış olasılığı düşer. Kesin satış süresi verilmez. Hızlı satış ${r.quickSaleTokens} token karşılığında mevcut değeri kazandırır. Kadro en az ${r.minSquad} oyuncu ve en az bir kaleci içerir.`;
 $('listedCards').innerHTML=view.listings.length?view.listings.map(l=>playerCard(view.players[l.playerId],{price:l.price,actions:button('Fiyatı düzenle','reprice',l.playerId)+button('Listeden çıkar','unlist',l.playerId,true)})).join(''):empty('Henüz satış ilanın yok.','Aşağıdaki kadrodan bir oyuncu seçerek fiyatını belirle.');
 $('squadCards').innerHTML=owned.map(p=>{const listed=view.listings.some(l=>l.playerId===p.id),blocked=owned.length<=r.minSquad||owned.filter(q=>q.pos===p.pos).length<=r.minByPosition[p.pos];return playerCard(p,{actions:button(listed?'Fiyatı düzenle':'Satış fiyatı belirle',listed?'reprice':'list',p.id,false,blocked||(!listed&&view.listings.length>=r.maxListings))+button('Hızlı sat · '+r.quickSaleTokens+' token','quick-sell',p.id,true,blocked||view.wallet.tokens<r.quickSaleTokens)});}).join('');
}
function renderScout(){
 if(!view)return;const r=view.rules,j=view.scout,searching=j?.status==='searching',expired=j&&now()>=j.expiresAt;
 $('scoutCost').textContent=`Görev: ${countdown(r.scoutSeconds)} · ${money(r.scoutCash)} · En fazla ${r.scoutResults} aday. Oyuncu alım bedeli ayrıca ödenir. Eşleşme yoksa görev ücreti alınmaz.`;
 $('startScout').disabled=working||searching||!view.catalogCount||view.wallet.cash<r.scoutCash;
 $('scoutTitle').textContent=searching?'GÖZLEMCİN SAHADA.':j&&!expired?'RAPORUN HAZIR.':'İHTİYACINI BELİRLE.';
 $('scoutTimer').textContent=searching?countdown(j.readyAt-now()):j&&!expired?'HAZIR':'—';
 $('scoutDescription').textContent=searching?'Görev, oyun kapalıyken de ilerler. Sonuçlar süre tamamlandığında açılır.':!view.catalogCount?'Futbolcu kaynağı henüz eklenmedi. Filtreler ve keşif sistemi veri geldiğinde kullanılabilecek.':j&&!expired?'Adayları karşılaştır. İstediğin oyuncuyu kulüp bütçenle transfer edebilirsin. Sonuçlar '+when(j.expiresAt)+' tarihine kadar kullanılabilir.':expired?'Önceki keşif raporunun süresi doldu. Yeni bir görev başlatabilirsin.':'Filtreleri belirle ve gözlemcini görevlendir.';
 const available=j?.status==='ready'&&!expired?j.results.filter(l=>l.available&&!view.players.some(p=>p.owned!==false&&p.uid===l.player.uid)):[];
 $('scoutCards').innerHTML=available.length?available.map(l=>playerCard(l.player,{price:l.price,actions:button('Keşiften transfer et','scout-buy',l.id)})).join(''):empty(searching?'Keşif devam ediyor.':'Henüz kullanılabilir rapor yok.',searching?'Adayların kimliği ve bedeli görev tamamlanınca açılacak.':'Hazır adaylar ve transfer bedelleri burada görünecek.','target');
}
function renderOffer(){
 const o=view?.offer;if(!view)return;
 if(!o||o.claimed||o.expiresAt<=now()||view.players.some(p=>p.owned!==false&&p.uid===o.player.uid)){
  $('offerContent').innerHTML=empty(o?.claimed?'Teklif kadrona katıldı.':'Şu an aktif özel teklif yok.',view.catalogCount?'Kadronun ihtiyaçlarına uygun yeni bir fırsat oluştuğunda burada göreceksin.':'Gerçek futbolcu havuzu eklendiğinde ihtiyaca göre süreli token teklifleri oluşturulacak.','shield');return;
 }
 const own=view.players.filter(p=>p.owned!==false&&p.pos===o.position).sort((a,b)=>a.rating-b.rating)[0];
 $('offerContent').innerHTML=`<div class="offer-grid"><div class="panel offer-context"><span class="eyebrow">${escape(label[o.position])} İÇİN FIRSAT</span><h3>KADRONA YENİ BİR GÜÇ.</h3><p>${escape(own?.name||'Mevcut kadro')} · Güç ${num(own?.rating)} → ${escape(o.player.name)} · Güç ${num(o.player.rating)}</p><div class="offer-clock" data-expires="${o.expiresAt}">${countdown(o.expiresAt-now())}</div><p>Standart token bedeli: ${num(o.standardTokens)}. Bu teklifin bedeli: ${num(o.tokens)} token. Futbolcuyu ve toplam bedeli onay ekranında inceleyebilirsin.</p></div>${playerCard(o.player,{premium:true,price:o.tokens,tokens:true,actions:button('Token ile transfer et','offer-buy',o.id,false,view.wallet.tokens<o.tokens)})}</div>`;
}
function table(headers,rows){return `<div class="panel transfer-table-wrap"><table class="transfer-table"><thead><tr>${headers.map(h=>`<th scope="col">${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
function renderBooks(){
 if(!view)return;
 $('historyContent').innerHTML=view.history.length?table(['TARİH','İŞLEM','FUTBOLCU','KULÜP','BEDEL'],view.history.map(h=>`<tr><td>${escape(when(h.at))}</td><td>${escape(kind[h.type]||h.type)}</td><td>${escape(h.player)}</td><td>${escape(h.buyer||h.seller)}</td><td>${h.tokens?num(h.tokens)+' token':money(h.price)}</td></tr>`)):empty('İlk hamlen henüz yapılmadı.','Tamamlanan alım ve satımlar burada kayıt altına alınır.');
 $('ledgerContent').innerHTML=table(['TARİH','İŞLEM','HAREKET','İŞLEM SONRASI BAKİYE'],view.ledger.map(l=>`<tr><td>${escape(when(l.at))}</td><td>${escape(kind[l.kind]||l.kind)}</td><td class="${l.delta>0?'positive':'negative'}">${l.delta>0?'+':''}${num(l.delta)} ${l.currency==='tokens'?'token':'K'}</td><td>${num(l.balance)} ${l.currency==='tokens'?'token':'K'}</td></tr>`));
 $('tokenPacks').innerHTML=view.rules.tokenPacks.map(p=>`<article class="panel token-pack"><span class="eyebrow">TRİBÜN TOKEN</span><strong>${num(p.tokens)}</strong><p>Özel transfer ve hızlı satış işlemleri için token paketi.</p><button class="button ghost" disabled>Satın alma yakında</button></article>`).join('');
 $('rewardTerms').textContent=`Doğrulanmış reklam tamamlaması başına ${view.rules.rewardTokens} token. Günde en fazla ${view.rules.rewardDailyLimit} ödül, aralarında en az ${view.rules.rewardCooldownSeconds/3600} saat.`;
}
function receive(data){
 if(view&&data.profileId===view.profileId&&data.revision<view.revision)return;
 view=data;offset=data.serverTime-Date.now()/1000;
 $('cashBalance').textContent=Number(data.wallet.cash).toLocaleString('tr-TR',{notation:'compact',maximumFractionDigits:1})+' K';$('cashBalance').title=money(data.wallet.cash);$('tokenBalance').textContent=num(data.wallet.tokens);
 $('connectionStatus').textContent=data.rosterLockedUntil?'GÜNLÜK MAÇ · KADRO '+when(data.rosterLockedUntil)+' TARİHİNE KADAR KİLİTLİ':'TRANSFER MERKEZİ BAĞLI · '+when(data.serverTime);$('connectionStatus').dataset.state='ready';$('connectionHelp').hidden=true;
 renderMarket();renderSales();renderScout();renderOffer();renderBooks();
}
function failed(e){$('connectionStatus').textContent='Transfer bağlantısı kurulamadı.';$('connectionStatus').dataset.state='error';$('connectionHelp').hidden=false;$('connectionMessage').textContent=e.message;}
async function refresh(){if(polling||working)return;polling=true;$('refreshTransfers').disabled=true;try{let data=await API.connect();const starters=API.cached().starters;if(starters?.length===11&&JSON.stringify(starters)!==JSON.stringify(data.starters))data=await API.command('lineup',{starters});receive(data);}catch(e){failed(e);}finally{polling=false;$('refreshTransfers').disabled=false;}}
function showTab(tab,push=true){if(!['market','sell','scout','offers','history','wallet'].includes(tab))tab='market';activeTab=tab;document.querySelectorAll('[data-tab]').forEach(b=>{b.setAttribute('aria-selected',String(b.dataset.tab===tab));b.tabIndex=b.dataset.tab===tab?0:-1;});document.querySelectorAll('.transfer-view').forEach(s=>s.hidden=s.id!=='view-'+tab);if(push)history.replaceState(null,'','#'+tab);}
function openIntent(action,id){
 if(!view||working)return;let p,price,tokens=0,title,body='',payload={};
 if(['list','reprice','quick-sell','unlist'].includes(action)){
  p=view.players[Number(id)];if(!p||p.owned===false)return;payload.playerId=p.id;
  const l=view.listings.find(l=>l.playerId===p.id);
  if(action==='list'||action==='reprice'){
   title=action==='list'?'SATIŞ FİYATINI BELİRLE.':'İLAN FİYATINI DÜZENLE.';const min=Math.ceil(value(p)*view.rules.minPriceMultiplier),max=Math.floor(value(p)*view.rules.maxPriceMultiplier);price=l?.price||min;
   body=playerCard(p)+`<div class="sale-controls"><label>İLAN FİYATI<input type="number" id="salePriceNumber" min="${min}" max="${max}" step="1" value="${price}"></label><label class="sr-only" for="salePriceRange">Satış fiyatı kaydırıcısı</label><input type="range" id="salePriceRange" aria-label="Satış fiyatı" min="${min}" max="${max}" step="1" value="${price}"><div class="sale-bounds"><span>En az ${money(min)}</span><span>En fazla ${money(max)}</span></div><div class="sale-explanation" id="saleDemand"></div></div>`;payload.price=price;
  }else if(action==='quick-sell'){
   title='HIZLI SATIŞI ONAYLA.';tokens=view.rules.quickSaleTokens;price=value(p);payload.expectedValue=price;payload.expectedTokens=tokens;body=playerCard(p)+`<div class="sale-explanation"><b>${money(price)}</b> kulüp bütçene eklenecek. İşlem bedeli <b>${tokens} token</b>. Oyuncu kadrodan ayrılacak; ilk 11’deyse uygun yedek yerini alacak.</div>`;
  }else{title='İLANI GERİ ÇEK.';body=playerCard(p)+'<p>Oyuncuyu transfer listesinden çıkarmak ücretsizdir.</p>';}
 }else if(action==='scout-start'){
  title='KEŞİF GÖREVİNİ ONAYLA.';payload.criteria=readFilters($('scoutFilters'));payload.expectedCash=view.rules.scoutCash;body=`<div class="sale-explanation">Görev bedeli <b>${money(view.rules.scoutCash)}</b>. Süre <b>${countdown(view.rules.scoutSeconds)}</b>. Adayları görmek satın alma zorunluluğu oluşturmaz.</div>`;
 }else{
  let l;if(action==='buy'){l=view.market.find(x=>x.id===id);payload.listingId=id;}
  if(action==='scout-buy'){l=view.scout?.results.find(x=>x.id===id);payload.resultId=id;}
  if(action==='offer-buy'){l=view.offer?.id===id?view.offer:null;payload.offerId=id;tokens=l?.tokens||0;}
  if(!l)return;p=l.player;price=l.price||0;if(tokens)payload.expectedTokens=tokens;else payload.expectedCash=price;title='TRANSFERİ ONAYLA.';body=playerCard(p,{premium:!!tokens,price:tokens||price,tokens:!!tokens})+`<div class="sale-explanation">${escape(p.name)} kadrona katılacak. Toplam bedel <b>${tokens?num(tokens)+' token':money(price)}</b>.</div>`;
 }
 intent={action,payload,id:API.requestId()};$('transferDialogTitle').textContent=title;$('transferDialogContent').innerHTML=body;$('transferDialogError').textContent='';$('confirmTransfer').textContent=action==='quick-sell'?tokens+' token ile sat':action==='offer-buy'?tokens+' token ile al':'İşlemi onayla';$('confirmTransfer').disabled=false;
 $('transferModal').hidden=false;
 if($('salePriceNumber')){
  const n=$('salePriceNumber'),range=$('salePriceRange');
  function update(source){const v=Number(source.value);if(source===range)n.value=source.value;else range.value=source.value;intent.payload.price=v;const valid=n.value!==''&&Number.isSafeInteger(v)&&v>=Number(n.min)&&v<=Number(n.max);$('confirmTransfer').disabled=!valid;const ratio=v/value(p);$('saleDemand').textContent=valid?`${ratio.toLocaleString('tr-TR',{maximumFractionDigits:2})} × mevcut değer · ${ratio<=1.3?'Görece hızlı satış beklentisi':ratio<=1.8?'Orta hızda satış beklentisi':'Daha uzun bekleme ihtimali'}. Talep ve rastgele pazar kontrolleri etkiler; süre garantisi yok.`:'Fiyat izin verilen aralıkta bir tam sayı olmalı.';}
  n.oninput=()=>update(n);range.oninput=()=>update(range);update(n);
 }
}
async function execute(){
 if(!intent||working)return;working=true;$('confirmTransfer').disabled=true;$('transferDialogError').textContent='';const sent=intent;
 // Keep this request ID on transport failures; retries cannot double-spend.
 try{const data=await API.command(sent.action,sent.payload,sent.id);receive(data);$('transferModal').hidden=true;intent=null;toast(data.result.message);}
 catch(e){$('transferDialogError').textContent=e.message;}
 finally{working=false;$('confirmTransfer').disabled=false;}
}
document.querySelectorAll('[data-tab]').forEach(b=>{
 b.onclick=()=>showTab(b.dataset.tab);
 b.onkeydown=e=>{const buttons=[...document.querySelectorAll('[data-tab]')],i=buttons.indexOf(b);let next;if(e.key==='ArrowRight')next=buttons[(i+1)%buttons.length];if(e.key==='ArrowLeft')next=buttons[(i-1+buttons.length)%buttons.length];if(e.key==='Home')next=buttons[0];if(e.key==='End')next=buttons.at(-1);if(next){e.preventDefault();showTab(next.dataset.tab);next.focus();}};
});
document.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(b&&!b.disabled)openIntent(b.dataset.action,b.dataset.id);});
document.querySelectorAll('[data-subpositions]').forEach(select=>{const form=select.closest('form'),pos=form.elements.pos;function update(){const old=select.value;select.innerHTML='<option value="">Tümü</option>'+(pos.value?subs[pos.value]:Object.values(subs).flat()).map(s=>`<option value="${s}">${s}</option>`).join('');if([...select.options].some(o=>o.value===old))select.value=old;}pos.addEventListener('change',update);update();});
$('marketFilters').onsubmit=e=>e.preventDefault();$('marketFilters').addEventListener('input',renderMarket);$('marketFilters').addEventListener('change',renderMarket);$('marketFilters').onreset=()=>setTimeout(()=>{const s=$('marketFilters').elements.subposition;s.innerHTML='<option value="">Tümü</option>'+Object.values(subs).flat().map(v=>`<option value="${v}">${v}</option>`).join('');renderMarket();},0);
$('marketSort').onchange=renderMarket;$('scoutFilters').onsubmit=e=>{e.preventDefault();if(!$('startScout').disabled)openIntent('scout-start');};
$('confirmTransfer').onclick=execute;$('refreshTransfers').onclick=refresh;
window.addEventListener('hashchange',()=>showTab(location.hash.slice(1),false));
window.addEventListener('pageshow',e=>{if(e.persisted)refresh();});
setInterval(()=>{if(!document.hidden&&view&&!working&&!polling)refresh();},20000);
setInterval(()=>{if(!view)return;document.querySelectorAll('[data-expires]').forEach(el=>el.textContent=countdown(Number(el.dataset.expires)-now()));if(view.scout?.status==='searching')$('scoutTimer').textContent=countdown(view.scout.readyAt-now());},1000);
showTab(location.hash.slice(1),false);refresh();
window.TribunTransferPage={snapshot:()=>view,refresh,openIntent,execute,showTab};
})();
