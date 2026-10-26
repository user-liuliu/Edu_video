import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory,RouterView} from 'vue-router'
import ElementPlus,{ElMessageBox} from 'element-plus'
import PptOutlineView from '../src/views/workbench/PptOutlineView.vue'
import PptPreviewView from '../src/views/workbench/PptPreviewView.vue'
import PptList from '../src/components/workbench/PptList.vue'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals();ElMessageBox.close()})
const outline={slides:[{id:'s1',layout:'concept',title:'二次函数',content:'y=ax²+bx+c，a≠0',slots:{}}],review:{status:'passed',version:'ppt-knowledge-1',issues:[],changes:[],repairs:0}}
const project={id:'p1',revision:3,title:'函数',prompt:'讲解函数',style:'auto',web_search:false,status:'outline_ready',confirmed_revision:null,rendered_revision:null,updated_at:'2026-10-25T00:00:00Z',outline,pages:[],warnings:[],job:null}
async function setup({path='/presentations/p1/outline',confirmed=false,vision=true,fail=false,pages=false}={}){
 let saved:any={...project,...(confirmed?{confirmed_revision:3,status:'outline_confirmed'}:{}),...(pages?{pages:outline.slides,status:'ready',rendered_revision:3}:{})}
 const requests:{url:string;method:string;body:any}[]=[]
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
  if(url==='/api/account/credits')return new Response(JSON.stringify({available:100,video_cost:10,ppt_cost:10}))
  const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):undefined
  requests.push({url,method,body})
  if(url.endsWith('/config'))return new Response(JSON.stringify({system_available:true,review_available:vision,layouts:{concept:'概念与公式'}}))
  if(url.endsWith('/confirm')){
   if(fail)return new Response(JSON.stringify({detail:{code:'revision_conflict',message:'课件已更新，请刷新后重试'}}),{status:409})
   saved={...saved,confirmed_revision:3,status:'outline_confirmed'};return new Response(JSON.stringify(saved))
  }
  if(url.endsWith('/jobs/render')){saved={...saved,status:'generating',job:{id:'j1',kind:'render',status:'running',stage:'制作页面',progress:10}};return new Response(JSON.stringify(saved.job))}
  return new Response(JSON.stringify(saved))
 })
 vi.stubGlobal('fetch',fetcher)
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/presentations/:id/outline',name:'ppt-outline',component:PptOutlineView},{path:'/presentations/:id/preview',name:'ppt-preview',component:PptPreviewView},{path:'/presentations/:id/edit',name:'ppt-edit',component:{template:'<div>需求</div>'}}]})
 await router.push(path);const w=mount(RouterView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 return {w,router,requests}
}
function button(w:ReturnType<typeof mount>,label:string){return w.findAll('button').find(b=>b.text()===label)!}

