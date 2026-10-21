/* Real offline browser checks, invoked with a temporary output directory. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=process.argv[2],browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[],network=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{network.push(route.request().url());route.abort()});
  await page.setContent(fs.readFileSync(path.join(root,'runtime-check.html'),'utf8'),{waitUntil:'load'});
  await page.evaluate(()=>window.sceneReady);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const poses=[];
  for(const t of [0,.4,.8,1.2,2,2.8,3.5,4]){
   await page.evaluate(t=>window.seek(t),t);
   poses.push(await page.screenshot({path:path.join(root,'motion-'+t+'.png')}));
  }
  assert(!poses[0].equals(poses[4]),'Travel changes real pixels');
  for(const index of [7,4,2,0]){
   await page.evaluate(t=>window.seek(t),[0,.4,.8,1.2,2,2.8,3.5,4][index]);
   assert((await page.screenshot()).equals(poses[index]),'Reverse seek matches sprite pixels');
  }
  assert.deepEqual(await page.evaluate(()=>window.filmDiagnostics),[]);
  assert.deepEqual(errors,[]);assert.deepEqual(network,[],'No asset or script network calls');
  if(fs.existsSync(path.join(root,'playback.html'))){
   await page.goto('about:blank');
   await page.setContent(fs.readFileSync(path.join(root,'playback.html'),'utf8'),{waitUntil:'load'});
   await page.evaluate(()=>window.sceneReady);
   const duration=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8')).duration;
   for(const [index,ratio] of [0,.12,.25,.4,.55,.7,.85,.99].entries()){
    await page.evaluate(t=>window.seek(t),duration*ratio);
    await page.screenshot({path:path.join(root,'sample-'+index+'.png')});
   }
   const t=duration*.55;await page.evaluate(t=>window.seek(t),t);const a=await page.screenshot();
   await page.evaluate(t=>window.seek(t),duration*.2);await page.evaluate(t=>window.seek(t),t);
   assert((await page.screenshot()).equals(a));assert.deepEqual(await page.evaluate(()=>window.filmDiagnostics),[]);
  }
  const result={offline:true,decoded:true,reverse_seek:true,frames:poses.length,errors,network};
  fs.writeFileSync(path.join(root,'motion-browser-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
