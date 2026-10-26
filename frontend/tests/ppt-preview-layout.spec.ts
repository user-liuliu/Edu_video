import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory,RouterView} from 'vue-router'
import ElementPlus from 'element-plus'
import PptPreviewView from '../src/views/workbench/PptPreviewView.vue'
enableAutoUnmount(afterEach)
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})
const slides=[{id:'s1',layout:'concept',title:'认识光合作用',content:'从一片叶子，认识植物制造有机物的过程。',slots:{}},{id:'s2',layout:'concept',title:'原料与产物',content:'二氧化碳和水转化为有机物，并释放氧气。',slots:{}}]
const passed={status:'passed',repairs:0,issues:[]}
async function setup(extra:Record<string,unknown>={},snapshots:Record<string,unknown>={}){
 const saved={id:'p1',revision:3,confirmed_revision:3,rendered_revision:3,title:'光合作用',style:'auto',status:'ready',outline:{slides},pages:slides.map(s=>({...s,review:passed})),warnings:[],job:null,...extra}
 const requests:{url:string;body:any}[]=[]
 vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>{if(url==='/api/account/credits')return new Response(JSON.stringify({balance:100,reserved:0,available:100,video_cost:10,ppt_cost:10}));if(init?.method==='POST'){requests.push({url,body:JSON.parse(String(init.body))});return new Response(JSON.stringify({id:'j1',kind:'revise',status:'pending',stage:'等待处理',progress:0}))}return new Response(JSON.stringify(snapshots[url]??saved))})
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/presentations/:id/preview',component:PptPreviewView},{path:'/presentations/:id/outline',name:'ppt-outline',component:{template:'<div>大纲</div>'}}]})
 await router.push('/presentations/p1/preview');const w=mount(RouterView,{attachTo:document.body,global:{plugins:[router,ElementPlus]}});await flushPromises();return {w,requests}
}
function button(w:ReturnType<typeof mount>,label:string){return w.findAll('button').find(b=>b.text()===label)!}
test('preview places player before directory with local actions and collapsed editing',async()=>{
 const {w,requests}=await setup()
 expect(w.get('h1').text()).toBe('PPT 预览')
 const layout=w.get('.ppt-preview-layout')
 expect(layout.element.firstElementChild?.classList.contains('ppt-player-column')).toBe(true)
 const contents=layout.get('[data-testid=page-status-list]')
 expect(contents.text()).toContain('课件内容')
 expect(contents.text()).toContain(slides[1].content)
 expect(contents.findAll('img')).toHaveLength(0)
 expect(w.get('.ppt-player-column .ppt-download').text()).toBe('满意，下载 PPTX')
 expect(w.get('.ppt-heading').find('.ppt-download').exists()).toBe(false)
 expect(w.find('[aria-label="修改课件页面"]').exists()).toBe(false)
 expect(contents.findAll('input[type=checkbox]')).toHaveLength(0)
 expect(w.find('[data-testid=page-review]').exists()).toBe(false)
 expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
 expect(contents.findAll('.el-tag')).toHaveLength(0)
 expect(contents.get('button').attributes('aria-describedby')).toBeUndefined()
 expect(w.text()).not.toContain('系统会先质检')
 expect(requests).toHaveLength(0)
})
test('editing displayed page preselects it and submits only selected IDs',async()=>{
 const {w,requests}=await setup()
 await w.get('[aria-label="预览第 2 页：原料与产物"]').trigger('click')
 expect(w.get('.ppt-slide-preview > img').attributes('alt')).toBe('第 2 页：原料与产物')
 await button(w,'修改这一页').trigger('click');await flushPromises()
 const panel=w.get('[aria-label="修改课件页面"]')
 expect((panel.get('[aria-label="选择第 1 页"]').element as HTMLInputElement).checked).toBe(false)
 expect((panel.get('[aria-label="选择第 2 页"]').element as HTMLInputElement).checked).toBe(true)
 expect(button(w,'修改所选课件页面').attributes('disabled')).toBeDefined()
 await panel.get('[aria-label="选择第 1 页"]').setValue(true)
 await panel.get('[aria-label="修改要求"]').setValue('增加箭头说明')
 await button(w,'修改所选课件页面').trigger('click');await flushPromises()
 expect(requests).toEqual([{url:'/api/presentations/p1/jobs/revise',body:expect.objectContaining({revision:3,slide_ids:['s2','s1'],instruction:'增加箭头说明'})}])
})
test('cancel makes no request and reopening selects newly displayed page',async()=>{
 const {w,requests}=await setup()
 await button(w,'修改这一页').trigger('click');await flushPromises()
 await w.get('[aria-label="修改要求"]').setValue('暂不提交')
 await button(w,'取消').trigger('click')
 expect(w.find('[aria-label="修改课件页面"]').exists()).toBe(false)
 await button(w,'下一页').trigger('click')
 await button(w,'修改这一页').trigger('click');await flushPromises()
 expect((w.get('[aria-label="选择第 2 页"]').element as HTMLInputElement).checked).toBe(true)
 expect((w.get('[aria-label="修改要求"]').element as HTMLTextAreaElement).value).toBe('')
 expect(requests).toHaveLength(0)
})
test('review suggestions expand details and open editing for exact page',async()=>{
 const issue={category:'readability',message:'文字过小',repair:'增大字号'}
 const {w}=await setup({pages:[{...slides[0],review:{...passed,status:'needs_attention',issues:[issue]}}]})
 expect((w.get('details[data-testid=page-review]').element as HTMLDetailsElement).open).toBe(true)
 expect(w.findAll('img')).toHaveLength(0)
 expect(w.find('a.ppt-download').exists()).toBe(false)
 await button(w,'采用本页修改建议').trigger('click');await flushPromises()
 expect(w.get('[aria-label="修改课件页面"]').exists()).toBe(true)
 expect((w.get('[aria-label="选择第 1 页"]').element as HTMLInputElement).checked).toBe(true)
 expect((w.get('[aria-label="修改要求"]').element as HTMLTextAreaElement).value).toBe('文字过小：增大字号')
})
test('pending preview keeps one explicit start above player and never renders on load',async()=>{
 const {w,requests}=await setup({pages:[],rendered_revision:null,status:'outline_confirmed'})
 expect(w.get('.ppt-generation-actions').text()).toContain('开始生成 PPT')
 expect(w.findAll('button').filter(b=>b.text()==='开始生成 PPT')).toHaveLength(1)
 expect(w.text()).toContain('大纲已确认，课件尚未生成')
 expect(w.find('[aria-label="修改课件页面"]').exists()).toBe(false)
 expect(requests).toHaveLength(0)
})
test('busy preview preserves prior output and disables modifications and downloads',async()=>{
 const {w,requests}=await setup({job:{id:'j1',kind:'render',status:'running',stage:'制作页面',progress:10},status:'generating'})
 expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
 expect(button(w,'修改这一页').attributes('disabled')).toBeDefined()
 expect(w.find('a.ppt-download').exists()).toBe(false)
 expect(w.text()).toContain('上一版')
 expect(requests).toHaveLength(0)
})

