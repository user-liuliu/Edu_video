import {mount,flushPromises,enableAutoUnmount,type VueWrapper} from '@vue/test-utils'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus,{ElMessageBox} from 'element-plus'
import {afterEach,expect,test,vi} from 'vitest'
import PptList from '../src/components/workbench/PptList.vue'
import type {PptProject} from '../src/api/presentations'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks()})
const slides=[{id:'s1',title:'封面',layout:'cover',content:'植物怎样生长',slots:{}},{id:'s2',title:'第二页',layout:'summary',content:'课堂回顾',slots:{}}]
const project:PptProject={id:'p1',title:'植物的一生',prompt:'讲解植物生长过程',style:'auto',web_search:false,status:'ready',revision:3,confirmed_revision:3,rendered_revision:3,outline:{slides},pages:slides,warnings:[],job:null,updated_at:'2026-10-25T10:00:00Z'}
async function setup(items:PptProject[]=[project],drafts=false,total=items.length){
 const fetcher=vi.fn(async(_url:string,init?:RequestInit)=>init?.method==='DELETE'?new Response(null,{status:204}):new Response(JSON.stringify({items,total})))
 vi.stubGlobal('fetch',fetcher)
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{template:'<div />'}},...['ppt-create','ppt-preview','ppt-outline','ppt-edit'].map(name=>({path:'/presentation/'+name+'/:id?',name,component:{template:'<div />'}}))]})
 await router.push('/')
 const w=mount(PptList,{props:{drafts},global:{plugins:[router,ElementPlus]}})
 await flushPromises()
 return {w,router,fetcher}
}
function button(w:VueWrapper,text:string){return w.findAll('button').find(b=>b.text()===text)!}

test('PPT works use the video card layout and real first-page preview',async()=>{
 const {w,router,fetcher}=await setup()
 expect(fetcher.mock.calls[0]?.[0]).toContain('scope=completed')
 const card=w.get('.projects article')
 expect(card.get('.project-info .status').text()).toBe('已导出')
 expect(card.get('.summary').text()).toBe(project.prompt)
 expect(card.text()).toContain('2 页')
 expect(card.text()).toContain('更新于')
 const cover=card.get('.project-cover img')
 expect(cover.attributes('src')).toBe('/api/presentations/p1/slides/s1/preview?revision=3')
 expect(cover.attributes('loading')).toBe('lazy')
 await cover.trigger('load')
 expect(card.find('.cover-placeholder').exists()).toBe(false)
 expect(card.get('.ppt-cover').attributes('aria-busy')).toBe('false')
 expect(w.find('iframe').exists()).toBe(false)
 expect(w.get('a[href*=export]').attributes('href')).toBe('/api/presentations/p1/export')
 await button(w,'查看课件').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-preview')
 expect(router.currentRoute.value.params.id).toBe('p1')
})

test('PPT drafts use the same cards and placeholders while keeping editing available',async()=>{
 const draft={...project,status:'draft',rendered_revision:null,pages:[],outline:null}
 const {w,router,fetcher}=await setup([draft],true)
 expect(fetcher.mock.calls[0]?.[0]).toContain('scope=drafts')
 expect(w.get('h1').text()).toBe('PPT 草稿')
 expect(w.get('.projects article .project-cover').exists()).toBe(true)
 expect(w.find('.project-cover img').exists()).toBe(false)
 expect(w.find('a[href*=export]').exists()).toBe(false)
 await button(w,'继续编辑').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-edit')
})

test('a failed cover does not leave a broken image or block opening the PPT',async()=>{
 const {w,router}=await setup()
 await w.get('.project-cover img').trigger('error')
 expect(w.find('.project-cover img').exists()).toBe(false)
 expect(w.get('.project-cover .app-icon').exists()).toBe(true)
 await button(w,'查看课件').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-preview')
})

test.each(['stale','unapproved','reordered'])('%s first page uses a placeholder rather than another slide',async kind=>{
 const p=structuredClone(project)
 if(kind==='stale')p.rendered_revision=2
 if(kind==='reordered')p.outline!.slides=[...p.outline!.slides].reverse()
 if(kind==='unapproved'){
  p.status='partial_ready'
  p.pages=p.pages.map((s,i)=>({...s,review:{status:i===0?'needs_attention':'passed',repairs:0,issues:i===0?[{category:'teaching',message:'需要修改',repair:'调整内容'}]:[]}}))
 }
 const {w}=await setup([p],true)
 expect(w.find('.project-cover img').exists()).toBe(false)
 expect(button(w,'查看课件').exists()).toBe(true)
 if(kind==='unapproved')expect(w.get('a[href*=export]').attributes('href')).toContain('partial=true')
})

test('partial PPT uses the actual first page when it passed review',async()=>{
 const pages=slides.map((s,i)=>({...s,review:{status:i===0?'passed' as const:'needs_attention' as const,repairs:0,issues:i===0?[]:[{category:'teaching' as const,message:'需要修改',repair:'调整内容'}]}}))
 const {w}=await setup([{...project,status:'partial_ready',pages}],true)
 expect(w.get('.project-cover img').attributes('src')).toContain('/slides/s1/preview')
 expect(w.get('a[href*=export]').attributes('href')).toContain('partial=true')
})

test('switching from works to drafts resets pagination and still opens the outline',async()=>{
 const {w,router,fetcher}=await setup([{...project,rendered_revision:null,pages:[],status:'outline_ready'}],false,21)
 await w.get('.btn-next').trigger('click');await flushPromises()
 expect(fetcher.mock.calls.at(-1)?.[0]).toContain('page=2')
 await w.setProps({drafts:true});await flushPromises()
 expect(fetcher.mock.calls.at(-1)?.[0]).toContain('scope=drafts&page=1')
 await button(w,'继续编辑').trigger('click');await flushPromises()
 expect(router.currentRoute.value.name).toBe('ppt-outline')
})

test('PPT deletion still confirms and reloads the list',async()=>{
 const confirm=vi.spyOn(ElMessageBox,'confirm').mockResolvedValue('confirm')
 const {w,fetcher}=await setup()
 await button(w,'删除').trigger('click');await flushPromises()
 expect(confirm).toHaveBeenCalled()
 expect(fetcher.mock.calls.some(([url,init])=>url==='/api/presentations/p1?revision=3'&&init?.method==='DELETE')).toBe(true)
 expect(fetcher.mock.calls.filter(([url])=>url.includes('scope=completed'))).toHaveLength(2)
})

test('PPT generation keeps deletion disabled',async()=>{
 const {w}=await setup([{...project,status:'generating'}],true)
 expect(button(w,'删除').attributes('disabled')).toBeDefined()
})


test.each(['fallback','teacher_confirmed'] as const)('%s delivery displays real first page on drafts and works',async mode=>{
 const first={...slides[0]!,review:mode==='fallback'?{status:'needs_attention' as const,repairs:2,issues:[{category:'teaching' as const,message:'内部记录',repair:'已交付'}]}:undefined,delivery:{version:'ppt-delivery-1',mode}}
 const second={...slides[1]!,review:{status:'passed' as const,repairs:0,issues:[]}}
 for(const drafts of [true,false]){
  const {w}=await setup([{...project,pages:[first,second]}],drafts)
  expect(w.get('.project-cover img').attributes('src')).toContain('/slides/s1/preview')
  expect(w.get('a[href*=export]').attributes('href')).not.toContain('partial=true')
 }
})
