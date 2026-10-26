import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory,RouterView} from 'vue-router'
import ElementPlus,{ElMessageBox} from 'element-plus'
import {restoreCreation,clearCreationMemory,rememberCreation} from '../src/utils/creation-memory'
import PptPreviewView from '../src/views/workbench/PptPreviewView.vue'
import CreatePptView from '../src/views/workbench/CreatePptView.vue'
import PptOutlineView from '../src/views/workbench/PptOutlineView.vue'
import CreateVideoView from '../src/views/workbench/CreateVideoView.vue'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();clearCreationMemory();ElMessageBox.close()})
const slides=[{id:'1',layout:'concept',title:'光合作用',content:'植物制造养分',slots:{}},{id:'2',layout:'summary',title:'回顾',content:'能量的来源',slots:{}}]
const project={id:'p1',revision:3,title:'植物',prompt:'讲解植物',style:'auto',web_search:false,status:'outline_ready',confirmed_revision:null,rendered_revision:null,updated_at:'2026-10-23T10:00:00Z',outline:{slides,review:{status:'passed',version:'ppt-knowledge-1',issues:[],changes:[],repairs:0}},pages:[],warnings:[],job:null}
function fakeFetch(){return vi.fn(async(url:string,init?:RequestInit)=>{
  if(url==='/api/account/credits')return new Response(JSON.stringify({available:100,video_cost:10,ppt_cost:10}))
  if(url.includes('/config/form'))return new Response(JSON.stringify({system_available:true,fields:[{key:'prompt',label:'想讲什么',default:'',options:[],default_by_subject:{}}]}))
  if(url.endsWith('/config'))return new Response(JSON.stringify({system_available:true,review_available:true,search_available:true,search_visible:true,search_default:false,templates:[{id:'clear-blue-teaching',name:'简洁教学 · 清蓝',version:'1.0.0'}],layouts:{concept:'概念与公式',summary:'回顾与延伸'}}))
  if(url.endsWith('/materials'))return new Response('[]')
  if(url.includes('/jobs/'))return new Response(JSON.stringify({id:'j1',status:'pending',progress:0,kind:'rewrite',stage:'等待处理'}))
  return new Response(JSON.stringify(init?.method==='PUT'?{...project,revision:4}:project))
})}
async function setup(path:string,_view:any){const router=createRouter({history:createMemoryHistory(),routes:[{path:'/presentations/new',name:'ppt-create',component:CreatePptView},{path:'/projects/new',component:CreateVideoView},{path:'/presentations/:id/edit',name:'ppt-edit',component:CreatePptView},{path:'/presentations/:id/outline',name:'ppt-outline',component:PptOutlineView},{path:'/presentations/:id/preview',name:'ppt-preview',component:PptPreviewView}]});await router.push(path);const w=mount(RouterView,{global:{plugins:[router,ElementPlus]}});await flushPromises();return {w,router}}

test('PPT creation preserves composer order and only exposes style as setting',async()=>{
  vi.stubGlobal('fetch',fakeFetch());const {w}=await setup('/presentations/new',CreatePptView)
  expect(w.get('.creation-welcome').text()).toBe('今天讲点啥？')
  expect(w.get('.creation-mode').text()).toContain('生成视频')
  expect(w.get('.creation-settings').text()).toContain('课件风格')
  expect(w.get('.creation-settings').findAll('.el-select')).toHaveLength(1)
  expect(w.get('.creation-settings').text()).not.toContain('页面比例')
  expect(w.text()).toContain('生成 PPT 大纲')
  w.unmount()
})

test('switching between PPT and video restores each unsaved creation form',async()=>{
  vi.stubGlobal('fetch',fakeFetch());const {w}=await setup('/presentations/new',CreatePptView)
  await w.get('[data-testid=project-title]').setValue('未保存的植物课')
  await w.get('textarea').setValue('从叶片开始讲')
  await w.get('[data-mode=video]').trigger('click');await flushPromises()
  await w.get('[data-testid=project-title]').setValue('视频内容')
  await w.get('[data-mode=ppt]').trigger('click');await flushPromises()
  expect((w.get('[data-testid=project-title]').element as HTMLInputElement).value).toBe('未保存的植物课')
  expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('从叶片开始讲');w.unmount()
})