test('cancel restores keyboard focus to the page edit action',async()=>{
 const {w}=await setup()
 const edit=button(w,'修改这一页')
 await edit.trigger('click');await flushPromises()
 const cancel=button(w,'取消')
 ;(cancel.element as HTMLButtonElement).focus()
 expect(document.activeElement).toBe(cancel.element)
 await cancel.trigger('click');await flushPromises()
 expect(document.activeElement).toBe(edit.element)
})


test('final technical fallback stays previewable and downloadable without claiming quality passed',async()=>{
 const {w,requests}=await setup({pages:[{...slides[0],delivery:{version:'ppt-delivery-1',mode:'fallback'},review:{status:'needs_attention',repairs:2,issues:[{category:'teaching',message:'内部质检意见',repair:'内部修改'}]}}],outline:{slides:[slides[0]]}})
 expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
 expect(w.get('a.ppt-download').attributes('href')).toBe('/api/presentations/p1/export')
 expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
 expect(w.find('[data-testid=page-review]').exists()).toBe(false)
 expect(w.find('[data-testid=page-status-list] .el-tag').exists()).toBe(false)
 expect(w.text()).not.toContain('内部质检意见')
 expect(w.text()).not.toContain('审核通过')
 expect(w.text()).not.toContain('仍需检查')
 expect(w.text()).not.toContain('自动补齐未通过页面')
 expect(requests).toHaveLength(0)
})

test('historical version previews its own pages and download without editing current deck',async()=>{
 const old={id:'p1',revision:1,confirmed_revision:1,rendered_revision:1,title:'旧版光合作用',style:'auto',status:'ready',outline:{slides:[slides[1]]},pages:[{...slides[1],title:'旧版原料',review:passed}],warnings:[],job:null}
 const {w,requests}=await setup({versions:[{revision:1,title:'旧版光合作用',page_count:1,created_at:null}]},{'/api/presentations/p1/versions/1':old})
 await w.get('[aria-label=课件版本]').setValue('1');await flushPromises()
 expect(w.get('.ppt-slide-preview > img').attributes('src')).toContain('version=1')
 expect(w.get('.ppt-slide-preview > img').attributes('alt')).toContain('旧版原料')
 expect(w.get('a.ppt-download').attributes('href')).toBe('/api/presentations/p1/export?version=1')
 expect(w.text()).toContain('正在查看历史版本')
 expect(w.find('[data-testid=review-summary]').exists()).toBe(false)
 expect(w.find('[data-testid=page-review]').exists()).toBe(false)
 expect(w.find('[data-testid=page-status-list] .el-tag').exists()).toBe(false)
 expect(w.findAll('button').some(b=>b.text()==='修改这一页')).toBe(false)
 await w.get('[aria-label=课件版本]').setValue('current');await flushPromises()
 expect(w.get('.ppt-slide-preview > img').attributes('src')).toBe('/api/presentations/p1/slides/s1/preview?revision=3')
 expect(button(w,'修改这一页')).toBeDefined()
 expect(requests).toHaveLength(0)
})

