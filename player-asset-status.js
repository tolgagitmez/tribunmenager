'use strict';
/* Shared, read-only asset diagnostics. Provenance strings are declarations;
   source/licence evidence and packaged-file hashes are checked separately. */
(function(root){
const states=Object.freeze(['loading','ready','missing','invalid','webgl-unavailable','renderer-error']);
const boneNames=Object.freeze(['pelvis','spine','chest','neck','head','clavicle.L','upper_arm.L','forearm.L','hand.L','thigh.L','shin.L','foot.L','clavicle.R','upper_arm.R','forearm.R','hand.R','thigh.R','shin.R','foot.R']);
const expectedPath='assets/player/player-model-data.js';
let scriptFailure=null;
function scriptFailed(url){
 const entry=root.performance?.getEntriesByName?.(url)?.slice(-1)[0],status=entry?.responseStatus;
 scriptFailure=(status?'HTTP '+status:'HTTP/ağ yükleme hatası')+' · '+url;return scriptFailure;
}
const clean=(value,max=500)=>typeof value==='string'?value.slice(0,max):'';
const finiteArray=(value,size)=>Array.isArray(value)&&value.length===size&&value.every(Number.isFinite);
function declaredMetadata(assets,manifest){
 const a=assets&&typeof assets==='object'?assets:{},m=manifest&&typeof manifest==='object'?manifest:a.metadata||a.provenance||{};
 const licence=m.license??a.license,source=m.source??a.source;
 const license=clean(typeof licence==='string'?licence:licence?.spdx||licence?.id||licence?.name,120);
 const sourceText=clean(typeof source==='string'?source:source?.url||source?.name,800);
 const files=Array.isArray(m.files)?m.files.slice(0,100).map(f=>typeof f==='string'?{path:clean(f,300)}:{path:clean(f?.path,300),sha256:clean(f?.sha256,64)}):[];
 return {id:clean(m.id||m.modelId||a.id,120),version:clean(String(m.version??a.version??''),80),license,source:sourceText,files,declaredOnly:true};
}
function decodeBase64(value){
 if(typeof value!=='string')throw Error('Base64 veri metni gerekli.');
 const normalized=value.replace(/\s/g,'');
 if(!normalized.length||normalized.length%4!==0||!/^[A-Za-z0-9+/]*={0,2}$/.test(normalized))throw Error('Base64 veri biçimi geçersiz.');
 const binary=typeof atob==='function'?atob(normalized):Buffer.from(normalized,'base64').toString('binary'),bytes=new Uint8Array(binary.length);
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);return bytes.buffer;
}
function validate(assets){
 const errors=[],warnings=[],summary={boneCount:0,lods:[],metadata:declaredMetadata(assets)};
 const fail=(code,path,message)=>errors.push({code,path,message});
 if(!assets||typeof assets!=='object'||Array.isArray(assets))return {ok:false,errors:[{code:'ASSET_MISSING',path:expectedPath,message:'Oyuncu model verisi bulunamadı.'}],warnings,summary};
 const bones=assets.bones;
 if(!Array.isArray(bones)||bones.length!==19)fail('BONE_COUNT','bones','Bu çizici için 19 deform kemiği gerekli.');
 else{
  summary.boneCount=bones.length;const seen=new Set();
  bones.forEach((bone,i)=>{
   const path='bones['+i+']';
   if(!bone||!boneNames.includes(bone.name)||seen.has(bone.name))fail('BONE_NAME',path+'.name','Kemik adı eksik, yinelenmiş veya çiziciyle uyumsuz.');
   seen.add(bone?.name);
   if(!finiteArray(bone?.head,3)||!finiteArray(bone?.tail,3))fail('BONE_ENDPOINT',path,'Kemik başı ve sonu üç sonlu koordinat içermeli.');
   else if(Math.hypot(...bone.tail.map((v,j)=>v-bone.head[j]))<1e-6)fail('BONE_LENGTH',path,'Sıfır uzunluklu kemik çizilemez.');
   if(!finiteArray(bone?.matrix,16)||!finiteArray(bone?.inverseBind,16))fail('BONE_MATRIX',path,'Kemik ve inverse-bind matrisleri 16 sonlu sayı içermeli.');
  });
  if(bones[8]?.name!=='hand.L'||bones[15]?.name!=='hand.R')fail('HAND_BONE_ORDER','bones','Kaleci el malzemesi hand.L=8 ve hand.R=15 kemik sırasını gerektirir.');
 }
 if(!Array.isArray(assets.lods)||!assets.lods.length)fail('LOD_MISSING','lods','En az bir çizilebilir ayrıntı düzeyi gerekli.');
 else assets.lods.forEach((lod,i)=>{
  const path='lods['+i+']';let vertices,indices;
  try{const buffer=decodeBase64(lod?.vertices);if(buffer.byteLength%80!==0||buffer.byteLength<240)throw Error('Köşe verisi 80 baytlık kayıtlar ve en az üç köşe içermeli.');vertices=new Float32Array(buffer);}
  catch(error){fail('VERTEX_BUFFER',path+'.vertices',clean(error.message));}
  try{if(!['H','I'].includes(lod?.indexType))throw Error('İndis türü H veya I olmalı.');const buffer=decodeBase64(lod?.indices),width=lod.indexType==='H'?2:4;if(buffer.byteLength%width!==0||buffer.byteLength<width*3)throw Error('İndis verisinin bayt uzunluğu geçersiz.');indices=lod.indexType==='H'?new Uint16Array(buffer):new Uint32Array(buffer);if(indices.length%3!==0)throw Error('Üçgen indis sayısı üçün katı olmalı.');}
  catch(error){fail('INDEX_BUFFER',path+'.indices',clean(error.message));}
  if(!vertices||!indices)return;
  const vertexCount=vertices.length/20,bounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]},usedBones=new Set();let invalidFloat=false,invalidJoint=false,invalidWeight=false,invalidNormal=false;
  for(let n=0;n<vertexCount;n++){
   const at=n*20;
   for(let k=0;k<20;k++)if(!Number.isFinite(vertices[at+k]))invalidFloat=true;
   for(let k=0;k<3;k++){bounds.min[k]=Math.min(bounds.min[k],vertices[at+k]);bounds.max[k]=Math.max(bounds.max[k],vertices[at+k]);}
   if(Math.hypot(vertices[at+3],vertices[at+4],vertices[at+5])<1e-6)invalidNormal=true;
   let sum=0;
   for(let k=0;k<4;k++){
    const joint=vertices[at+8+k],weight=vertices[at+12+k];
    if(!Number.isInteger(joint)||joint<0||joint>=19)invalidJoint=true;
    if(!Number.isFinite(weight)||weight<0||weight>1)invalidWeight=true;
    if(weight>0)usedBones.add(joint);sum+=weight;
   }
   if(!Number.isFinite(sum)||Math.abs(sum-1)>.015)invalidWeight=true;
  }
  if(invalidFloat)fail('NONFINITE_VERTEX',path+'.vertices','Köşe verisinde sonlu olmayan sayı var.');
  if(invalidNormal)fail('ZERO_NORMAL',path+'.vertices','Yüzey normalinin uzunluğu sıfır olamaz.');
  if(invalidJoint)fail('JOINT_RANGE',path+'.vertices','Köşe kemik indisleri 0–18 aralığında tam sayı olmalı.');
  if(invalidWeight)fail('SKIN_WEIGHTS',path+'.vertices','Deri ağırlıkları 0–1 aralığında olmalı ve toplamları bire yakın olmalı.');
  if(indices.some(index=>index>=vertexCount))fail('INDEX_RANGE',path+'.indices','Üçgen indisi köşe tamponunun dışına çıkıyor.');
  const height=bounds.max[1]-bounds.min[1];if(Number.isFinite(height)&&(height<.5||height>3))warnings.push({code:'MODEL_SCALE',path,message:'Modelin metre ölçeği ve boyu görsel olarak doğrulanmalı.'});
  summary.lods.push({index:i,vertexCount,indexCount:indices.length,triangleCount:indices.length/3,indexType:lod.indexType,skinnedBoneCount:usedBones.size,bounds});
 });
 if(!summary.metadata.license||!summary.metadata.source)warnings.push({code:'PROVENANCE_UNDECLARED',path:'metadata',message:'Kaynak/lisans bildirimi model verisinde belirtilmemiş; paket kredi kaydı ayrıca doğrulanmalı.'});
 return {ok:errors.length===0,errors,warnings,summary};
}
function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
function inspect(options={}){
 const {assets,renderer,rendererError,loading=false,webgl=true}=options,loadError=options.loadError||scriptFailure,validation=options.validation||validate(assets),provenance=declaredMetadata(assets,options.manifest),details=[];
 let state,label,message;
 if(webgl===false){state='webgl-unavailable';label='2D YEDEK GÖRÜNÜM';message='WebGL kullanılamıyor. Ayrıntılı oyuncu modeli için tarayıcının grafik hızlandırmasını kontrol et.';}
 else if(loading){state='loading';label='OYUNCU MODELİ YÜKLENİYOR';message='Oyuncu modeli, iskelet verileri ve dokular yükleniyor.';}
 else if(!assets){state='missing';label='YEDEK OYUNCU MODELİ';message='Oyuncu model dosyası yüklenemedi. Paketi tamamen çıkartıp yerel başlatıcıyla yeniden aç.';details.push('Beklenen dosya: '+(options.expectedPath||expectedPath));}
 else if(!validation.ok){state='invalid';label='OYUNCU MODELİ GEÇERSİZ';message='Oyuncu model verisi çiziciyle uyumlu değil. Teknik ayrıntılarda hatalı dosya veya veri alanı belirtiliyor.';}
 else if(rendererError){state='renderer-error';label='YEDEK OYUNCU MODELİ';message='Oyuncu modeli veya dokuları hazırlanamadı. Teknik ayrıntılarda eksik dosya ya da grafik hatası belirtiliyor.';}
 else if(!renderer){state='loading';label='OYUNCU ÇİZİCİSİ HAZIRLANIYOR';message='Oyuncu verisi doğrulandı; 3D çizici hazırlanıyor.';}
 else{state='ready';label='İSKELETLİ OYUNCU MODELİ';message='Paketlenmiş iskeletli oyuncu modeli çizime hazır.';}
 if(loadError)details.push('Yükleme: '+clean(typeof loadError==='string'?loadError:loadError.message));
 if(rendererError)details.push('Çizici: '+clean(typeof rendererError==='string'?rendererError:rendererError.message));
 for(const item of validation.errors)details.push(item.code+' · '+item.path+': '+item.message);
 for(const item of validation.warnings)details.push(item.code+' · '+item.message);
 return freeze({state,label,message,details,modelId:provenance.id||null,summary:validation.summary,provenance});
}
function mount(element,status){
 if(!element)return null;const document=element.ownerDocument;
 element.dataset.playerAssetState=status.state;element.dataset.playerModelState=status.state;
 const box=document.createElement('details'),title=document.createElement('summary'),copy=document.createElement('p');title.textContent=status.label;copy.textContent=status.message;box.append(title,copy);
 const information=[status.modelId?'Model: '+status.modelId:null,status.provenance.version?'Sürüm: '+status.provenance.version:null,status.provenance.license?'Lisans kaydı: '+status.provenance.license:null,status.provenance.source?'Kaynak: '+status.provenance.source:null,'Kaynak belgeleri ve dosya özetleri: assets/player/CREDITS.md ve assets/player/manifest.json.',...status.details].filter(Boolean);
 const list=document.createElement('ul');for(const line of information){const row=document.createElement('li');row.textContent=line;list.append(row);}box.append(list);element.replaceChildren(box);return box;
}
const api={states,boneNames,expectedPath,declaredMetadata,validate,inspect,mount,scriptFailed};root.TribunPlayerAssetStatus=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
