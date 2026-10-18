import {mount,flushPromises} from '@vue/test-utils'
import ElementPlus, {ElMessageBox} from 'element-plus'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory} from 'vue-router'
import OutlineView from '../src/views/workbench/OutlineView.vue'

afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()})
test('loads full outline, edits a segment and saves actual content',async()=>{
 const alertDialog=vi.spyOn(ElMessageBox,'alert').mockResolvedValue()
 const calls:{url:string;init?:RequestInit}[]=[]
 const outline={project_id:'p1',revision:2,status:'outline_ready',segments:[{id:'s1',position:0,title:'开场',objective:'理解概念',narration:'同学们好',visuals:[{kind:'文字卡',description:'概念标题'}],evidence_ids:[],content_kind:'knowledge',review_notes:['未核实出处'],content_revision:1,reviewed_revision:1,review_passed:true,review_issues:[],estimated_duration_seconds:3}]}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return new Response(JSON.stringify(outline))}))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView},{path:'/projects/:id/edit',name:'project-edit',component:{template:'<div />'}}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(w.text()).toContain('未核实出处');expect(w.text()).toContain('预计时长');expect(w.text()).toContain('AI已审核');expect(w.get('.segment header .el-tag').classes()).toContain('el-tag--success')
 await w.get('[aria-label="逐字稿 1"]').setValue('修改后的完整讲稿')
 await w.get('[data-testid="save-outline"]').trigger('click');await flushPromises()
 const saved=calls.find(c=>c.init?.method==='PUT')
 expect(JSON.parse(String(saved?.init?.body)).segments[0].narration).toBe('修改后的完整讲稿')
 expect(alertDialog).toHaveBeenCalledWith('大纲已保存','保存成功',{confirmButtonText:'知道了',type:'success'})
 expect(w.text()).not.toContain('大纲已保存');w.unmount();alertDialog.mockRestore()
})

test('failed generation returns to requirement form for current configuration confirmation',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')?{id:'j1',kind:'generate',status:'failed',error_message:'失败'}:{project_id:'p1',revision:1,status:'failed',segments:[],job_id:'j1'}))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView},{path:'/projects/:id/edit',name:'project-edit',component:{template:'<div>需求</div>'}}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 const retry=w.findAll('button').find(b=>b.text()==='重新生成大纲')!
 await retry.trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('project-edit');w.unmount()
})

test('processing outline hides return action and shows live progress',async()=>{
 const outline={project_id:'p1',revision:1,status:'draft',segments:[],job_id:'j1',needs_regeneration:false}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')?{id:'j1',kind:'generate',status:'running',stage:'准备大纲',progress:5,error_message:null}:outline))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView},{path:'/projects/:id/edit',name:'project-edit',component:{template:'<div />'}}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(w.find('[data-testid="live-outline-progress"]').exists()).toBe(true)
 expect(w.find('[data-testid="return-requirement"]').exists()).toBe(false)
 w.unmount()
})

test('loading restores the task stage and elapsed time when the page reopens',async()=>{
 vi.useFakeTimers()
 vi.setSystemTime(new Date('2026-10-18T08:00:38Z'))
 const outline={project_id:'p1',revision:1,status:'outlining',segments:[],job_id:'j1',needs_regeneration:false}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')?{id:'j1',kind:'generate',status:'running',stage:'生成大纲',progress:45,created_at:'2026-10-18T08:00:00Z',error_message:null}:outline))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(w.get('[data-testid="outline-elapsed-time"]').text()).toBe('已等待 00:38')
 await vi.advanceTimersByTimeAsync(2000);await flushPromises()
 expect(w.get('[data-testid="outline-elapsed-time"]').text()).toBe('已等待 00:40')
 expect(w.text()).toContain('生成大纲')
 expect(w.text()).toContain('持续处理')
 expect(w.text()).not.toContain('%')
 w.unmount()
 const reopened=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(reopened.get('[data-testid="outline-elapsed-time"]').text()).toBe('已等待 00:40')
 reopened.unmount()
})

test('processing outline keeps the previous segments read-only',async()=>{
 const segment=(id:string,position:number)=>({id,position,title:`段落${position+1}`,objective:'理解概念',narration:'同学们好',visuals:[{kind:'文字卡',description:'概念标题'},{kind:'文字卡',description:'补充说明'}],evidence_ids:[],content_kind:'knowledge',review_notes:[],content_revision:1,reviewed_revision:1,review_passed:true,review_issues:[],estimated_duration_seconds:3})
 const outline={project_id:'p1',title:'二次函数',revision:2,status:'outlining',segments:[segment('s1',0),segment('s2',1)],job_id:'j1',needs_regeneration:false}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')?{id:'j1',kind:'generate',status:'running',stage:'准备大纲',progress:5,error_message:null}:outline))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 const remove=w.findAll('button').find(button=>button.text()==='删除段落')!
 const removeVisual=w.findAll('button').find(button=>button.text()==='移除')!
 expect(remove.attributes('disabled')).toBeDefined()
 expect(removeVisual.attributes('disabled')).toBeDefined()
 await remove.trigger('click')
 expect(w.findAll('.segment')).toHaveLength(2)
 w.unmount()
})