test('outline edits require save and rewrite submits only checked page IDs',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',fetcher);const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  await w.get('[aria-label="选择第 1 页"]').setValue(true)
  await w.get('[aria-label="修改要求"]').setValue('增加生活实例')
  await w.get('[data-testid=rewrite-pages]').trigger('click');await flushPromises()
  const call=fetcher.mock.calls.find(([url])=>url.endsWith('/jobs/rewrite'))
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({revision:3,slide_ids:['1'],instruction:'增加生活实例'})
  w.unmount()
})

test('saved new PPT retains project identity and uploaded references after switching',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',fetcher);const {w}=await setup('/presentations/new',CreatePptView)
  await w.get('[data-testid=project-title]').setValue('植物');await w.get('textarea').setValue('讲解植物')
  await w.get('[data-testid=save-draft]').trigger('click');await flushPromises()
  await w.get('[data-mode=video]').trigger('click');await flushPromises()
  await w.get('[data-mode=ppt]').trigger('click');await flushPromises()
  await w.get('[data-testid=save-draft]').trigger('click');await flushPromises()
  expect(fetcher.mock.calls.filter(([url,init])=>url==='/api/presentations'&&init?.method==='POST')).toHaveLength(1)
  expect(fetcher.mock.calls.some(([url])=>url==='/api/presentations/p1/materials')).toBe(true)
  w.unmount()
})

test('opening an already rendered outline does not bounce back to preview',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify({...project,job:{id:'old',kind:'render',status:'succeeded',progress:100},pages:slides})):fetcher(url,init))
  const {w,router}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(router.currentRoute.value.path).toBe('/presentations/p1/outline');w.unmount()
})

test('cleared session cannot be repopulated by an unmounting creation view',async()=>{
  vi.stubGlobal('fetch',fakeFetch());const {w}=await setup('/presentations/new',CreatePptView)
  await w.get('[data-testid=project-title]').setValue('上个账号的私密课件')
  clearCreationMemory();w.unmount()
  expect(restoreCreation('ppt','/presentations/new')).toBeUndefined()
})


test('preview displays unresolved visual review issues and actionable repairs',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify({...project,status:'ready',pages:[{...slides[0],review:{status:'needs_attention',repairs:2,issues:[{category:'teaching',message:'遮光区颜色有误',repair:'遮光区改为浅色'}]}}]})):fetcher(url,init))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.get('[data-testid=page-review]').text()).toContain('仍需检查')
  expect(w.text()).toContain('遮光区颜色有误')
  expect(w.text()).toContain('遮光区改为浅色')
  w.unmount()
})

test('completed preview navigates reviewed and legacy pages without audit labels',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'ready',pages:[{...slides[0],review:{status:'passed',repairs:1,issues:[]}},slides[1]]})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.find('[data-testid=page-review]').exists()).toBe(false)
  await w.get('[aria-label="预览第 2 页：回顾"]').trigger('click')
  expect(w.find('[data-testid=page-review]').exists()).toBe(false)
  expect(w.find('[data-testid=page-status-list] .el-tag').exists()).toBe(false)
  w.unmount()
})

const issue={category:'teaching',message:'遮光区颜色有误',repair:'遮光区改为浅色'}
const passed={status:'passed',repairs:1,issues:[]}
const renderJob={id:'render-1',project_id:'p1',kind:'render',status:'running',stage:'逐页审核教学图意与排版：光合作用',progress:90,error_message:null}
function button(w:ReturnType<typeof mount>,label:string){return w.findAll('button').find(b=>b.text()===label)!}

