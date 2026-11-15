'use strict';
// Local-only static server for the independent GLB inspector. No external API.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json','.glb':'model/gltf-binary','.png':'image/png','.css':'text/css; charset=utf-8','.wasm':'application/wasm'};
function createServer(){
 return http.createServer((req,res)=>{
  if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end();return;}
  let name;
  try{name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);}catch{res.writeHead(400);res.end();return;}
  const file=path.resolve(root,'.'+(name==='/'?'/character-viewer.html':name));
  if(file!==root&&!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  fs.stat(file,(error,info)=>{
   if(error||!info.isFile()){res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');return;}
   res.writeHead(200,{'Content-Type':mime[path.extname(file).toLowerCase()]||'application/octet-stream','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
   if(req.method==='HEAD'){res.end();return;}
   fs.createReadStream(file).pipe(res);
  });
 });
}
if(require.main===module){
 const port=Number(process.env.PORT)||8088;
 createServer().listen(port,'127.0.0.1',()=>console.log('3D GLB viewer: http://127.0.0.1:'+port+'/character-viewer.html'));
}
module.exports={createServer};