test('failed outline refreshes partial material warnings without requiring a page reload',async()=>{
 vi.useFakeTimers()
 let failed=false
 const warning={material_id:'m1',filename:'电路.docx',location:'文档插图 1',message:'图片未解析，请补传 PNG/JPEG/WebP'}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')
  ?{id:'j1',kind:'generate',status:failed?'failed':'running',stage:'生成大纲',progress:45,error_message:failed?'模型调用失败':null}
  :{project_id:'p1',title:'电路',revision:1,status:failed?'failed':'outlining',segments:[],job_id:'j1',needs_regeneration:false,material_warnings:failed?[warning]:[]}))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 failed=true
 await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(w.text()).toContain('模型调用失败')
 expect(w.text()).toContain('电路.docx')
 expect(w.text()).toContain('文档插图 1')
 expect(w.text()).toContain('图片未解析')
 w.unmount()
})


test('stage jumps update the label without changing an indeterminate loading bar',async()=>{
 vi.useFakeTimers()
 let progress=45
 const outline={project_id:'p1',title:'电路',revision:1,status:'outlining',segments:[],job_id:'j1',needs_regeneration:false}
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')
  ?{id:'j1',kind:'generate',status:'running',stage:progress===45?'生成大纲':'审核大纲',progress,error_message:null}
  :outline))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 try{
  expect(w.get('[role="progressbar"]').attributes('aria-valuenow')).toBeUndefined()
  expect(w.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('生成大纲')
  const band=w.get('[data-testid="outline-loading-band"]').element
  const style=w.get('[data-testid="outline-loading-band"]').attributes('style')
  expect(w.text()).not.toContain('%')
  progress=80
  await vi.advanceTimersByTimeAsync(1000);await flushPromises()
  expect(w.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('审核大纲')
  expect(w.get('[data-testid="outline-loading-band"]').element).toBe(band)
  expect(w.get('[data-testid="outline-loading-band"]').attributes('style')).toBe(style)
  progress=95
  await vi.advanceTimersByTimeAsync(1000);await flushPromises()
  expect(w.get('[role="progressbar"]').attributes('aria-valuenow')).toBeUndefined()
  expect(w.text()).not.toContain('%')
 }finally{w.unmount()}
})

test.each(['succeeded','failed'])('loading ends when the task becomes %s',async(status)=>{
 vi.useFakeTimers()
 let finished=false
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/jobs/')
  ?{id:'j1',kind:'generate',status:finished?status:'running',stage:'生成大纲',progress:finished?100:45,error_message:status==='failed'?'模型调用失败':null}
  :{project_id:'p1',title:'电路',revision:1,status:finished?'outline_ready':'outlining',segments:[],job_id:'j1',needs_regeneration:false}))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView},{path:'/projects/:id/edit',name:'project-edit',component:{template:'<div />'}}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 try{
  expect(w.find('[data-testid="live-outline-progress"]').exists()).toBe(true)
  finished=true
  await vi.advanceTimersByTimeAsync(1000);await flushPromises()
  expect(w.find('[data-testid="live-outline-progress"]').exists()).toBe(false)
  expect(w.find('[data-testid="return-requirement"]').exists()).toBe(true)
  if(status==='failed')expect(w.text()).toContain('模型调用失败')
 }finally{w.unmount()}
})

test('loading reports a lost connection and recovers automatically on the next poll',async()=>{
 vi.useFakeTimers()
 let offline=false
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.includes('/jobs/')&&offline)throw new TypeError('Failed to fetch')
  return new Response(JSON.stringify(url.includes('/jobs/')
   ?{id:'j1',kind:'generate',status:'running',stage:'生成大纲',progress:45,error_message:null}
   :{project_id:'p1',title:'电路',revision:1,status:'outlining',segments:[],job_id:'j1',needs_regeneration:false}))
 }))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 try{
  offline=true
  await vi.advanceTimersByTimeAsync(1000);await flushPromises()
  expect(w.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('重新连接')
  expect(w.text()).toContain('暂时无法获取任务状态')
  expect(w.text()).not.toContain('后台持续处理')
  offline=false
  await vi.advanceTimersByTimeAsync(1000);await flushPromises()
  expect(w.get('[role="progressbar"]').attributes('aria-valuetext')).toContain('生成大纲')
  expect(w.text()).toContain('后台持续处理')
  expect(w.text()).not.toContain('暂时无法获取任务状态')
 }finally{w.unmount()}
})


test('editing one reviewed segment marks only that segment pending and reverting restores its status',async()=>{
 const segment=(id:string,position:number)=>({id,position,title:`段落${position+1}`,objective:'理解概念',narration:'同学们好',visuals:[{kind:'文字卡',description:'概念标题'}],evidence_ids:[],content_kind:'knowledge',review_notes:[],content_revision:1,reviewed_revision:1,review_passed:true,review_issues:[],estimated_duration_seconds:3})
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({project_id:'p1',title:'电路',revision:1,status:'outline_ready',segments:[segment('s1',0),segment('s2',1)],job_id:null,needs_regeneration:false}))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/outline',name:'project-outline',component:OutlineView}]})
 await router.push('/projects/p1/outline')
 const w=mount(OutlineView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 try{
  const first=w.findAll('.segment')[0]!,second=w.findAll('.segment')[1]!
  expect(first.get('header .el-tag').text()).toBe('AI已审核')
  await w.get('[aria-label="逐字稿 1"]').setValue('修改后的完整讲稿')
  expect(first.get('header .el-tag').text()).toBe('待审核')
  expect(second.get('header .el-tag').text()).toBe('AI已审核')
  await w.get('[aria-label="逐字稿 1"]').setValue('同学们好')
  expect(first.get('header .el-tag').text()).toBe('AI已审核')
  await first.findAll('button').find(b=>b.text()==='下移')!.trigger('click')
  expect(w.findAll('.segment header .el-tag').map(t=>t.text())).toEqual(['AI已审核','AI已审核'])
 }finally{w.unmount()}
})