test('historical navigation keeps versioned downloads while current task runs',async()=>{
 const old={id:'p1',revision:1,confirmed_revision:1,rendered_revision:1,title:'旧版',status:'ready',outline:{slides},pages:slides.map(s=>({...s,review:passed})),warnings:[],job:null}
 const {w}=await setup({versions:[{revision:1,page_count:2}],job:{id:'j1',status:'running',kind:'revise',stage:'修改页面'}},{'/api/presentations/p1/versions/1':old})
 await w.get('[aria-label=课件版本]').setValue('1');await flushPromises()
 await button(w,'下一页').trigger('click')
 expect(w.get('.ppt-slide-preview > img').attributes('src')).toBe('/api/presentations/p1/slides/s2/preview?version=1')
 expect(w.get('a.ppt-download').attributes('href')).toBe('/api/presentations/p1/export?version=1')
 expect(w.find('[data-testid=review-progress]').exists()).toBe(false)
})

test('slow historical response cannot replace returning current version',async()=>{
 const {w}=await setup({versions:[{revision:1,page_count:1}]})
 let finish!:(response:Response)=>void
 vi.stubGlobal('fetch',()=>new Promise<Response>(resolve=>{finish=resolve}))
 await w.get('[aria-label=课件版本]').setValue('1')
 await w.get('[aria-label=课件版本]').setValue('current')
 finish(new Response(JSON.stringify({id:'p1',revision:1,pages:[slides[1]],outline:{slides:[slides[1]]}})));await flushPromises()
 expect(w.get('.ppt-slide-preview > img').attributes('src')).toContain('revision=3')
 expect(w.text()).not.toContain('正在查看历史版本')
})

test('historical fetch failure keeps the displayed deck and clear selection',async()=>{
 const {w}=await setup({versions:[{revision:1,page_count:1}]})
 vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({detail:{code:'ppt_version_not_found',message:'历史版本不可用'}}),{status:404}))
 await w.get('[aria-label=课件版本]').setValue('1');await flushPromises()
 expect((w.get('[aria-label=课件版本]').element as HTMLSelectElement).value).toBe('current')
 expect(w.get('.ppt-slide-preview > img').attributes('src')).toContain('revision=3')
 expect(w.text()).toContain('历史版本不可用')
})


test('current SVG preview opens the direct editor and locks page navigation',async()=>{
 const {w,requests}=await setup({pages:slides.map(s=>({...s,renderer:'ppt-master-6.7.0',review:passed}))})
 expect(button(w,'直接编辑文字')).toBeTruthy()
 await button(w,'直接编辑文字').trigger('click');await flushPromises()
 expect(w.find('[aria-label="直接编辑课件文字"]').exists()).toBe(true)
 expect(button(w,'下一页').attributes('disabled')).toBeDefined()
 expect(w.find('.ppt-download').exists()).toBe(false)
 expect(requests).toHaveLength(0)
 await w.get('[data-testid="cancel-text-edit"]').trigger('click');await flushPromises()
 expect(w.find('[aria-label="直接编辑课件文字"]').exists()).toBe(false)
 expect(w.find('.ppt-download').exists()).toBe(true)
})


test('PPT generation discloses ten credits and blocks insufficient balance before submission',async()=>{
 const {w,requests}=await setup({pages:[],rendered_revision:null,status:'outline_confirmed'},{'/api/account/credits':{balance:9,reserved:0,available:9,video_cost:10,ppt_cost:10}})
 expect(w.text()).toContain('10 积分')
 expect(w.text()).toContain('手动编辑和下载不扣费')
 const existing=globalThis.fetch
 vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>url==='/api/account/credits'?new Response(JSON.stringify({balance:9,reserved:0,available:9,video_cost:10,ppt_cost:10})):existing(url,init))
 await button(w,'开始生成 PPT').trigger('click');await flushPromises()
 expect(w.text()).toContain('积分不足')
 expect(requests).toHaveLength(0)
})