test('input to outline approval to preview keeps generation and review in the third step',async()=>{
  vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
  vi.useFakeTimers({toFake:['setTimeout','clearTimeout']})
  let saved:any={...project,revision:1,status:'draft',outline:null}
  let failPreviewLoadOnce=false
  const fallback=fakeFetch()
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined
    if(url==='/api/presentations'&&init?.method==='POST')return new Response(JSON.stringify(saved))
    if(url.endsWith('/jobs/outline')){saved={...saved,status:'generating',job:{...renderJob,id:'outline-1',kind:'outline',stage:'生成大纲'}};return new Response(JSON.stringify(saved.job))}
    if(url==='/api/presentations/p1/outline'&&init?.method==='PUT'){saved={...saved,revision:3,outline:{slides:body.slides}};return new Response(JSON.stringify(saved))}
    if(url.endsWith('/jobs/check')){saved={...saved,revision:saved.revision+1,outline:{...saved.outline,review:{status:'passed',version:'ppt-knowledge-1',issues:[],changes:[],repairs:0}}};return new Response(JSON.stringify({id:'check',kind:'check',status:'succeeded',progress:100}))}
    if(url.endsWith('/confirm')){saved={...saved,status:'outline_confirmed',confirmed_revision:saved.revision};return new Response(JSON.stringify(saved))}
    if(url.endsWith('/jobs/render')){failPreviewLoadOnce=true;saved={...saved,status:'generating',job:renderJob};return new Response(JSON.stringify(renderJob))}
    if(url==='/api/presentations/p1'&&failPreviewLoadOnce){failPreviewLoadOnce=false;return new Response(JSON.stringify({detail:{code:'unavailable',message:'服务器暂时不可用'}}),{status:503})}
    if(url==='/api/presentations/p1')return new Response(JSON.stringify(saved))
    return fallback(url,init)
  })
  vi.stubGlobal('fetch',fetcher)
  const {w,router}=await setup('/presentations/new',CreatePptView)
  await w.get('[data-testid=project-title]').setValue('植物')
  await w.get('textarea').setValue('讲解植物')
  await button(w,'生成 PPT 大纲').trigger('click');await flushPromises()
  expect(router.currentRoute.value.path).toBe('/presentations/p1/outline')
  saved={...project,revision:2,job:{...saved.job,status:'succeeded',progress:100}}
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  await w.get('[aria-label="第 1 页标题"]').setValue('光合作用的条件')
  await button(w,'重新审查').trigger('click');await flushPromises()
  await button(w,'确认大纲').trigger('click');await flushPromises()
  expect(router.currentRoute.value.path).toBe('/presentations/p1/preview')
  expect(w.text()).toContain('大纲已确认，课件尚未生成')
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/jobs/render'))).toBe(false)
  await button(w,'开始生成 PPT').trigger('click');await flushPromises()
  expect(w.text()).toContain('服务器暂时不可用')
  await button(w,'重新加载').trigger('click');await flushPromises()
  expect(w.get('[aria-label="PPT 制作流程"]').findAll('li')).toHaveLength(3)
  expect(w.get('[aria-current="step"]').text()).toContain('PPT 预览')
  expect(w.get('[data-testid=review-progress]').text()).toContain('逐页审核教学图意与排版')
  expect(w.get('[data-testid=page-status-list]').text()).toContain('等待生成与审核')
  expect(w.find('a.ppt-download').exists()).toBe(false)
  expect(w.find('img').exists()).toBe(false)
  const outlineSave=fetcher.mock.calls.find(([url,init])=>url.endsWith('/outline')&&init?.method==='PUT')
  expect(JSON.parse(String(outlineSave?.[1]?.body))).toMatchObject({revision:2,slides:[{...slides[0],title:'光合作用的条件'},slides[1]]})
  expect(JSON.parse(String(fetcher.mock.calls.find(([url])=>url.endsWith('/jobs/render'))?.[1]?.body)).revision).toBe(4)
  saved={...saved,status:'ready',rendered_revision:4,pages:saved.outline.slides.map((s:any)=>({...s,review:passed})),job:{...renderJob,status:'succeeded',progress:100}}
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
  expect(w.find('[data-testid=page-review]').exists()).toBe(false)
  expect(w.get('a.ppt-download').attributes('href')).toBe('/api/presentations/p1/export')
  w.unmount()
})

