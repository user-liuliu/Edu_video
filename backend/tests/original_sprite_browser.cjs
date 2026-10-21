const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve(__dirname,'../../pixel-art/original-cast'),output=path.resolve(__dirname,'../../.superpowers/asset-expansion');
 console.log('Starting original cast browser check');
 const browser=await chromium.launch({channel:'chrome',headless:true,timeout:30000});
 try{
  const page=await browser.newPage({viewport:{width:1380,height:1200}}),errors=[],network=[];
  page.setDefaultTimeout(15000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>{network.push(r.request().url());r.abort()});
  await page.setContent(fs.readFileSync(path.join(root,'catalog.html'),'utf8'),{waitUntil:'load'});
  console.log('Catalog document loaded');
  await page.evaluate(()=>window.catalogReady);
  console.log('All original sprite images decoded');
  await page.click('#play');
  const checks=[];
  for(const direction of ['down','left','right','up'])for(const action of ['idle','walk','run','wave','nod','talk','pickup','carry','sit','jump','work']){
   await page.selectOption('#direction',direction);await page.selectOption('#action',action);
   await page.evaluate(()=>window.seekCatalog(.3));
   const first=await page.evaluate(()=>document.getElementById('cast').toDataURL()+'|'+document.getElementById('actions').toDataURL());
   await page.evaluate(()=>window.seekCatalog(.6));
   const later=await page.evaluate(()=>document.getElementById('cast').toDataURL()+'|'+document.getElementById('actions').toDataURL());
   if(['walk','run','wave','carry','jump','pickup'].includes(action))assert.notEqual(first,later,action+' must change pixels: '+direction);
   await page.evaluate(()=>window.seekCatalog(7));await page.evaluate(()=>window.seekCatalog(.3));
   assert.equal(await page.evaluate(()=>document.getElementById('cast').toDataURL()+'|'+document.getElementById('actions').toDataURL()),first,'Reverse seek: '+action+' '+direction);
   checks.push({direction,action});
   if(action==='work')console.log('Checked direction: '+direction);
  }
  await page.selectOption('#action','idle');await page.selectOption('#direction','down');await page.evaluate(()=>window.seekCatalog(0));
  await page.screenshot({path:path.join(output,'catalog-browser.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  const result={checks:checks.length,characters:20,offline:true,reverse_seek:true,errors,network};
  fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
