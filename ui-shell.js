'use strict';
(function(){
const paths={ball:'<circle cx="12" cy="12" r="9"/><path d="m12 7 5 3-2 6H9l-2-6 5-3Zm0-4v4M3.5 9l3.5 1M6 19l3-3m9 3-3-3m5.5-7-3.5 1"/>',squad:'<path d="M9 3 6 5 3 4 1 9l4 2v10h14V11l4-2-2-5-3 1-3-2c0 4-6 4-6 0Z"/>',tactics:'<rect x="3" y="2" width="18" height="20" rx="2"/><path d="M3 12h18M8 2v4h8V2m-8 20v-4h8v4"/><circle cx="12" cy="12" r="3"/>',training:'<path d="m3 21 4-12h3l4 12H3Zm13 0 2-6h2l2 6h-6ZM6 5l2-2 2 2M17 6h4m-2-2v4"/>',analysis:'<path d="M3 3v18h18M7 16v-4m5 4V8m5 8V5"/>',league:'<path d="M8 3h8v6c0 6-8 6-8 0V3Zm0 2H4v3c0 3 4 3 4 3m8-6h4v3c0 3-4 3-4 3M12 14v5m-4 2h8"/>',studio:'<circle cx="12" cy="7" r="4"/><path d="M4 22v-3c0-7 16-7 16 0v3M8 18v4m8-4v4"/>',play:'<path d="m9 5 11 7-11 7V5Z"/>',pause:'<path d="M8 5v14m8-14v14"/>',arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',arrowup:'<path d="M6 18 18 6M6 6h12v12"/>',chevron:'<path d="m6 9 6 6 6-6"/>',check:'<path d="m5 12 4 4L19 6"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',motion:'<path d="m4 8 4 4-4 4m5-10 6 6-6 6m8-14 3 8-3 8"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',swap:'<path d="M3 7h17l-4-4m5 14H4l4 4M3 17V7m18 0v10"/>',shield:'<path d="m12 2 8 3v7c0 5-8 10-8 10S4 17 4 12V5l8-3Z"/>',target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',refresh:'<path d="M20 9a8 8 0 1 0 0 7M20 3v6h-6"/>',sound:'<path d="m11 5-6 4H2v6h3l6 4V5Zm4 3c3 2 3 6 0 8m3-11c5 4 5 10 0 14"/>'};
const icon=name=>'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+(paths[name]||paths.ball)+'</svg>';
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
let stored=null;try{stored=localStorage.getItem('tribun-ui-motion');}catch{}
const media=window.matchMedia?.('(prefers-reduced-motion: reduce)');let motion=stored==='on'?true:stored==='off'?false:!media?.matches;
function applyMotion(){
 document.documentElement.dataset.motion=motion?'on':'off';
 document.querySelectorAll('[data-motion-toggle]').forEach(b=>{b.setAttribute('aria-pressed',String(motion));b.setAttribute('aria-label',motion?'Arayüz hareketlerini azalt':'Arayüz hareketlerini aç');b.title=motion?'Arayüz hareketleri açık':'Arayüz hareketleri azaltıldı';});
 document.querySelectorAll('[data-motion-svg]').forEach(svg=>{if(motion&&!document.hidden)svg.unpauseAnimations?.();else svg.pauseAnimations?.();});
}
document.querySelectorAll('[data-motion-toggle]').forEach(b=>b.addEventListener('click',()=>{motion=!motion;try{localStorage.setItem('tribun-ui-motion',motion?'on':'off');}catch{}applyMotion();}));
media?.addEventListener?.('change',e=>{let preference=null;try{preference=localStorage.getItem('tribun-ui-motion');}catch{}if(!preference){motion=!e.matches;applyMotion();}});
document.addEventListener('visibilitychange',()=>{document.documentElement.dataset.visibility=document.hidden?'hidden':'visible';applyMotion();});
const header=document.querySelector('.app-header'),menu=document.querySelector('[data-menu-toggle]'),nav=document.querySelector('.app-nav');
function closeMenu(){header?.removeAttribute('data-nav-open');menu?.setAttribute('aria-expanded','false');}
if(header&&menu&&nav){header.dataset.enhanced='';menu.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));header.toggleAttribute('data-nav-open',open);if(open)nav.querySelector('a,button')?.focus();});nav.addEventListener('click',e=>{if(e.target.closest('a,button'))closeMenu();});}
let activeModal=null,returnFocus=null;
const overlays=[...document.querySelectorAll('.overlay,.modal-wrap')];
function focusable(dialog){return [...dialog.querySelectorAll('a[href],button:not([disabled]),select:not([disabled]),input:not([disabled]),[tabindex="0"]')].filter(el=>!el.closest('[hidden]')&&getComputedStyle(el).display!=='none');}
function syncModal(){
 const next=overlays.find(el=>!el.hidden)||null;
 if(next===activeModal)return;
 if(next){if(!activeModal)returnFocus=document.activeElement;activeModal=next;document.body.classList.add('modal-open');const dialog=next.querySelector('.dialog,.modal')||next;dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');dialog.setAttribute('tabindex','-1');(focusable(dialog)[0]||dialog).focus({preventScroll:true});}
 else{activeModal=null;document.body.classList.remove('modal-open');returnFocus?.focus?.({preventScroll:true});returnFocus=null;}
 document.querySelectorAll('.app-header,main,.scoreboard,.app-footer,.app-hero').forEach(el=>{if(!el.contains(activeModal)&&!activeModal?.contains(el))el.inert=!!activeModal;});
}
const observer=new MutationObserver(syncModal);overlays.forEach(el=>observer.observe(el,{attributes:true,attributeFilter:['hidden']}));
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){
  if(activeModal){const closer=activeModal.querySelector('[data-dialog-close],#closeModal,#closeSubs');if(closer){e.preventDefault();closer.click();}}
  else if(header?.hasAttribute('data-nav-open')){closeMenu();menu?.focus();}
 }
 if(e.key==='Tab'&&activeModal){const dialog=activeModal.querySelector('.dialog,.modal')||activeModal,items=focusable(dialog);if(!items.length){e.preventDefault();dialog.focus();return;}const first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
});
document.querySelectorAll('[data-dialog-close]').forEach(b=>b.addEventListener('click',()=>{const overlay=b.closest('.overlay,.modal-wrap');if(overlay)overlay.hidden=true;}));
window.TribunUI={icon,hydrate,motionEnabled:()=>motion,syncMotion:applyMotion,syncModal};
hydrate();applyMotion();syncModal();
})();