test('resuming an active render from the outline opens preview with progress',async()=>{
  const fetcher=fakeFetch()
  vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify({...project,status:'generating',job:renderJob})):fetcher(url,init))
  const {w,router}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(router.currentRoute.value.path).toBe('/presentations/p1/preview')
  expect(w.get('[data-testid=review-progress]').text()).toContain('逐页审核')
  w.unmount()
})

test('preview shows all page verdicts and uses a suggestion only for its page',async()=>{
  let saved:any={...project,status:'ready',rendered_revision:3,pages:[{...slides[0],review:passed},{...slides[1],review:{status:'needs_attention',repairs:2,issues:[issue]}}],warnings:[{slide_id:'2',page:2,message:'第 2 页仍需检查：遮光区颜色有误'},{filename:'参考.pdf',location:'第 3 页',message:'图片未提取'}]}
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/jobs/revise')){saved={...saved,status:'generating',job:{...renderJob,kind:'revise'}};return new Response(JSON.stringify(saved.job))}
    return new Response(JSON.stringify(saved))
  })
  vi.stubGlobal('fetch',fetcher)
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
  expect(w.get('[data-testid=page-status-list]').text()).toContain('第 2 页')
  expect(w.find('[aria-label="生成提醒"]').exists()).toBe(false)
  expect(w.text()).not.toContain('参考.pdf')
  expect(w.text()).not.toContain('第 2 页仍需检查：遮光区颜色有误')
  await w.get('[aria-label="预览第 2 页：回顾"]').trigger('click')
  expect(w.get('[data-testid=page-review]').text()).toContain('已自动修复 2 次')
  expect(w.get('[data-testid=page-review]').text()).toContain('教学一致性')
  await button(w,'采用本页修改建议').trigger('click')
  expect((w.get('[aria-label="选择第 1 页"]').element as HTMLInputElement).checked).toBe(false)
  expect((w.get('[aria-label="选择第 2 页"]').element as HTMLInputElement).checked).toBe(true)
  expect((w.get('[aria-label="修改要求"]').element as HTMLTextAreaElement).value).toContain('遮光区改为浅色')
  await button(w,'修改所选课件页面').trigger('click');await flushPromises()
  expect(JSON.parse(String(fetcher.mock.calls.find(([url])=>url.endsWith('/jobs/revise'))?.[1]?.body))).toMatchObject({revision:3,slide_ids:['2'],instruction:expect.stringContaining('遮光区改为浅色')})
  expect(w.text()).toContain('上一版')
  expect(button(w,'采用本页修改建议').attributes('disabled')).toBeDefined()
  w.unmount()
})

test('failed initial render stays in preview and can retry the same confirmed outline',async()=>{
  let saved:any={...project,status:'outline_ready',confirmed_revision:3,job:{...renderJob,status:'failed',error_message:'视觉审核服务暂时不可用，请重试'}}
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/jobs/render')){saved={...saved,status:'generating',job:renderJob};return new Response(JSON.stringify(renderJob))}
    return new Response(JSON.stringify(saved))
  })
  vi.stubGlobal('fetch',fetcher)
  const {w,router}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.text()).toContain('视觉审核服务暂时不可用，请重试')
  await button(w,'重新生成并审核').trigger('click');await flushPromises()
  expect(router.currentRoute.value.path).toBe('/presentations/p1/preview')
  expect(w.get('[data-testid=review-progress]').text()).toContain('逐页审核')
  expect(JSON.parse(String(fetcher.mock.calls.find(([url])=>url.endsWith('/jobs/render'))?.[1]?.body)).revision).toBe(3)
  w.unmount()
})

test('missing review configuration keeps outline editing and confirmation available',async()=>{
  const fetcher=fakeFetch()
  vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>{const response=await fetcher(url,init);return url.endsWith('/config')?new Response(JSON.stringify({...await response.json(),review_available:false})):response})
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(w.text()).toContain('仍可制作课件')
  expect(button(w,'确认大纲').attributes('disabled')).toBeUndefined()
  expect(w.get('[aria-label="第 1 页标题"]').attributes('disabled')).toBeUndefined()
  w.unmount()
})

