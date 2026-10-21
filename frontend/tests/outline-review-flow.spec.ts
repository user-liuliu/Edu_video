import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import ElementPlus,{ElMessageBox} from 'element-plus'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory} from 'vue-router'
import OutlineView from '../src/views/workbench/OutlineView.vue'

let wrapper:VueWrapper|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined;ElMessageBox.close();document.body.innerHTML='';vi.unstubAllGlobals();vi.useRealTimers();vi.restoreAllMocks()})
const makeSegment=(id:string,passed:boolean|null=true)=>({id,position:0,title:id,objective:'理解电路',narration:'同学们好',visuals:[{kind:'文字卡',description:'电路图'}],evidence_ids:[],content_kind:'knowledge',review_notes:['请教师核对教材'],content_revision:1,reviewed_revision:passed===null?0:1,review_passed:passed,review_issues:passed===false?['公式错误']:[],estimated_duration_seconds:3})
async function setup(segments=[makeSegment('s1')],needsSave=false,status='outline_ready'){
 vi.useFakeTimers()
 let data:any={project_id:'p1',title:'串联电路',revision:2,status,segments,job_id:null,needs_regeneration:false,needs_save:needsSave}
 let failSave=false,jobStatus='running'
 const calls:{url:string;method:string;body:any}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method||'GET',body=init?.body?JSON.parse(String(init.body)):null
  calls.push({url,method,body})
  if(method==='PUT'){
   if(failSave)return new Response(JSON.stringify({detail:{code:'conflict',message:'保存版本冲突'}}),{status:409})
   const updatedSegments=body.segments.map((s:any)=>{
    if(s.narration!=='同学们好')return {...s,content_revision:2,review_passed:null,reviewed_revision:1,review_issues:[]}
    return s
   })
   data={...data,revision:data.revision+1,needs_save:false,segments:updatedSegments}
   return new Response(JSON.stringify(data))
  }
  if(url.endsWith('/review')&&method==='POST')return new Response(JSON.stringify({id:'j1',kind:'review',status:'running',stage:'审核大纲',progress:80}))
  if(url.includes('/jobs/')){
   if(jobStatus==='succeeded')data={...data,revision:data.revision+1,segments:data.segments.map((s:any)=>({...s,review_passed:true,review_issues:[],reviewed_revision:s.content_revision}))}
   return new Response(JSON.stringify({id:'j1',kind:'review',status:jobStatus,stage:'审核大纲',progress:80,error_message:jobStatus==='failed'?'模型调用超时，请稍后重试':null}))
  }
  if(url.endsWith('/confirm')&&method==='POST')data={...data,revision:data.revision+1,status:'outline_confirmed'}
  return new Response(JSON.stringify(data))
 }))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView},{path:'/projects/:id/video',name:'project-video',component:{template:'<div>视频预览</div>'}}]})
 await router.push('/projects/p1/outline')
 wrapper=mount(OutlineView,{attachTo:document.body,global:{plugins:[router,ElementPlus]}});await flushPromises()
 return {w:wrapper,calls,setFailSave:(v:boolean)=>failSave=v,setJob:(v:string)=>jobStatus=v}
}
async function click(text:string){const button=wrapper!.findAll('button').find(b=>b.text()===text);expect(button,`button ${text}`).toBeDefined();await button!.trigger('click');await flushPromises()}
async function dialogClick(text:string){const button=[...document.querySelectorAll<HTMLButtonElement>('.el-message-box button')].find(b=>b.textContent?.trim()===text);expect(button,`dialog button ${text}`).toBeDefined();button!.click();await flushPromises()}

test('saving unapproved segments persists content then offers review with separate counts',async()=>{
 const {w,calls}=await setup([makeSegment('pending',null),makeSegment('failed',false)])
 await click('保存大纲')
 expect(calls.some(c=>c.method==='PUT')).toBe(true)
 expect(document.querySelector('.el-message-box')?.textContent).toContain('大纲已保存')
 expect(document.querySelector('.el-message-box')?.textContent).toContain('待审核 1 段、审核未通过 1 段')
 expect(calls.some(c=>c.url.endsWith('/review'))).toBe(false)
 await dialogClick('去审核')
 expect(calls.find(c=>c.url.endsWith('/review'))?.body.revision).toBe(3)
 expect(w.get('[aria-label="逐字稿 1"]').attributes('disabled')).toBeDefined()
})

test('continue editing after save does not silently call the model',async()=>{
 const {w,calls}=await setup([makeSegment('pending',null)])
 await click('保存大纲');await dialogClick('继续编辑')
 expect(calls.some(c=>c.url.endsWith('/review'))).toBe(false)
 expect(w.get('.segment header .el-tag').text()).toBe('待审核')
})

