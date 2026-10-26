import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import {createPinia,setActivePinia} from 'pinia'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus,{ElMessage} from 'element-plus'
import AppLayout from '../src/layouts/AppLayout.vue'
import CreatePptView from '../src/views/workbench/CreatePptView.vue'
import CreateVideoView from '../src/views/workbench/CreateVideoView.vue'
import {useAuthStore} from '../src/stores/auth'
import {clearCreationMemory,creationEpoch} from '../src/utils/creation-memory'
import {clearAllVideoDraftCache} from '../src/utils/video-draft-cache'

enableAutoUnmount(afterEach)
afterEach(async()=>{clearCreationMemory();await clearAllVideoDraftCache();ElMessage.closeAll();vi.unstubAllGlobals()})
const Empty={template:'<div>作品页面</div>'}
const project={id:'p1',revision:3,title:'已保存的植物课',prompt:'讲解光合作用',style:'clear-blue-teaching',web_search:false,status:'draft',materials:[]}
async function setup(path='/projects/new'){
 const fetcher=vi.fn(async(url:string)=>{
  let body:unknown=project
  if(url.includes('/config/form'))body={system_available:true,fields:[{key:'prompt',label:'想讲什么',default:'',options:[],default_by_subject:{}},{key:'materials',label:'参考素材',default:null,options:[],default_by_subject:{}}]}
  else if(url.endsWith('/config'))body={system_available:true,search_available:true,search_visible:true,search_default:false,templates:[{id:'clear-blue-teaching',name:'简洁教学'}]}
  else if(url.endsWith('/materials'))body=[{id:'saved',filename:'已保存资料.pdf',size:5,status:'stored'}]
  else if(url.includes('/credits'))body={available:60,reserved:0}
  return new Response(JSON.stringify(body))
 })
 vi.stubGlobal('fetch',fetcher)
 const pinia=createPinia();setActivePinia(pinia)
 useAuthStore().user={id:'teacher-1',username:'老师',role:'teacher',status:'active'}
 const router=createRouter({history:createMemoryHistory(),routes:[
  {path:'/projects/new',name:'project-create',component:CreateVideoView},
  {path:'/projects/:id/edit',name:'project-edit',component:CreateVideoView},
  {path:'/presentations/new',name:'ppt-create',component:CreatePptView},
  {path:'/presentations/:id/edit',name:'ppt-edit',component:CreatePptView},
  {path:'/presentations/:id/outline',name:'ppt-outline',component:Empty},
  {path:'/projects/:id/outline',name:'project-outline',component:Empty},
  {path:'/projects',name:'project-list',component:Empty},
  {path:'/drafts',name:'project-drafts',component:Empty},
  {path:'/account',name:'account-settings',component:Empty},
  {path:'/account/balance',name:'account-balance',component:Empty},
  {path:'/',name:'home',component:Empty},{path:'/login',name:'login',component:Empty}
 ]})
 await router.push(path);await router.isReady()
 const w=mount(AppLayout,{global:{plugins:[pinia,router,ElementPlus]}});await flushPromises()
 return {w,router,fetcher}
}
function title(w:ReturnType<typeof mount>){return (w.get('[data-testid=project-title]').element as HTMLInputElement).value}
async function make(w:ReturnType<typeof mount>){await w.get('a.rail-link[title=工作台]').trigger('click');await flushPromises()}
async function mode(w:ReturnType<typeof mount>,value:'ppt'|'video'){await w.get('[data-mode='+value+']').trigger('click');await flushPromises()}
async function choose(w:ReturnType<typeof mount>,name:string){const input=w.get('input[type=file]');Object.defineProperty(input.element,'files',{value:[new File(['test'],name,{type:'application/pdf'})],configurable:true});await input.trigger('change');await flushPromises()}

test('old PPT outline followed by fresh creation cannot restore previous edit address or inputs',async()=>{
 const {w,router}=await setup('/presentations/p1/edit')
 expect(title(w)).toBe(project.title)
 await w.get('[data-testid=project-title]').setValue('未保存修改');await choose(w,'不应带入新建.pdf')
 await router.push('/presentations/p1/outline');await flushPromises();await make(w);await mode(w,'ppt')
 expect(router.currentRoute.value.path).toBe('/presentations/new');expect(title(w)).toBe('')
 expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('');expect(w.text()).not.toContain('不应带入新建.pdf')
})
test('leaving unsaved PPT for My Videos resets the next creation',async()=>{
 const {w,router}=await setup('/presentations/new')
 await w.get('[data-testid=project-title]').setValue('上一次临时内容')
 await router.push('/projects');await flushPromises();await make(w);await mode(w,'ppt');expect(title(w)).toBe('')
})
test('switching modes inside same creation keeps both forms and pending files',async()=>{
 const {w}=await setup()
 await w.get('[data-testid=project-title]').setValue('视频临时内容');await choose(w,'视频资料.pdf')
 await mode(w,'ppt');await w.get('[data-testid=project-title]').setValue('课件临时内容');await choose(w,'课件资料.pdf')
 await mode(w,'video');expect(title(w)).toBe('视频临时内容');expect(w.text()).toContain('视频资料.pdf')
 await mode(w,'ppt');expect(title(w)).toBe('课件临时内容');expect(w.text()).toContain('课件资料.pdf')
})
test('reopening a saved draft uses saved values and materials instead of discarded edits',async()=>{
 const {w,router}=await setup('/presentations/p1/edit')
 await w.get('[data-testid=project-title]').setValue('不保存的编辑')
 await router.push('/drafts');await flushPromises();await router.push('/presentations/p1/edit');await flushPromises()
 expect(title(w)).toBe(project.title);expect(w.text()).toContain('已保存资料.pdf')
})
test('sidebar Video Creation starts fresh from active PPT creation',async()=>{
 const {w}=await setup('/presentations/new')
 await w.get('[data-testid=project-title]').setValue('旧课件')
 await make(w);await mode(w,'ppt');expect(title(w)).toBe('')
})
test('sidebar Video Creation resets current new video without changing URL',async()=>{
 const {w,router}=await setup()
 await w.get('[data-testid=project-title]').setValue('旧视频');await choose(w,'旧资料.pdf');await make(w)
 expect(router.currentRoute.value.path).toBe('/projects/new');expect(title(w)).toBe('');expect(w.text()).not.toContain('旧资料.pdf')
})
test('discarded video attachments cannot return in a new creation',async()=>{
 const {w,router}=await setup();await choose(w,'未保存素材.pdf')
 await router.push('/drafts');await flushPromises();await make(w);expect(w.text()).not.toContain('未保存素材.pdf')
})
test('cancelled navigation does not discard active creation session',async()=>{
 const {w,router}=await setup('/presentations/new')
 await w.get('[data-testid=project-title]').setValue('保留中的课件');await mode(w,'video');await mode(w,'ppt')
 const epoch=creationEpoch();const remove=router.beforeEach(to=>to.name==='project-create'?false:true)
 await make(w);expect(creationEpoch()).toBe(epoch);expect(title(w)).toBe('保留中的课件')
 remove();await mode(w,'video');await mode(w,'ppt');expect(title(w)).toBe('保留中的课件')
})
