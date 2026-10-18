// Render local manual diagrams only; no page navigation or device access.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),q=path.join(root,'output/qualification/bf1-mermaid-render-2026-10-18-r3');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
(async()=>{
  if(fs.existsSync(q))throw Error('Preserve prior render evidence');fs.mkdirSync(q);
  const doc=fs.readFileSync(path.join(root,'docs/bf1/TECHNICAL_MANUAL.md'),'utf8').replace(/\r\n/g,'\n');
  const blocks=[...doc.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(v=>v[1]);if(blocks.length!==3)throw Error('Expected three diagrams');
  const names=['boot-and-apps','migration-and-recovery','drift-collection'];const output=path.join(root,'docs/bf1/diagrams');fs.mkdirSync(output,{recursive:true});
  const renderer=path.join(root,'tmp/bf1-mermaid-render/mermaid-10.9.3.min.js');
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--disable-networking','--disable-background-networking']});
  const records=[];
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1100}});await page.route('**/*',route=>route.abort());
    await page.setContent('<html><body style="margin:20px;background:white"><main id="render"></main></body></html>');await page.addScriptTag({path:renderer});
    await page.evaluate(()=>mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',flowchart:{htmlLabels:false,useMaxWidth:false}}));
    for(let i=0;i<blocks.length;i++){
      const svg=await page.evaluate(async ({source,index})=>{await mermaid.parse(source);const result=await mermaid.render('bf1Diagram'+index,source);document.querySelector('#render').innerHTML=result.svg;return result.svg;},{source:blocks[i],index:i});
      const count=await page.locator('svg g.node').count();if(count<5||svg.includes('Syntax error'))throw Error('Incomplete diagram');
      fs.writeFileSync(path.join(output,names[i]+'.svg'),svg);await page.locator('svg').screenshot({path:path.join(q,names[i]+'.png')});
      records.push({name:names[i],source_sha256:digest(blocks[i]),svg_sha256:digest(svg),nodes:count,passed:true});
    }
    fs.writeFileSync(path.join(q,'report.json'),JSON.stringify({passed:true,diagrams:records,renderer_version:'mermaid 10.9.3',renderer_sha256:digest(fs.readFileSync(renderer)),browser:browser.version(),board_access:false,network_requests_during_render:false},null,2)+'\n');
    console.log('PASS three Mermaid diagrams parsed, rendered and captured');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