test('pending review metadata is never counted as passed or legacy',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'ready',rendered_revision:3,pages:[{...slides[0],review:{status:'pending',repairs:1,issues:[issue]}}]})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.get('[data-testid=page-review]').text()).toContain('等待内容与可用性检查')
  expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
  expect(w.get('[data-testid=page-review]').text()).not.toContain('审核通过')
  expect(w.get('[data-testid=page-review]').text()).not.toContain('尚无审核记录')
  w.unmount()
})

test('preview load failure offers recovery without leaving the third step',async()=>{
  let unavailable=true
  vi.stubGlobal('fetch',async()=>unavailable?new Response(JSON.stringify({detail:{code:'unavailable',message:'服务器暂时不可用'}}),{status:503}):new Response(JSON.stringify({...project,status:'generating',job:renderJob})))
  const {w,router}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.text()).toContain('服务器暂时不可用')
  expect(w.find('.el-empty').exists()).toBe(false)
  unavailable=false
  await button(w,'重新加载').trigger('click');await flushPromises()
  expect(router.currentRoute.value.path).toBe('/presentations/p1/preview')
  expect(w.get('[data-testid=review-progress]').text()).toContain('逐页审核')
  w.unmount()
})

test('multiple review suggestions remain separate editable instructions',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'ready',rendered_revision:3,pages:[{...slides[0],review:{status:'needs_attention',repairs:2,issues:[issue,{category:'readability',message:'注释字号过小',repair:'增大注释字号'}]}}]})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  await button(w,'采用本页修改建议').trigger('click')
  expect((w.get('[aria-label="修改要求"]').element as HTMLTextAreaElement).value).toBe('遮光区颜色有误：遮光区改为浅色\n注释字号过小：增大注释字号')
  w.unmount()
})

test('page controls expose review verdicts and prior-version context to screen readers',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'generating',rendered_revision:3,pages:[{...slides[0],review:{status:'needs_attention',repairs:2,issues:[issue]}}],job:{...renderJob,kind:'revise'}})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  const control=w.get('[aria-label="预览第 1 页：光合作用"]')
  const description=w.get('#'+control.attributes('aria-describedby'))
  expect(description.text()).toContain('仍需检查')
  expect(description.text()).toContain('上一版')
  w.unmount()
})


test('unapproved stored pages expose status and recovery but no images or download',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'ready',rendered_revision:3,pages:[{...slides[0],review:{status:'needs_attention',repairs:2,issues:[issue]}}]})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.findAll('img')).toHaveLength(0)
  expect(w.find('a.ppt-download').exists()).toBe(false)
  expect(w.text()).toContain('审核通过后开放预览')
  expect(w.text()).toContain('遮光区颜色有误')
  w.unmount()
})


test('partial delivery previews only approved pages and offers automatic completion without instructions',async()=>{
  const fetcher=fakeFetch();let request:any=null
  vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/jobs/render')){request=JSON.parse(String(init?.body));return new Response(JSON.stringify({...renderJob,status:'pending'}))}
    if(url==='/api/presentations/p1')return new Response(JSON.stringify({...project,status:'partial_ready',confirmed_revision:3,rendered_revision:3,pages:[{...slides[0],review:passed},{...slides[1],review:{status:'needs_attention',repairs:2,issues:[issue]}}]}))
    return fetcher(url,init)
  })
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.get('a.ppt-download').attributes('href')).toContain('partial=true')
  expect(w.get('a.ppt-download').text()).toContain('已通过部分')
  expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
  expect(w.get('[data-testid=partial-recovery]').text()).toContain('1 / 2')
  expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
  const buttons=w.findAll('button');await buttons.find(b=>b.text().includes('自动补齐'))!.trigger('click');await flushPromises()
  expect(request).toMatchObject({revision:3})
})


test.each(['generating','failed'])('partial pages remain usable when latest job is %s',async(status)=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status,rendered_revision:3,pages:[{...slides[0],review:passed},{...slides[1],review:{status:'needs_attention',repairs:2,issues:[issue]}}],job:{...renderJob,status:status==='generating'?'running':'failed'}})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
  if(status==='failed')expect(w.get('a.ppt-download').attributes('href')).toContain('partial=true')
  expect(w.text()).toContain('1 / 2')
})


