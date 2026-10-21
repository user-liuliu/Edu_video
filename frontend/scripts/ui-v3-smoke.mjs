import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

// Exercise the real Vue UI against isolated fixtures; no model calls or real data writes.
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:4198'
const output = path.resolve(process.env.UI_QA_OUTPUT || '../.superpowers/ui-v3-qa')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const failures = [], checks = [], unexpected = [], errors = []
const field = (key,label,value,options=[]) => ({key,label,default:value,visible:true,options:options.map(value=>({value,label:value,subjects:null})),default_by_subject:{}})
const fields = [field('prompt','想讲什么',null),field('materials','参考素材',null),field('subject','科目','数学',['数学','语文','物理']),field('grade','年级','初三',['初三','初二']),field('textbook_edition','教材版本','人教版',['人教版','统编版']),field('duration','视频时长','1',['1','3','custom']),field('aspect_ratio','视频尺寸','16:9',['16:9','9:16']),field('voice','配音声音','system:zh-CN',['system:zh-CN','model-voice']),field('web_search','允许联网搜索',true)]
fields.find(f=>f.key==='textbook_edition').default_by_subject={语文:'统编版'}
const makeSegment=(id,title,review_passed=true)=>({id,position:Number(id.slice(1))-1,title,objective:'通过生活实例理解教学内容',narration:'观察生活中的变化，联系已有知识，理解本节课的重要概念。',visuals:[{kind:'数学图形',description:'清晰展示图像变化与关键概念，平滑过渡。'}],evidence_ids:[],content_kind:'knowledge',review_notes:[],review_passed,review_issues:review_passed===false?['请补充事实依据']:[],estimated_duration_seconds:20,content_revision:1,reviewed_revision:review_passed===null?0:1})
const segments=[makeSegment('s1','认识一次函数'),makeSegment('s2','观察斜率变化',null),makeSegment('s3','联系生活中的实例',false)]
const project={id:'p1',title:'一次函数与生活',prompt:'给初三学生讲解一次函数，用生活中的实例引入。',form_values:{subject:'数学',grade:'初三',textbook_edition:'人教版',duration:'1',aspect_ratio:'16:9',voice:'system:zh-CN',web_search:true},revision:1,status:'draft',needs_regeneration:false,updated_at:'2026-10-21T01:00:00+08:00'}
const outline={project_id:'p1',title:project.title,revision:1,status:'outline_ready',needs_save:false,needs_regeneration:false,job_id:null,segments}
const preferences={enabled:true,options:{teaching:['先举例再讲概念','多用生活实例'],expression:['简洁清晰'],visual:['清晰图形'],settings:['使用系统配音']},items:[{id:'pref1',category:'teaching',value:'多用生活实例'}],suggestions:[{id:'pref2',category:'expression',value:'简洁清晰',reason:'来自你重复提交的表达要求'}]}
let role='teacher', loggedIn=true, savedMaterials=[], calls=[], htmlPreview=false
const context=await browser.newContext({viewport:{width:1440,height:1000}})
const page=await context.newPage()
page.on('pageerror',e=>errors.push(e.message))
await page.route(url=>url.pathname.startsWith('/api/'),async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname,method=req.method()
  calls.push({path:p,method,body:req.postData()})
  let body,status=200,contentType='application/json'
  if(p==='/api/auth/me'){body=loggedIn?{id:'u1',username:role==='admin'?'管理员':'王老师',role,status:'active'}:{detail:{code:'not_authenticated',message:'请登录'}};if(!loggedIn)status=401}
  else if(p==='/api/config/form')body={system_available:true,form_version:'v1',fields}
  else if(p==='/api/preferences')body=preferences
  else if(p==='/api/projects'&&method==='GET')body={items:[{...project,status:url.searchParams.get('scope')==='drafts'?'draft':'completed'}],total:1}
  else if(p==='/api/projects'&&method==='POST'){Object.assign(project,JSON.parse(req.postData()));body=project;status=201}
  else if(p==='/api/projects/p1')body=project
  else if(p==='/api/projects/p1/materials'&&method==='POST'){body={id:'m1',filename:'教学参考.pdf',size:32,status:'stored',error_message:null};savedMaterials=[body]}
  else if(p==='/api/projects/p1/materials')body=savedMaterials
  else if(p==='/api/projects/p1/outline')body=htmlPreview?{...outline,status:'outline_confirmed'}:outline
  else if(p==='/api/projects/p1/videos')body=[{id:'v1',project_id:'p1',number:1,outline_revision:1,status:htmlPreview?'preview_ready':'succeeded',duration:60,media_url:htmlPreview?null:'/fixture.mp4',html_url:htmlPreview?'/fixture.html':null,audio_url:htmlPreview?'/fixture.wav':null,playback_mode:'whole_html',aspect_ratio:'16:9',created_at:'2026-10-21',job:{id:'j1',kind:'video',status:'succeeded',stage:'已完成'},segments:segments.map((s,i)=>({id:s.id,outline_segment_id:s.id,position:i,title:s.title,narration:s.narration,start:i*20,end:(i+1)*20}))}]
  else if(p==='/api/admin/settings/form-fields')body={fields}
  else if(p==='/api/admin/settings/generation-params')body={max_concurrent_jobs:2,max_retries:2,duration_tolerance_pct:15,long_term_memory_enabled:true}
  else if(p==='/api/admin/settings/registration')body={open:true}
  else if(p==='/api/admin/users')body={items:[{id:'u2',username:'张老师',role:'teacher',status:'active',created_at:'2026-10-21T01:00:00Z',video_count:2}],total:1}
  else if(p==='/api/admin/model-configs')body=[['outline_llm','写大纲/讲稿'],['review_llm','审核'],['vision_llm','看图识别'],['tts','配音']].map(([purpose,label])=>({purpose,label,required:true,base_url:'https://model.example/v1',model:'configured-model',enabled:true,api_key_status:'set',api_key_masked:'已配置',voices:[],last_test_ok:true,last_test_message:'连接正常',last_tested_at:'2026-10-21T01:00:00Z'}))
  else {unexpected.push(method+' '+p);body={detail:{code:'fixture_missing',message:'未配置测试数据'}};status=404}
  await route.fulfill({status,contentType,body:JSON.stringify(body)})
})
const videoFixture=process.env.UI_VIDEO_FIXTURE?await readFile(process.env.UI_VIDEO_FIXTURE):null
await page.route('**/fixture.mp4',route=>route.fulfill(videoFixture?{contentType:'video/mp4',body:videoFixture}:{status:204,body:''}))
// Synthetic silent media tests the existing player without generating content.
const silentAudio=Buffer.alloc(44+8000*2*60)
silentAudio.write('RIFF',0);silentAudio.writeUInt32LE(silentAudio.length-8,4);silentAudio.write('WAVEfmt ',8);silentAudio.writeUInt32LE(16,16);silentAudio.writeUInt16LE(1,20);silentAudio.writeUInt16LE(1,22);silentAudio.writeUInt32LE(8000,24);silentAudio.writeUInt32LE(16000,28);silentAudio.writeUInt16LE(2,32);silentAudio.writeUInt16LE(16,34);silentAudio.write('data',36);silentAudio.writeUInt32LE(silentAudio.length-44,40)
await page.route('**/fixture.wav',route=>route.fulfill({contentType:'audio/wav',body:silentAudio}))
await page.route('**/fixture.html',route=>route.fulfill({contentType:'text/html',body:"<!doctype html><html><body><p id=time>0</p><script>window.seek=t=>document.getElementById('time').textContent=String(t);addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='edu-preview:init')parent.postMessage({type:'edu-preview:ready',channel:e.data.channel},'*')})</script></body></html>"}))
async function check(name,fn){try{await fn();checks.push(name)}catch(e){failures.push({name,error:e.message})}}
async function visit(url){await page.goto(base+url);await page.locator('h1').first().waitFor({state:'attached'});await page.locator('.el-loading-mask').waitFor({state:'hidden'});await page.waitForTimeout(350)}
async function layout(name,url,width){
 await page.setViewportSize({width,height:1000});await visit(url)
 await check(name+' no horizontal overflow',async()=>{const x=await page.evaluate(()=>({page:document.documentElement.scrollWidth,viewport:innerWidth}));assert.ok(x.page<=x.viewport+1,JSON.stringify(x))})
 await page.screenshot({path:path.join(output,name+'.png'),fullPage:true})
}
try{
 await page.setViewportSize({width:1227,height:800});await visit('/projects/new')
 await check('sidebar collapse preserves unsaved input and navigation',async()=>{
  assert.equal(await page.getByText('教师工作台',{exact:true}).count(),0)
  assert.equal(await page.locator('.creation-title').count(),0)
  const composer=await page.locator('.creation-composer').boundingBox();assert.ok(composer.y<210)
  assert.equal(await page.locator('.creation-welcome').textContent(),'今天讲点啥？')
  assert.equal(await page.locator('header .rail-toggle').count(),0)
  assert.equal(await page.locator('aside .rail-toolbar .rail-toggle').count(),1)
  await page.locator('textarea').fill('收起侧栏后仍然保留的需求')
  const before=await page.locator('.side-rail').boundingBox()
  await page.getByRole('button',{name:'收起侧边栏',exact:true}).click();await page.waitForTimeout(350)
  const after=await page.locator('.side-rail').boundingBox();assert.ok(after.width<before.width);assert.equal(Math.round(after.width),72)
  assert.equal(await page.locator('textarea').inputValue(),'收起侧栏后仍然保留的需求')
  assert.equal(await page.locator('.rail-link').count(),5)
  await page.screenshot({path:path.join(output,'sidebar-collapsed.png'),fullPage:true,animations:'allow'})
  await page.getByRole('button',{name:'展开侧边栏',exact:true}).click();await page.waitForTimeout(350)
  assert.equal(Math.round((await page.locator('.side-rail').boundingBox()).width),Math.round(before.width))
 })
 for(const [width,height] of [[1440,900],[1366,768],[1227,676],[906,676],[832,676]]){
  await page.setViewportSize({width,height});await visit('/projects/new')
  await check('creation fits one screen '+width+'x'+height,async()=>{
   const g=await page.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth}));assert.ok(g.height<=g.viewport+1,JSON.stringify(g));assert.ok(g.width<=g.viewportWidth+1)
   const composer=await page.locator('.creation-composer').boundingBox();const main=await page.locator('.app-main').boundingBox();assert.ok(composer.width/main.width>.85)
   await page.getByRole('button',{name:'使用说明',exact:true}).click();await page.getByText('系统配音在服务器离线生成，不调用配音模型，不消耗配音模型额度；声音较机械。预览和导出使用同一份配音，支持简单快慢调整，不支持克隆音色或复杂情感。',{exact:true}).waitFor({state:'visible'});await page.mouse.click(1,1)
   await page.getByRole('button',{name:'查看素材上传说明',exact:true}).click();await page.getByText('可以先选择素材，未保存前不会上传。',{exact:true}).waitFor({state:'visible'});await page.mouse.click(1,1)
  })
  await page.screenshot({path:path.join(output,'compact-create-'+width+'.png'),fullPage:true})
 }
 for(const width of [1440,832,390,320]){
  await layout('create-'+width,'/projects/new',width)
  await check('settings columns '+width,async()=>{const columns=await page.locator('.creation-settings-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);assert.equal(columns,width<=650?2:width<=900?6:3);assert.equal(await page.locator('.creation-settings-grid .el-select').count(),6)})
 }
 await page.setViewportSize({width:1440,height:1000});await visit('/projects/new')
 await check('subject defaults, explicit save and pending attachment preserved',async()=>{
  await page.locator('[data-testid=project-title] input, input[data-testid=project-title]').fill('二次函数课堂')
  await page.locator('textarea').fill('讲解二次函数和抛物线')
  await page.locator('.el-select').filter({has:page.getByRole('combobox',{name:'科目',exact:true})}).click();await page.getByRole('option',{name:'语文',exact:true}).click()
  assert.ok((await page.locator('.el-select').filter({has:page.getByRole('combobox',{name:'教材版本',exact:true})}).textContent()).includes('统编版'))
  await page.getByLabel('上传参考素材').setInputFiles({name:'教学参考.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 fixture')})
  assert.equal(calls.filter(c=>c.method==='POST').length,0)
  await page.getByTestId('save-draft').click();await page.getByText('已保存为草稿',{exact:true}).waitFor()
  const post=calls.find(c=>c.path==='/api/projects'&&c.method==='POST');assert.ok(post);assert.equal(JSON.parse(post.body).form_values.textbook_edition,'统编版')
  await page.getByText('已保存，生成时解析',{exact:false}).waitFor();assert.equal(await page.getByText('教学参考.pdf',{exact:true}).count(),1)
 })
 for(const width of [1440,390,320])for(const [name,url] of [['videos','/projects'],['drafts','/drafts'],['preferences','/preferences'],['account','/?section=account'],['outline','/projects/p1/outline'],['video','/projects/p1/video']])await layout(name+'-'+width,url,width)
 if(videoFixture)await check('project cards display paused MP4 first frame',async()=>{
  await page.setViewportSize({width:1227,height:800});await visit('/projects')
  await page.locator('.video-cover video.ready').waitFor()
  const state=await page.locator('.video-cover video').evaluate(v=>({paused:v.paused,time:v.currentTime,width:v.videoWidth}))
  assert.equal(state.paused,true);assert.ok(state.time<.01);assert.ok(state.width>0)
  await page.screenshot({path:path.join(output,'video-cover.png'),fullPage:true})
 })
 await page.setViewportSize({width:1440,height:1000});await visit('/projects/p1/outline')
 await check('outline audit states and editing remain functional',async()=>{assert.equal(await page.getByText('AI已审核',{exact:true}).count(),1);assert.equal(await page.getByText('待审核',{exact:true}).count(),1);assert.equal(await page.getByText('审核未通过',{exact:true}).count(),1);await page.getByLabel('段落标题 1',{exact:true}).fill('修改后的片段');assert.equal(await page.getByText('待审核',{exact:true}).count(),2)})
 htmlPreview=true
 await check('HTML only project cards render a frozen first frame without narration',async()=>{
  await visit('/projects');await page.locator('.video-cover .cover-frame.ready').waitFor()
  assert.equal(await page.frameLocator('.video-cover iframe').locator('#time').textContent(),'0')
  assert.equal(await page.locator('.video-cover audio').count(),0)
  await page.screenshot({path:path.join(output,'html-cover.png'),fullPage:true})
 })
 for(const width of [1440,390,320]){
  await layout('html-preview-'+width,'/projects/p1/video',width)
  await page.locator('.html-player[aria-busy="false"]').waitFor()
  await page.screenshot({path:path.join(output,'html-preview-'+width+'.png'),fullPage:true})
 }
 await check('HTML preview playback, chapter seeking and export control preserved',async()=>{
  await page.getByRole('button',{name:'播放',exact:true}).click();await page.getByRole('button',{name:'暂停',exact:true}).click()
  await page.locator('.teaching-list button').nth(1).click()
  await page.waitForFunction(()=>document.querySelector('.clock')?.textContent?.includes('0:20'))
  assert.equal(await page.frameLocator('iframe[title="教学动画"]').locator('#time').textContent(),'20')
  assert.equal(await page.getByRole('button',{name:'满意，导出MP4',exact:true}).count(),1)
  assert.equal(await page.locator('.player-error').count(),0)
 })
 htmlPreview=false
 role='admin'
 for(const width of [1440,390,320])for(const [name,url] of [['page-config','/admin/page-config'],['model-config','/admin/model-config'],['users','/admin/users']])await layout(name+'-'+width,url,width)
 await check('admin has only admin rail entries',async()=>{assert.deepEqual(await page.locator('.rail-link').allTextContents(),['页面配置','模型配置','用户管理'])})
 loggedIn=false
 for(const width of [1440,390,320])await layout('login-'+width,'/login',width)
 await check('no runtime errors',async()=>assert.deepEqual(errors,[]))
 await check('no unexpected API calls',async()=>assert.deepEqual(unexpected,[]))
}finally{await browser.close()}
const result={base,checks,failures,errors,unexpected,screenshots:output}
await writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2))
console.log(JSON.stringify(result,null,2))
if(failures.length)process.exitCode=1