test('confirming an outline navigates to preview without starting generation',async()=>{
 const confirm=vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
 const {w,router,requests}=await setup()
 await button(w,'确认大纲').trigger('click');await flushPromises()
 expect(confirm).toHaveBeenCalled()
 expect(requests.filter(r=>r.url.endsWith('/confirm'))).toEqual([{url:'/api/presentations/p1/confirm',method:'POST',body:{revision:3}}])
 expect(requests.some(r=>r.url.includes('/jobs/'))).toBe(false)
 expect(router.currentRoute.value.name).toBe('ppt-preview')
 expect(w.text()).toContain('大纲已确认，课件尚未生成')
 expect(button(w,'开始生成 PPT').exists()).toBe(true)
})
test('cancelling outline confirmation makes no mutation and stays in editor',async()=>{
 vi.spyOn(ElMessageBox,'confirm').mockRejectedValue('cancel')
 const {w,router,requests}=await setup()
 await button(w,'确认大纲').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-outline')
 expect(requests.some(r=>r.method==='POST')).toBe(false)
 expect(w.find('[aria-label="第 1 页标题"]').exists()).toBe(true)
})
test('failed confirmation preserves editor and explains revision conflict',async()=>{
 vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
 const {w,router,requests}=await setup({fail:true})
 await button(w,'确认大纲').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-outline')
 expect(w.text()).toContain('课件已更新，请刷新后重试')
 expect(requests.some(r=>r.url.includes('/jobs/'))).toBe(false)
})
test('confirmed outline preview stays idle after loading until explicit start',async()=>{
 const {w,requests}=await setup({path:'/presentations/p1/preview',confirmed:true})
 expect(w.text()).toContain('大纲已确认，课件尚未生成')
 expect(requests.some(r=>r.url.includes('/jobs/'))).toBe(false)
 await button(w,'开始生成 PPT').trigger('click');await flushPromises()
 expect(requests.filter(r=>r.url.endsWith('/jobs/render'))).toHaveLength(1)
 expect(requests.find(r=>r.url.endsWith('/jobs/render'))?.body).toMatchObject({revision:3})
 expect(w.find('[data-testid=review-progress]').exists()).toBe(true)
})
test('direct preview access cannot generate an unconfirmed outline',async()=>{
 const {w,requests}=await setup({path:'/presentations/p1/preview'})
 expect(w.text()).toContain('请先返回大纲页确认当前大纲')
 expect(button(w,'开始生成 PPT')).toBeUndefined()
 expect(button(w,'重新生成并审核')).toBeUndefined()
 expect(requests.some(r=>r.url.includes('/jobs/'))).toBe(false)
})
test('confirmation is independent of vision model availability',async()=>{
 vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
 const {w,router}=await setup({vision:false})
 expect(button(w,'确认大纲').attributes('disabled')).toBeUndefined()
 await button(w,'确认大纲').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-preview')
})
test('already confirmed outline reopens preview without confirming or generating again',async()=>{
 const {w,router,requests}=await setup({confirmed:true})
 await button(w,'进入 PPT 预览').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-preview')
 expect(requests.some(r=>r.method==='POST')).toBe(false)
})
test('editing a confirmed outline requires saving and review before reconfirming',async()=>{
 const {w}=await setup({confirmed:true})
 await w.get('[aria-label="第 1 页标题"]').setValue('修订后的标题')
 expect(button(w,'进入 PPT 预览')).toBeUndefined()
 expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
})


test('an existing confirmed deck can be regenerated from preview while keeping its previous pages',async()=>{
 const {w,requests}=await setup({path:'/presentations/p1/preview',confirmed:true,pages:true})
 expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
 await button(w,'重新生成整份 PPT').trigger('click');await flushPromises()
 expect(requests.filter(r=>r.url.endsWith('/jobs/render'))).toHaveLength(1)
 expect(w.find('.ppt-slide-preview > img').exists()).toBe(true)
 expect(w.text()).toContain('上一版')
})

test('draft list translates the confirmed outline status',async()=>{
 vi.stubGlobal('fetch',async()=>new Response(JSON.stringify({items:[{...project,status:'outline_confirmed',confirmed_revision:3}],total:1})))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{template:'<div />'}}]})
 await router.push('/')
 const w=mount(PptList,{props:{drafts:true},global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(w.text()).toContain('大纲已确认')
 expect(w.text()).not.toContain('outline_confirmed')
})


test.each([false,true])('outline groups save, review and the next step with confirmed=%s',async(confirmed)=>{
 const {w}=await setup({confirmed,pages:confirmed})
 const actions=w.get('[aria-label="大纲操作"]')
 expect(actions.findAll('button').map(b=>b.text())).toEqual(['保存大纲','已审查',confirmed?'进入 PPT 预览':'确认大纲'])
 expect(w.get('[data-testid=knowledge-review]').findAll('button')).toHaveLength(0)
 expect(button(w,'查看已生成课件')).toBeUndefined()
})

test('adding a page follows the outline content and keeps edits subject to review',async()=>{
 const {w}=await setup({confirmed:true})
 const add=button(w,'添加页面')
 const pages=w.get('.outline-pages').element
 expect(Boolean(pages.compareDocumentPosition(add.element)&Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
 expect(Boolean(add.element.compareDocumentPosition(w.get('[aria-label="选页修改"]').element)&Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
 await add.trigger('click')
 expect(w.findAll('.outline-pages .outline-page')).toHaveLength(2)
 expect(button(w,'确认大纲').attributes('disabled')).toBeDefined()
 expect(button(w,'保存大纲').attributes('disabled')).toBeUndefined()
})