test('outline requires knowledge checking before confirmation and shows formula corrections',async()=>{
  let saved:any={...project,outline:{slides}}
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/jobs/check'))return new Response(JSON.stringify({id:'check1',kind:'check',status:'pending',progress:0,stage:'核查知识点和公式'}))
    if(url==='/api/presentations/p1')return new Response(JSON.stringify(saved))
    return fakeFetch()(url,init)
  })
  vi.stubGlobal('fetch',fetcher)
  const {w,router}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
  await button(w,'核查知识点和公式').trigger('click');await flushPromises()
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/jobs/check'))).toBe(true)
  expect(router.currentRoute.value.path).toBe('/presentations/p1/outline')
  w.unmount()
})

test('checked outline displays corrections and local edits require another check',async()=>{
  const checked={...project,outline:{slides,review:{version:'ppt-knowledge-1',status:'passed',issues:[],repairs:1,changes:[{slide_id:'1',message:'公式符号错误',before:'x=b/(2a)',after:'x=-b/(2a)'}]}}}
  const fallback=fakeFetch();vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify(checked)):fallback(url,init))
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(w.get('[data-testid=knowledge-review]').text()).toContain('x=-b/(2a)')
  expect(button(w,'确认大纲').attributes('disabled')).toBeUndefined()
  await w.get('[aria-label="第 1 页内容"]').setValue('编辑后需再检查')
  expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
  w.unmount()
})

test('completed deck keeps preview and download without surfacing internal visual suggestions',async()=>{
  const page={...slides[0],review:{status:'passed',repairs:0,issues:[{category:'visual',severity:'suggestion',message:'留白可增加','repair':'增加段间距'}]}}
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'ready',rendered_revision:3,pages:[page]})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.get('a.ppt-download').attributes('href')).toBe('/api/presentations/p1/export')
  expect(w.get('.ppt-slide-preview img').exists()).toBe(true)
  expect(w.find('[data-testid=page-review]').exists()).toBe(false)
  expect(w.text()).not.toContain('留白可增加')
  expect(w.find('[data-testid=page-status-list] .el-tag').exists()).toBe(false)
  w.unmount()
})


test('passed outline locks review until actual outline content changes',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',fetcher)
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  const review=()=>w.get('[data-testid=review-outline]')
  expect(review().text()).toBe('已审查')
  expect(review().attributes('disabled')).toBeDefined()
  await review().trigger('click');await flushPromises()
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/jobs/check'))).toBe(false)
  await w.get('[aria-label="选择第 1 页"]').setValue(true)
  await w.get('[aria-label="修改要求"]').setValue('尚未提交的修改要求')
  expect(review().attributes('disabled')).toBeDefined()
  await w.get('[aria-label="第 1 页内容"]').setValue('修改后的知识点')
  expect(review().text()).toBe('重新审查')
  expect(review().attributes('disabled')).toBeUndefined()
  expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
  await w.get('[aria-label="第 1 页内容"]').setValue('植物制造养分')
  expect(review().text()).toBe('已审查')
  expect(review().attributes('disabled')).toBeDefined()
  expect(button(w,'确认大纲').attributes('disabled')).toBeUndefined()
})

test('saving an edited outline keeps generation locked until recheck succeeds',async()=>{
  let saved:any=JSON.parse(JSON.stringify(project))
  const fallback=fakeFetch(),requests:string[]=[]
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url==='/api/presentations/p1/outline'&&init?.method==='PUT'){
      requests.push('save')
      saved={...saved,revision:4,outline:{slides:JSON.parse(String(init.body)).slides}}
      return new Response(JSON.stringify(saved))
    }
    if(url.endsWith('/jobs/check')){
      requests.push('check')
      saved={...saved,revision:5,outline:{...saved.outline,review:project.outline.review}}
      return new Response(JSON.stringify({id:'check',kind:'check',status:'succeeded',progress:100}))
    }
    if(url==='/api/presentations/p1')return new Response(JSON.stringify(saved))
    return fallback(url,init)
  })
  vi.stubGlobal('fetch',fetcher)
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  await w.get('[aria-label="第 1 页标题"]').setValue('修订标题')
  await button(w,'保存大纲').trigger('click');await flushPromises()
  expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
  expect(w.get('[data-testid=review-outline]').attributes('disabled')).toBeUndefined()
  expect(w.get('[data-testid=review-outline]').text()).toBe('重新审查')
  await button(w,'确认大纲').trigger('click');await flushPromises()
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/jobs/render'))).toBe(false)
  await w.get('[data-testid=review-outline]').trigger('click');await flushPromises()
  expect(requests).toEqual(['save','check'])
  expect(w.get('[data-testid=review-outline]').text()).toBe('已审查')
  expect(w.get('[data-testid=review-outline]').attributes('disabled')).toBeDefined()
  expect(button(w,'确认大纲').attributes('disabled')).toBeUndefined()
})

