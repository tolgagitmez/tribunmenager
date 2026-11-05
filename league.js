'use strict';
const $=id=>document.getElementById(id),key='tribun-league-token';
const storage={get:k=>{try{return localStorage.getItem(k);}catch{return null;}},set:(k,v)=>{try{localStorage.setItem(k,v);return true;}catch{return false;}},remove:k=>{try{localStorage.removeItem(k);}catch{}}};
let token=storage.get(key),data=null,refreshing=false;
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(text,kind='error'){$('error').textContent=text;$('error').dataset.kind=kind;}
function busy(button,value){button.disabled=value;button.setAttribute('aria-busy',String(value));}
async function req(path,body){
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
 try{
  let response;
  try{response=await fetch(path,{...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}),signal:controller.signal});}
  catch{throw Error('Oyun sunucusuna ulaşılamadı. Sunucuyu başlatıp bağlantını kontrol ederek yeniden dene.');}
  let result;try{result=await response.json();}catch{throw Error('Lig hizmeti yanıt vermiyor. Oyunu yerel oyun sunucusu üzerinden aç.');}
  if(!response.ok)throw Error(result.error||'İşlem tamamlanamadı. Biraz sonra yeniden dene.');
  return result;
 }finally{clearTimeout(timeout);}
}
async function lobby(action){
 const name=$(action==='create'?'createName':'joinName'),manager=name.value.trim(),code=$('joinCode').value.trim().toUpperCase();
 if(!manager){message('Devam etmek için menajer adını yaz.');name.focus();return;}
 if(action==='join'&&!/^[A-F0-9]{6}$/.test(code)){message('Davet kodu 6 karakterden oluşur. Arkadaşının paylaştığı kodu kontrol et.');$('joinCode').focus();return;}
 if($('createBtn').disabled||$('joinBtn').disabled)return;
 busy($('createBtn'),true);busy($('joinBtn'),true);message(action==='create'?'Ligin oluşturuluyor…':'Lige katılıyorsun…','info');
 try{
  const result=await req('/api/league/'+action,{manager,...(action==='join'?{code}:{})});
  token=result.token;const persisted=storage.set(key,token);
  if(window.TribunTransfers?.hasSession())await window.TribunTransfers.linkLeague(token);
  await refresh();
  if(!persisted)message('Lige katıldın. Tarayıcı kayıt izni vermediği için bu oturumu kapatırsan lig erişimin kaybolabilir.','info');
 }catch(e){message(e.message);}
 finally{busy($('createBtn'),false);busy($('joinBtn'),false);}
}
function timer(){
 if(!data)return;
 const now=Date.now()/1000,next=data.next_kickoff;
 if(data.active?.length){$('countdown').textContent='CANLI · '+Math.max(0,Math.ceil(data.active[0].kickoff+300-now))+' sn';$('matchInfo').textContent='Günlük maçlar başladı. 5 dakika sonunda sonuçlar kesinleşir.';}
 else if(next){const seconds=Math.max(0,Math.ceil(next-now)),days=Math.floor(seconds/86400);$('countdown').textContent=`${days?days+'g ':''}${String(Math.floor(seconds%86400/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;$('matchInfo').textContent=`Sıradaki maç günü: ${data.day}/10 · ${new Date(next*1000).toLocaleString('tr-TR')}`;}
 else{$('countdown').textContent='SEZON TAMAMLANDI';$('matchInfo').textContent='10. maç gününün sonuçlarını tabloda inceleyebilirsin.';}
}
function render(){
 $('lobby').hidden=true;$('status').hidden=false;
 $('leagueCode').textContent=data.code;$('myClub').textContent=data.my_club;$('managerName').textContent=data.manager;
 const context=$('navClubName');if(context)context.firstChild.textContent=data.my_club.toLocaleUpperCase('tr-TR');
 const badge=document.querySelector('.header-tools .club-badge');if(badge)badge.textContent=data.my_club.split(/\s+/).slice(0,2).map(word=>word[0]).join('').toLocaleUpperCase('tr-TR');
 $('standings').innerHTML=data.standings.map((team,i)=>`<tr class="${team.slot===data.my_slot?'is-own':''}"><td>${i+1}</td><td>${escapeHtml(team.club)}${team.slot===data.my_slot?'<span class="own-label">SENİN TAKIMIN</span>':''}</td><td>${team.played}</td><td>${team.w}</td><td>${team.d}</td><td>${team.l}</td><td>${team.gf-team.ga}</td><td><b>${team.points}</b></td></tr>`).join('');
 $('clubs').innerHTML=data.teams.map(team=>`<div class="clubtile">${escapeHtml(team.name)}<small>${escapeHtml(team.manager)} · ${team.claimed?'Menajer':'Bilgisayar'}</small></div>`).join('');
 $('results').innerHTML=data.recent.length?data.recent.slice(-8).reverse().map(f=>`<div class="result-row"><span>${escapeHtml(f.home_name)}</span><b>${f.home_score} – ${f.away_score}</b><span>${escapeHtml(f.away_name)}</span></div>`).join(''):'<p>İlk düdük henüz çalmadı. Sonuçlar maçlar tamamlanınca burada.</p>';
 $('tacticInfo').textContent=`Kayıtlı plan: ${data.my_formation} · Pres ${data.my_tactics.press} · Sertlik ${data.my_tactics.aggression}`;
 timer();
}
async function refresh(){
 if(!token||refreshing)return false;
 refreshing=true;busy($('refreshBtn'),true);
 try{data=await req('/api/league/status?token='+encodeURIComponent(token));message('');render();return true;}
 catch(e){if(e.message.includes('menajer anahtarı')){storage.remove(key);token=null;data=null;$('lobby').hidden=false;$('status').hidden=true;}message(e.message);return false;}
 finally{refreshing=false;busy($('refreshBtn'),false);}
}
async function copyCode(){
 if(!data)return;
 try{if(!navigator.clipboard?.writeText)throw Error();await navigator.clipboard.writeText(data.code);message('Davet kodu kopyalandı. Arkadaşlarınla paylaşabilirsin.','success');}
 catch{const el=$('leagueCode'),range=document.createRange(),selection=window.getSelection();range.selectNodeContents(el);selection?.removeAllRanges();selection?.addRange(range);el.focus();message('Otomatik kopyalama kullanılamıyor. Seçili kodu kopyalayabilirsin.','info');}
}
async function sendTactics(){
 if(!token||$('sendTactics').disabled)return;
 busy($('sendTactics'),true);message('Oyun planın kaydediliyor…','info');
 try{let saved;try{saved=JSON.parse(storage.get('tribun-manager-pro09')||'{}');}catch{saved={};}await req('/api/league/tactics',{token,formation:saved?.formation||'4-3-3',tactics:saved?.tactics||{}});if(window.TribunTransfers?.hasSession())await window.TribunTransfers.linkLeague(token);if(await refresh())message('Oyun planın ve güncel kadron lige kaydedildi.','success');}
 catch(e){message(e.message);}
 finally{busy($('sendTactics'),false);}
}
document.querySelectorAll('[data-league-action]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();lobby(form.dataset.leagueAction);}));
$('refreshBtn').onclick=refresh;$('copyCode').onclick=copyCode;$('sendTactics').onclick=sendTactics;
setInterval(timer,1000);setInterval(()=>{if(token&&!document.hidden)refresh();},30000);
if(token){if(window.TribunTransfers?.hasSession())window.TribunTransfers.linkLeague(token).then(refresh).catch(e=>{message(e.message);refresh();});else refresh();}else req('/api/health').catch(()=>message('Günlük lig için yerel oyun sunucusunu başlat. Kurulum bilgisi aşağıdaki bağlantıda.','info'));
