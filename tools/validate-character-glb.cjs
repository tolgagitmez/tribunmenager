'use strict';
/* Official Khronos glTF Validator smoke check (run after installing gltf-validator). */
const fs=require('node:fs');
const path=require('node:path');
const validator=require('gltf-validator');
const inputs=process.argv.slice(2);
if(!inputs.length)inputs.push('assets/player/tribun-base-footballer.glb');
async function main(){
 let errors=0;
 for(const file of inputs){
  const resolved=path.resolve(file),blob=new Uint8Array(fs.readFileSync(resolved));
  const report=await validator.validateBytes(blob,{uri:path.basename(file),maxIssues:1000});
  const issues=report.issues||{},name=path.basename(file);
  console.log(name+': '+JSON.stringify({errors:issues.numErrors,warnings:issues.numWarnings,infos:issues.numInfos,hints:issues.numHints}));
  for(const issue of issues.messages||[])if(issue.severity===0||issue.severity===1){
   console.log('  '+issue.code+': '+issue.message+(issue.pointer?' @ '+issue.pointer:''));
  }
  fs.writeFileSync(resolved+'.validation.json',JSON.stringify(report,null,2)+'\n');
  errors+=issues.numErrors||0;
 }
 if(errors)process.exitCode=1;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
