import {mount,flushPromises} from '@vue/test-utils'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import {test,expect,vi,afterEach} from 'vitest'
import ProjectListView from '../src/views/workbench/ProjectListView.vue'
import PreferencesView from '../src/views/workbench/PreferencesView.vue'
afterEach(()=>vi.unstubAllGlobals())

test('draft list uses real projects and continues the selected draft',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify({items:[{id:'p1',title:'教材草稿',prompt:'二次函数',status:'draft',updated_at:'2026-10-16T10:00:00Z'}],total:21})))
 vi.stubGlobal('fetch',fetch)
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/drafts',name:'project-drafts',component:ProjectListView},{path:'/projects/:id/edit',name:'project-edit',component:{template:'<div />'}},{path:'/projects/:id/outline',name:'project-outline',component:{template:'<div />'}},{path:'/projects/new',name:'project-create',component:{template:'<div />'}}]})
 await router.push('/drafts')
 const w=mount(ProjectListView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(fetch.mock.calls[0]?.[0]).toContain('scope=drafts')
 expect(w.text()).toContain('教材草稿');expect(w.text()).toContain('草稿箱');expect(w.findAll('button').some(b=>b.text()==='新建视频')).toBe(false)
 const button=w.findAll('button').find(b=>b.text()==='继续编辑')!
 await button.trigger('click');await flushPromises()
 expect(router.currentRoute.value.params.id).toBe('p1');expect(router.currentRoute.value.name).toBe('project-edit');w.unmount()
})

test('completed video list requests only completed projects',async()=>{
 const fetch=vi.fn(async()=>new Response(JSON.stringify({items:[{id:'p2',title:'已完成视频',prompt:'二次函数',status:'completed',updated_at:'2026-10-16T11:00:00Z'}],total:1})))
 vi.stubGlobal('fetch',fetch)
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects',name:'project-list',component:ProjectListView},{path:'/projects/:id/outline',name:'project-outline',component:{template:'<div />'}},{path:'/projects/new',name:'project-create',component:{template:'<div />'}}]})
 await router.push('/projects')
 const w=mount(ProjectListView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 expect(fetch.mock.calls[0]?.[0]).toContain('scope=completed')
 expect(w.text()).toContain('已完成视频');expect(w.text()).not.toContain('草稿箱');expect(w.findAll('button').some(b=>b.text()==='新建视频')).toBe(false);w.unmount()
})

test('preferences remain unavailable while global memory is disabled',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({enabled:false,options:{},items:[],suggestions:[]}))))
 const w=mount(PreferencesView,{global:{plugins:[ElementPlus]}});await flushPromises()
 expect(w.text()).toContain('管理员已关闭长期偏好');expect(w.find('form').exists()).toBe(false);w.unmount()
})

test('saving a selected preference sends its category and explicit choice',async()=>{
 const calls:{url:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return new Response(JSON.stringify({enabled:true,options:{teaching:['多用生活实例'],expression:['简洁清晰'],visual:[],settings:[]},items:[],suggestions:[]}))}))
 const w=mount(PreferencesView,{global:{plugins:[ElementPlus]}});await flushPromises()
 expect(w.find('[data-testid="preferences-card-grid"]').exists()).toBe(true)
 await w.get('form').trigger('submit');await flushPromises()
 const saved=calls.find(c=>c.init?.method==='POST')!
 expect(JSON.parse(String(saved.init?.body))).toEqual({category:'teaching',value:'多用生活实例'});w.unmount()
})
