import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, expect, test, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import CreateVideoView from '../src/views/workbench/CreateVideoView.vue'
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

test('leaving without saving keeps the previously saved requirements', async () => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async (url:string) => new Response(JSON.stringify(
    url.includes('/config/form')
      ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}}]}
      : {id:'p1',revision:1,prompt:'已保存需求',form_values:{subject:'数学'},title:'已保存项目',status:'draft'},
  ))))
  const router=createRouter({history:createMemoryHistory(),routes:[
    {path:'/projects/:id/edit',name:'project-edit',component:CreateVideoView},
    {path:'/projects',name:'project-list',component:{template:'<div>项目</div>'}},
  ]})
  await router.push('/projects/p1/edit')
  const first=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await first.get('textarea').setValue('未保存的需求修改')
  await router.push('/projects');await flushPromises()
  expect(router.currentRoute.value.name).toBe('project-list')
  first.unmount()
  await router.push('/projects/p1/edit')
  const second=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  expect((second.get('textarea').element as HTMLTextAreaElement).value).toBe('已保存需求')
  second.unmount()
})

test('refreshing a new video page starts with the initial form state', async () => {
  localStorage.setItem('edu-video:draft:project:new', JSON.stringify({prompt:'不应恢复', title:'临时标题', values:{subject:'数学'}}))
  vi.stubGlobal('performance', { getEntriesByType: () => [{ type: 'reload' }] })
  vi.stubGlobal('fetch', vi.fn(async (url:string) => new Response(JSON.stringify(
    url.includes('/config/form')
      ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}}]}
      : [],
  ))))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/new',name:'project-create',component:CreateVideoView}]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  expect(localStorage.getItem('edu-video:draft:project:new')).toBeNull()
  w.unmount()
})
test('renders configured fields and saves an actual project', async () => {
  const calls: {url:string; init?: RequestInit}[] = []
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    const body=url.includes('/config/form') ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}}]} : {id:'p1',revision:1,prompt:'二次函数',form_values:{subject:'数学'},title:'二次函数',status:'draft'}
    return new Response(JSON.stringify(body), {status: url === '/api/projects' ? 201 : 200})
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',name:'project-create',component:CreateVideoView}]})
  await router.push('/')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}})
  await flushPromises()
  expect(w.find('[data-testid="wide-workspace"]').exists()).toBe(true)
  expect(w.text()).toContain('输入需求')
  expect(w.text()).toContain('大纲草稿')
  await w.get('input[data-testid="project-title"]').setValue('二次函数')
  await w.get('textarea').setValue('二次函数')
  await w.get('[data-testid="save-draft"]').trigger('click')
  await flushPromises()
  const saved=calls.find(c=>c.url==='/api/projects' && c.init?.method==='POST')
  expect(JSON.parse(String(saved?.init?.body))).toMatchObject({prompt:'二次函数',form_version:'v1',form_values:{subject:'数学'}})
  expect(w.findAll('button').some(button => button.text() === '查看项目')).toBe(false)
  w.unmount()
})

test('saving a draft shows a success popup', async () => {
  const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => new Response(JSON.stringify(
    url.includes('/config/form')
      ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}}]}
      : {id:'p1',revision:1,prompt:'需求',form_values:{subject:'数学'},title:'需求',status:'draft'},
  ), {status:init?.method==='POST'?201:200})))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/new',name:'project-create',component:CreateVideoView}]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await w.get('input[data-testid="project-title"]').setValue('需求')
  await w.get('textarea').setValue('需求')
  await w.get('[data-testid="save-draft"]').trigger('click');await flushPromises()
  expect(success).toHaveBeenCalledWith('已保存为草稿')
  success.mockRestore();w.unmount()
})