test.each(['unchecked','needs_attention'])('%s outline cannot generate a PPT',async(status)=>{
  const fallback=fakeFetch()
  const outline=status==='unchecked'?{slides}:{slides,review:{...project.outline.review,status,issues:[{slide_id:'1',message:'知识点有误',repair:'纠正知识点'}]}}
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify({...project,outline})):fallback(url,init))
  vi.stubGlobal('fetch',fetcher)
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  expect(w.get('[data-testid=review-outline]').attributes('disabled')).toBeUndefined()
  expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
  await button(w,'确认大纲').trigger('click');await flushPromises()
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/jobs/render'))).toBe(false)
})


test.each([
  {visible:false,defaultValue:false,available:true,stored:true,want:false},
  {visible:false,defaultValue:true,available:true,stored:false,want:true},
  {visible:true,defaultValue:true,available:true,stored:undefined,want:true},
  {visible:true,defaultValue:true,available:false,stored:true,want:false},
])('PPT search respects admin visibility and default $visible/$defaultValue/$available',async({visible,defaultValue,available,stored,want})=>{
  const fallback=fakeFetch();let submitted:any
  const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
    if(url==='/api/presentations/config')return new Response(JSON.stringify({system_available:true,search_available:available,search_visible:visible&&available,search_default:defaultValue&&available,templates:[],layouts:{}}))
    if(url==='/api/presentations'&&init?.method==='POST'){submitted=JSON.parse(String(init.body));return new Response(JSON.stringify({...project,...submitted}))}
    return fallback(url,init)
  })
  vi.stubGlobal('fetch',fetcher)
  if(stored!==undefined)rememberCreation('ppt','/presentations/new',{title:'旧草稿',prompt:'教学内容',style:'auto',webSearch:stored,files:[]})
  const {w}=await setup('/presentations/new',CreatePptView)
  expect(w.find('[aria-label="联网搜索"]').exists()).toBe(visible&&available)
  if(visible&&available)expect(w.get('[aria-label="联网搜索"]').attributes('aria-checked')).toBe(String(want))
  await w.get('[data-testid=project-title]').setValue('联网设置测试')
  await w.get('textarea').setValue('教学内容')
  await w.get('[data-testid=save-draft]').trigger('click');await flushPromises()
  expect(submitted.web_search).toBe(want)
})

test.each([['outline','pending'],['rewrite','running']])('PPT %s uses the video loading animation for %s jobs',async(kind,status)=>{
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-24T08:00:38Z'))
  const fallback=fakeFetch()
  const job={...renderJob,kind,status,stage:'正在整理课件大纲',created_at:'2026-10-24T08:00:00Z'}
  vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/presentations/p1'?new Response(JSON.stringify({...project,status:'generating',job})):fallback(url,init))
  const {w}=await setup('/presentations/p1/outline',PptOutlineView)
  const progress=w.get('[data-testid=live-outline-progress]')
  expect(progress.attributes('aria-label')).toBe('PPT 大纲生成进度')
  expect(progress.text()).toContain('正在整理课件大纲')
  expect(progress.get('[data-testid=outline-elapsed-time]').text()).toBe('已等待 00:38')
  expect(progress.find('[data-testid=outline-loading-band]').exists()).toBe(true)
  expect(w.find('.el-progress').exists()).toBe(false)
  expect(w.get('[aria-label="第 1 页标题"]').attributes('disabled')).toBeDefined()
})

