import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import CreateVideoView from '../src/views/workbench/CreateVideoView.vue'
import CreatePptView from '../src/views/workbench/CreatePptView.vue'
import {clearCreationMemory} from '../src/utils/creation-memory'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.unstubAllGlobals();clearCreationMemory()})
const cases=[
 {name:'video',path:'/projects/new',view:CreateVideoView,endpoint:'/api/config/form',config:{system_available:true,form_version:'1',fields:[{key:'prompt',label:'想讲什么',default:'',options:[],default_by_subject:{}}]}},
 {name:'PPT',path:'/presentations/new',view:CreatePptView,endpoint:'/api/presentations/config',config:{system_available:true,search_available:true,search_visible:true,search_default:false,templates:[],layouts:{}}},
] as const
async function setup(item:typeof cases[number]){
 const router=createRouter({history:createMemoryHistory(),routes:[{path:item.path,component:item.view}]})
 await router.push(item.path);await router.isReady()
 const w=mount(item.view,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 return w
}
for(const item of cases){
 test(item.name+' shows a loading placeholder until configuration is ready',async()=>{
  let finish!:(value:Response)=>void
  vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{finish=resolve})))
  const w=await setup(item)
  expect(w.get('[role=status][aria-busy=true]').text()).toContain('正在加载制作设置')
  expect(w.find('[data-testid=project-title]').exists()).toBe(false)
  finish(new Response(JSON.stringify(item.config)));await flushPromises()
  expect(w.find('[role=status][aria-busy=true]').exists()).toBe(false)
  expect(w.get('[data-testid=project-title]').exists()).toBe(true)
 })
 test(item.name+' can retry a failed configuration request without reloading the page',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({detail:{code:'service_unavailable',message:'配置服务暂不可用'}}),{status:503})).mockResolvedValueOnce(new Response(JSON.stringify(item.config)))
  vi.stubGlobal('fetch',fetcher)
  const w=await setup(item)
  expect(w.text()).toContain('配置服务暂不可用')
  expect(w.find('[data-testid=project-title]').exists()).toBe(false)
  await w.get('[data-testid=retry-creation-load]').trigger('click');await flushPromises()
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect(fetcher.mock.calls.every(([url])=>url===item.endpoint)).toBe(true)
  expect(w.text()).not.toContain('配置服务暂不可用')
  expect(w.find('[data-testid=retry-creation-load]').exists()).toBe(false)
  expect(w.get('[data-testid=project-title]').exists()).toBe(true)
 })
}