test('saving a draft uploads selected materials without preparing them', async () => {
  const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
  const calls: {url:string; init?:RequestInit}[] = []
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    let body: unknown = {id:'p1',revision:1,prompt:'需求',form_values:{},title:'需求',status:'draft'}
    if(url.includes('/config/form')) body={system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'materials',label:'参考素材',default:null,options:[],default_by_subject:{}}]}
    else if(url.includes('/materials') && init?.method==='GET') {
      const materialReads=calls.filter(call=>call.url.includes('/materials')&&call.init?.method==='GET').length
      body=materialReads>1?[{id:'m1',filename:'课件.pdf',size:4,status:'stored',error_message:null}]:[]
    }
    else if(url.includes('/materials') && init?.method==='POST') body={id:'m1',filename:'课件.pdf',size:4,status:'stored',error_message:null}
    return new Response(JSON.stringify(body),{status:url==='/api/projects'?201:200})
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/new',name:'project-create',component:CreateVideoView}]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await w.get('input[data-testid="project-title"]').setValue('需求')
  await w.get('textarea').setValue('需求')
  const input=w.get('input[type="file"]');const file=new File(['pdf'],'课件.pdf',{type:'application/pdf'})
  Object.defineProperty(input.element,'files',{value:[file],configurable:true});await input.trigger('change');await flushPromises()
  await w.get('[data-testid="save-draft"]').trigger('click');await flushPromises()
  expect(calls.some(call=>String(call.url).includes('/materials')&&call.init?.method==='POST')).toBe(true)
  expect(calls.some(call=>String(call.url).includes('/materials?defer_parse=true')&&call.init?.method==='POST')).toBe(true)
  expect(calls.some(call=>String(call.url).endsWith('/materials/prepare')&&call.init?.method==='POST')).toBe(false)
  expect(calls.filter(call=>call.url.includes('/materials')&&call.init?.method==='GET').length).toBeGreaterThanOrEqual(2)
  expect(w.text()).toContain('课件.pdf')
  expect(success).toHaveBeenCalledWith('已保存为草稿')
  success.mockRestore()
  w.unmount()
})

test('loading an existing project keeps the restored form clean',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/config/form')?{system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'语文',label:'语文',subjects:null}],default_by_subject:{}}]}:{id:'p1',revision:1,prompt:'已保存需求',title:'已保存',status:'draft',form_values:{subject:'语文'}}))))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/edit',component:CreateVideoView},{path:'/projects',name:'project-list',component:{template:'<div />'}}]})
 await router.push('/projects/p1/edit')
 const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 const {ElMessageBox}=await import('element-plus')
 const confirm=vi.spyOn(ElMessageBox,'confirm').mockRejectedValue('cancel')
 await router.push('/projects');await flushPromises()
 expect(confirm).not.toHaveBeenCalled();expect(router.currentRoute.value.path).toBe('/projects')
 confirm.mockRestore();w.unmount()
})

test('existing outline uses regenerate action and asks for confirmation', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  vi.stubGlobal('fetch', vi.fn(async (url:string) => new Response(JSON.stringify(
    url.includes('/config/form')
      ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}}]}
      : {id:'p1',revision:2,prompt:'已有大纲需求',form_values:{subject:'数学'},title:'已有大纲',status:'outline_ready',needs_regeneration:false},
  ))))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/edit',name:'project-edit',component:CreateVideoView}]})
  await router.push('/projects/p1/edit')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  const regenerate=w.findAll('button').find(button=>button.text()==='重新生成大纲')
  expect(regenerate).toBeTruthy()
  expect(w.findAll('button').some(button=>button.text()==='生成大纲')).toBe(false)
  await regenerate!.trigger('click');await flushPromises()
  expect(confirm).toHaveBeenCalledWith('是否重新生成大纲','重新生成大纲',{confirmButtonText:'重新生成大纲',cancelButtonText:'取消',type:'warning'})
  confirm.mockRestore();w.unmount()
})

test('project name is required before saving a new draft', async () => {
  const calls: {url:string; init?:RequestInit}[] = []
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    return new Response(JSON.stringify(url.includes('/config/form')
      ? {system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}}]}
      : {id:'p1',revision:1,prompt:'需求',form_values:{},title:'需求',status:'draft'}), {status: url === '/api/projects' ? 201 : 200})
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/new',name:'project-create',component:CreateVideoView}]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await w.get('textarea').setValue('需求')
  await w.get('[data-testid="save-draft"]').trigger('click');await flushPromises()
  expect(w.text()).toContain('请填写项目名称')
  expect(calls.some(call=>call.url==='/api/projects'&&call.init?.method==='POST')).toBe(false)
  w.unmount()
})