test.each(['render','revise'])('PPT %s keeps the shared loading animation through polling and hides it on completion',async kind=>{
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-24T08:00:38Z'))
  let job={...renderJob,kind,created_at:'2026-10-24T08:00:00Z'}
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'generating',job})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  const progress=w.get('[data-testid=live-outline-progress]')
  expect(progress.attributes('aria-label')).toBe('PPT 生成与审核进度')
  expect(w.get('[data-testid=review-progress]').text()).toContain('逐页审核')
  expect(progress.get('[data-testid=outline-elapsed-time]').text()).toBe('已等待 00:38')
  expect(w.find('.el-progress').exists()).toBe(false)
  const band=progress.get('[data-testid=outline-loading-band]').element
  job={...job,stage:'正在修复页面排版'}
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(w.get('[data-testid=outline-loading-band]').element).toBe(band)
  expect(w.get('[data-testid=outline-elapsed-time]').text()).toBe('已等待 00:40')
  expect(w.get('[data-testid=live-outline-progress]').text()).toContain('正在修复页面排版')
  job={...job,status:'succeeded',progress:100}
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(w.find('[data-testid=live-outline-progress]').exists()).toBe(false)
})

test('PPT loading pauses on a polling error and resumes after recovery',async()=>{
  vi.useFakeTimers()
  let offline=false
  vi.stubGlobal('fetch',async()=>{
    if(offline)throw new Error('网络连接暂时中断')
    return new Response(JSON.stringify({...project,status:'generating',job:renderJob}))
  })
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  offline=true
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  const progress=w.get('[data-testid=live-outline-progress]')
  expect(progress.classes()).toContain('connection-lost')
  expect(progress.text()).toContain('正在重新连接')
  expect(progress.text()).toContain('请勿重复提交')
  offline=false
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(w.get('[data-testid=live-outline-progress]').classes()).not.toContain('connection-lost')
  expect(w.get('[data-testid=live-outline-progress]').text()).toContain(renderJob.stage)
})


test('preview uses the resolved template name from the viewed version',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,style:'academic-formal',template_id:'academic-formal',template_name:'学术正式 · 墨红',status:'ready',pages:slides})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.get('.ppt-heading').text()).toContain('学术正式 · 墨红')
  expect(w.get('.ppt-heading').text()).not.toContain('简洁教学 · 清蓝')
  w.unmount()
})

test('approved style selection is submitted when saving a new PPT',async()=>{
  const fetcher=fakeFetch();vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>{
    if(url==='/api/presentations/config')return new Response(JSON.stringify({system_available:true,search_available:false,templates:[{id:'clear-blue-teaching',name:'简洁教学 · 清蓝',version:'1.0.0'},{id:'lively-illustration',name:'活泼插画 · 橙光',version:'1.0.0'},{id:'academic-formal',name:'学术正式 · 墨红',version:'1.0.0'}],layouts:{}}))
    return fetcher(url,init)
  })
  const {w}=await setup('/presentations/new',CreatePptView)
  await w.get('[data-testid=project-title]').setValue('新课件');await w.get('textarea').setValue('讲授二次函数')
  await w.getComponent({name:'ElSelect'}).vm.$emit('update:modelValue','lively-illustration')
  await w.get('[data-testid=save-draft]').trigger('click');await flushPromises()
  const call=fetcher.mock.calls.find(([url,init])=>url==='/api/presentations'&&init?.method==='POST')
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({style:'lively-illustration'})
  w.unmount()
})

test('active generation shows progress and contents without review totals',async()=>{
  vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({...project,status:'generating',confirmed_revision:3,pages:[],job:renderJob})))
  const {w}=await setup('/presentations/p1/preview',PptPreviewView)
  expect(w.find('[data-testid=review-progress]').exists()).toBe(true)
  expect(w.get('[data-testid=page-status-list]').text()).toContain('光合作用')
  expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
  expect(w.text()).not.toMatch(/页通过|页仍需检查|页等待审核/)
  w.unmount()
})