test('confirmation explains save requirement and only confirms the explicitly saved version',async()=>{
 const {calls,w}=await setup([makeSegment('s1')],true)
 await click('确认大纲')
 expect(w.text()).toContain('请先保存大纲')
 expect(calls.some(c=>c.url.endsWith('/confirm'))).toBe(false)
 await click('保存大纲');await dialogClick('知道了')
 await click('确认大纲');await dialogClick('确认大纲')
 expect(calls.find(c=>c.url.endsWith('/confirm'))?.body.revision).toBe(3)
 expect(w.vm.$router.currentRoute.value.name).toBe('project-video')
 expect(w.text()).toContain('大纲已确认')
})

test('pending and rejected segments cannot be confirmed even after saving',async()=>{
 const {w,calls}=await setup([makeSegment('pending',null),makeSegment('failed',false)])
 await click('保存大纲');await dialogClick('继续编辑')
 await click('确认大纲')
 expect(w.text()).toContain('存在未通过审核的片段')
 expect(calls.some(c=>c.url.endsWith('/confirm'))).toBe(false)
})

test('review saves dirty content first and a failed save prevents any model job',async()=>{
 const {w,calls,setFailSave}=await setup()
 await w.get('[aria-label="逐字稿 1"]').setValue('修改后的讲稿')
 expect(w.get('.segment header .el-tag').text()).toBe('待审核')
 setFailSave(true)
 await click('审核待处理片段')
 expect(w.text()).toContain('保存版本冲突')
 expect(calls.some(c=>c.url.endsWith('/review'))).toBe(false)
 expect(w.get('[aria-label="逐字稿 1"]').element.value).toBe('修改后的讲稿')
})

test('a review timeout preserves pending content and allows retry',async()=>{
 const {w,calls,setJob}=await setup([makeSegment('pending',null)])
 await click('审核待处理片段')
 setJob('failed');await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(w.text()).toContain('模型调用超时')
 expect(w.get('.segment header .el-tag').text()).toBe('待审核')
 expect(w.find('[data-testid="live-outline-progress"]').exists()).toBe(false)
 await click('重试失败任务')
 expect(calls.filter(c=>c.url.endsWith('/review'))).toHaveLength(2)
})

test('successful review unlocks confirmation without another save and without old rejection',async()=>{
 const {w,calls,setJob}=await setup([makeSegment('failed',false)])
 await click('审核待处理片段')
 setJob('succeeded');await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(w.get('.segment header .el-tag').text()).toBe('AI已审核')
 expect(w.find('[aria-label="未通过原因"]').exists()).toBe(false)
 await click('确认大纲');await dialogClick('确认大纲')
 expect(calls.some(c=>c.method==='PUT')).toBe(false)
 expect(calls.find(c=>c.url.endsWith('/confirm'))?.body.revision).toBe(3)
})

test('review saves an edited version once before submission and prevents duplicate jobs',async()=>{
 const {w,calls}=await setup()
 await w.get('[aria-label="逐字稿 1"]').setValue('修改后的讲稿')
 await click('审核待处理片段')
 expect(calls.filter(c=>c.method==='PUT')).toHaveLength(1)
 expect(calls.filter(c=>c.url.endsWith('/review'))).toHaveLength(1)
 expect(calls.find(c=>c.url.endsWith('/review'))?.body.revision).toBe(3)
 expect(calls.findIndex(c=>c.method==='PUT')).toBeLessThan(calls.findIndex(c=>c.url.endsWith('/review')))
 await click('审核待处理片段')
 expect(calls.filter(c=>c.url.endsWith('/review'))).toHaveLength(1)
 expect(w.get('[aria-label="逐字稿 1"]').attributes('disabled')).toBeDefined()
})

test('failed review submission keeps the editor usable without a false red verdict',async()=>{
 const {w,calls}=await setup([makeSegment('s1',null)])
 const originalFetch=globalThis.fetch
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>url.endsWith('/review')
  ?new Response(JSON.stringify({detail:{code:'system_unavailable',message:'审核模型暂不可用'}}),{status:409})
  :originalFetch(url,init)))
 await click('审核待处理片段')
 expect(w.text()).toContain('审核模型暂不可用')
 expect(w.get('.segment header .el-tag').text()).toBe('待审核')
 expect(w.get('[aria-label="逐字稿 1"]').attributes('disabled')).toBeUndefined()
 expect(calls.some(c=>c.url.endsWith('/confirm'))).toBe(false)
})

test.each(['preview_ready','video_exporting'])('outline in %s opens existing preview without reconfirming',async(status)=>{
 const {w,calls}=await setup([makeSegment('s1')],false,status)
 await click('进入视频预览')
 expect(w.vm.$router.currentRoute.value.name).toBe('project-video')
 expect(calls.some(c=>c.url.endsWith('/confirm'))).toBe(false)
})