test('new files are uploaded only when generating the outline', async () => {
  const calls: {url:string; init?:RequestInit}[] = []
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    let body: unknown={id:'p1',revision:1,prompt:'需求',form_values:{},title:'需求',status:'draft'}
    if(url.includes('/config/form')) body={system_available:true,form_version:'v1',fields:[{key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},{key:'materials',label:'参考素材',default:null,options:[],default_by_subject:{}}]}
    else if(url==='/api/projects') body={id:'p1',revision:1,prompt:'需求',form_values:{},title:'需求',status:'draft'}
    else if(url.includes('/materials')&&init?.method==='POST') body={id:'m1',filename:'课件.pdf',size:4,status:'stored',error_message:null}
    else if(url.includes('/outline/generate')) body={id:'j1',project_id:'p1',kind:'generate',status:'pending',stage:'等待处理',progress:0,error_message:null}
    else if(url.includes('/materials')&&init?.method==='GET') body=[{id:'m1',filename:'课件.pdf',size:4,status:'ready',error_message:null}]
    return new Response(JSON.stringify(body),{status:url==='/api/projects'?201:200})
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[
    {path:'/projects/new',name:'project-create',component:CreateVideoView},
    {path:'/projects/:id/outline',name:'project-outline',component:{template:'<div>大纲</div>'}},
  ]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await w.get('input[data-testid="project-title"]').setValue('需求')
  await w.get('textarea').setValue('需求')
  const input=w.get('input[type="file"]');const file=new File(['pdf'],'课件.pdf',{type:'application/pdf'})
  Object.defineProperty(input.element,'files',{value:[file],configurable:true});await input.trigger('change');await flushPromises()
  expect(calls.some(call=>String(call.url).includes('/materials')&&call.init?.method==='POST')).toBe(false)
  const generateButton=w.findAll('button').find((button)=>button.text()==='生成大纲')
  await generateButton!.trigger('click');await flushPromises()
  expect(calls.some(call=>String(call.url).includes('/materials')&&call.init?.method==='POST')).toBe(true)
  expect(calls.some(call=>String(call.url).includes('/outline/generate'))).toBe(true)
  expect(JSON.parse(sessionStorage.getItem('edu-video:outline-job-notification') ?? 'null'))
    .toEqual([{ jobId: 'j1', projectId: 'p1' }])
  w.unmount()
})

test('submits a durable outline task without waiting for material parsing in the page', async () => {
  const calls: {url:string; init?:RequestInit}[] = []
  const reason = '素材图片无法识别，请使用 PNG/JPEG/WebP 图片'
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    let body: unknown
    if (url.includes('/config/form')) body={system_available:true,form_version:'v1',fields:[
      {key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},
      {key:'materials',label:'参考素材',default:null,options:[],default_by_subject:{}},
    ]}
    else if (url.includes('/outline/generate')) body={id:'j1',project_id:'p1',kind:'generate',status:'pending',stage:'等待素材解析',progress:0,error_message:null}
    else if (url.includes('/materials')) body=[{id:'m1',filename:'课件.docx',size:4,status:'stored',error_message:null}]
    else body={id:'p1',revision:1,prompt:'需求',form_values:{},title:'需求',status:'draft'}
    return new Response(JSON.stringify(body),{status:url==='/api/projects'?201:202})
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/edit',name:'project-edit',component:CreateVideoView},{path:'/projects/:id/outline',name:'project-outline',component:{template:'<div>等待后台生成</div>'}}]})
  await router.push('/projects/p1/edit')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
  await w.findAll('button').find(button=>button.text()==='生成大纲')!.trigger('click');await flushPromises()
  expect(calls.some(call=>call.url.includes('/outline/generate'))).toBe(true)
  expect(calls.some(call=>call.url.endsWith('/materials/prepare'))).toBe(false)
  expect(router.currentRoute.value.name).toBe('project-outline')
  w.unmount()
})
