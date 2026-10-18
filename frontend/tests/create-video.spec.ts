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


test('restoring a draft preserves a non-default textbook and later subject changes apply defaults', async () => {
  const calls: {url: string; init?: RequestInit}[] = []
  const form = {system_available:true,form_version:'v1',fields:[
    {key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},
    {key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null},{value:'物理',label:'物理',subjects:null}],default_by_subject:{}},
    {key:'textbook_edition',label:'教材版本',default:'数学默认版',options:[
      {value:'数学默认版',label:'数学默认版',subjects:['数学']},
      {value:'物理默认版',label:'物理默认版',subjects:['物理']},
      {value:'物理自选版',label:'物理自选版',subjects:['物理']},
    ],default_by_subject:{数学:'数学默认版',物理:'物理默认版'}},
  ]}
  const saved={id:'p1',revision:1,title:'串联电路',prompt:'讲解串联电路',status:'draft',form_values:{subject:'物理',textbook_edition:'物理自选版'}}
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    calls.push({url,init})
    return new Response(JSON.stringify(url.includes('/config/form')?form:init?.method==='PATCH'?{...saved,...JSON.parse(String(init.body)),revision:2}:saved))
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/edit',component:CreateVideoView}]})
  await router.push('/projects/p1/edit')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}})
  try {
    await flushPromises()
    expect(w.findAllComponents({name:'ElSelect'})[1]!.props('modelValue')).toBe('物理自选版')
    await w.get('[data-testid="save-draft"]').trigger('click');await flushPromises()
    const request=calls.find(call=>call.init?.method==='PATCH')
    expect(JSON.parse(String(request?.init?.body)).form_values).toMatchObject({subject:'物理',textbook_edition:'物理自选版'})
    w.findAllComponents({name:'ElSelect'})[0]!.vm.$emit('update:modelValue','数学')
    await flushPromises()
    expect(w.findAllComponents({name:'ElSelect'})[1]!.props('modelValue')).toBe('数学默认版')
  } finally { w.unmount() }
})

test('save and material upload keep all requirement controls disabled until persistence completes', async () => {
  let finishSave!: (response: Response) => void
  let finishUpload!: (response: Response) => void
  const saveResponse=new Promise<Response>(resolve=>{finishSave=resolve})
  const uploadResponse=new Promise<Response>(resolve=>{finishUpload=resolve})
  const calls: string[]=[]
  const saved={id:'p1',revision:1,title:'项目',prompt:'原始需求',status:'draft',form_values:{subject:'数学'}}
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    calls.push(url)
    if(url==='/api/projects'&&init?.method==='POST')return saveResponse
    if(url.includes('/materials')&&init?.method==='POST')return uploadResponse
    return new Response(JSON.stringify(url.includes('/config/form')?{system_available:true,form_version:'v1',fields:[
      {key:'prompt',label:'想讲什么',default:null,options:[],default_by_subject:{}},
      {key:'subject',label:'科目',default:'数学',options:[{value:'数学',label:'数学',subjects:null}],default_by_subject:{}},
      {key:'web_search',label:'联网搜索',default:false,options:[],default_by_subject:{}},
      {key:'materials',label:'参考素材',default:null,options:[],default_by_subject:{}},
    ]}:url.includes('/materials')?[]:saved))
  }))
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/new',component:CreateVideoView}]})
  await router.push('/projects/new')
  const w=mount(CreateVideoView,{global:{plugins:[router,ElementPlus]}})
  try {
    await flushPromises()
    await w.get('input[data-testid="project-title"]').setValue('项目')
    await w.get('textarea').setValue('原始需求')
    const fileInput=w.get('input[type="file"]')
    Object.defineProperty(fileInput.element,'files',{value:[new File(['pdf'],'课件.pdf',{type:'application/pdf'})],configurable:true})
    await fileInput.trigger('change');await flushPromises()
    await w.get('[data-testid="save-draft"]').trigger('click');await flushPromises()
    function expectLocked(disabled: boolean) {
      expect((w.get('input[data-testid="project-title"]').element as HTMLInputElement).disabled).toBe(disabled)
      expect((w.get('textarea').element as HTMLTextAreaElement).disabled).toBe(disabled)
      expect(w.getComponent({name:'ElSelect'}).find('.el-select__wrapper').classes().includes('is-disabled')).toBe(disabled)
      expect((w.get('[role="switch"]').element).getAttribute('aria-disabled')==='true').toBe(disabled)
      expect((w.get('input[type="file"]').element as HTMLInputElement).disabled).toBe(disabled)
    }
    expectLocked(true)
    finishSave(new Response(JSON.stringify(saved),{status:201}));await flushPromises()
    expect(calls.some(url=>url.includes('/materials?defer_parse=true'))).toBe(true)
    expectLocked(true)
    finishUpload(new Response(JSON.stringify({id:'m1',filename:'课件.pdf',size:3,status:'stored'})));await flushPromises()
    expectLocked(false)
  } finally {
    finishSave(new Response(JSON.stringify(saved)));finishUpload(new Response('{}'));await flushPromises();w.unmount()
  }
})
