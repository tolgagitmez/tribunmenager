'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const UI=require('../attack-analysis-ui');
function fixture(){
 const dom=new JSDOM('<section id="analysis"></section>'),container=dom.window.document.querySelector('section');
 const team=i=>({team:i,attacks:0,stageCounts:{gain:0,pressureEscape:0,lineBreak:0,finalThird:0,box:0,shot:0},stageEligibility:{},startedBeyond:{},notRequired:{},endedByStage:{},evidence:{},rates:{shotsPer10InPlay:null},pending:0,censored:0});
 const report={valid:true,clock:{observedSeconds:0,inPlaySeconds:0,deadBallSeconds:0},teams:[team(0),team(1)],coverage:{},episodes:[],truncatedEpisodes:0};let fullReads=0,download;
 const view=UI.mount(container,{summary:()=>report,report:()=>{fullReads++;return structuredClone(report);},download:r=>download=r});
 return{dom,container,report,view,get fullReads(){return fullReads;},get download(){return download;}};
}
test('zero exposure shows an undefined rate rather than a false zero success rate',()=>{
 const f=fixture();assert.match(f.container.querySelector('.attack-overview').textContent,/Top oyunda 00:00/);assert.match(f.container.querySelector('.attack-overview').textContent,/— – —/);
 assert([...f.container.querySelectorAll('tbody td')].every(td=>td.textContent==='—'));assert.equal(f.fullReads,0);f.dom.window.close();
});
test('stage eligibility, advanced starts and no-pressure cases are displayed separately',()=>{
 const f=fixture(),t=f.report.teams[0];t.attacks=6;t.stageCounts.finalThird=2;t.stageEligibility.finalThird=5;t.startedBeyond.finalThird=1;t.notRequired.pressureEscape=3;f.view.render();
 const rows=[...f.container.querySelectorAll('tbody tr')];assert.match(rows[3].textContent,/2 \/ 5/);assert.match(rows[3].textContent,/Başlangıçta ileride: 1/);assert.match(rows[1].textContent,/Gerekmedi: 3/);assert.equal(t.stageCounts.gain,0);f.dom.window.close();
});
test('advanced starts are not added to the eligible conversion numerator',()=>{
 const f=fixture(),t=f.report.teams[0];t.stageCounts.box=3;t.stageEligibility.box=2;t.eligibleReached={box:1};t.startedBeyond.box=2;f.view.render();
 const row=[...f.container.querySelectorAll('tbody tr')][4];assert.match(row.textContent,/1 \/ 2/);assert.doesNotMatch(row.textContent,/3 \/ 2/);assert.match(row.textContent,/Başlangıçta ileride: 2/);f.dom.window.close();
});
test('terminal facts and support evidence use separate labels without inventing a cause',()=>{
 const f=fixture(),t=f.report.teams[0];t.attacks=3;t.endedByStage.lineBreak={'pass-interception':2};t.evidence.supportMissingSeconds=4;t.pending=1;f.view.render();
 assert.match(f.container.querySelector('.attack-endings').textContent,/Hat kırma · Pas rakibe geçti: 2/);assert.match(f.container.querySelector('.attack-evidence').textContent,/Destek görevi yok 4 sn/);
 assert.match(f.container.textContent,/tek başına hatanın nedenini kanıtlamaz/);assert.match(f.container.textContent,/Süren 1/);f.dom.window.close();
});
test('refresh only reads the summary and leaves the input report unchanged',()=>{
 const f=fixture();f.report.clock={observedSeconds:65,inPlaySeconds:40,deadBallSeconds:25};f.report.teams[0].rates.shotsPer10InPlay=1.5;const before=structuredClone(f.report);f.view.render();f.view.render();assert.deepEqual(f.report,before);assert.equal(f.fullReads,0);
 assert.match(f.container.querySelector('.attack-overview').textContent,/Top oyunda 00:40 · Duran top \/ ara 00:25 · Ölçülen 01:05/);assert.match(f.container.textContent,/1,5 – —/);f.dom.window.close();
});
test('export is explicit, contains full episodes and cannot inject report text as markup',()=>{
 const f=fixture();f.report.episodes=[{evidence:'<img src=x onerror=alert(1)>'}];f.report.coverage.crosses={releases:2,contacts:1,headedShots:1};f.report.coverage.keepers={processingOpportunities:3,catches:1,parries:1};f.view.render();assert.equal(f.container.querySelector('script'),null);assert.equal(f.container.querySelector('img'),null);assert.match(f.container.textContent,/Kafa teması 1 \(şut 1, pas 0\)/);assert.match(f.container.textContent,/Kalecinin işlediği fırsat 3 · Tutuş 1 · Çelme 1/);
 f.container.querySelector('button').click();assert.equal(f.fullReads,1);assert.deepEqual(f.download,f.report);assert.notEqual(f.download,f.report);f.view.destroy();assert.equal(f.container.childElementCount,0);f.dom.window.close();
});
test('truncation and invalid measurement records remain visible',()=>{
 const f=fixture();f.report.truncatedEpisodes=12;f.view.render();assert.equal(f.container.querySelector('[role=status]').hidden,false);assert.match(f.container.querySelector('[role=status]').textContent,/ilk 12 hücumu/);
 f.report.truncatedEpisodes=0;f.report.clock.unobservedSeconds=2;f.view.render();assert.equal(f.container.querySelector('[role=status]').hidden,false);assert.match(f.container.querySelector('[role=status]').textContent,/2 sn örneklenmedi/);
 f.report.valid=false;f.view.render();assert.match(f.container.querySelector('header').textContent,/KAYIT EKSİK/);assert.match(f.container.querySelector('[role=status]').textContent,/eksik var/);f.dom.window.close();
});
