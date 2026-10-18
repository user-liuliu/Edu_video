import {mount,flushPromises} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import {afterEach,expect,test,vi} from 'vitest'
import MaterialUpload from '../src/components/workbench/MaterialUpload.vue'
afterEach(()=>vi.unstubAllGlobals())
test('partial material parsing visibly warns about omitted images and their location',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify([{id:'m1',filename:'电路.docx',size:123,status:'ready',error_message:null,parse_warnings:[{location:'文档插图 9',message:'该图片未解析，请补传 PNG/JPEG/WebP 图片'}]}]))))
 const w=mount(MaterialUpload,{props:{projectId:'p1'},global:{plugins:[ElementPlus]}});await flushPromises()
 expect(w.text()).toContain('部分内容未解析')
 expect(w.text()).toContain('文档插图 9')
 expect(w.text()).toContain('补传 PNG/JPEG/WebP')
 w.unmount()
})
test('explains upload limits and lists actual material status',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify([{id:'m1',filename:'课件.docx',size:123,status:'failed',error_message:'文档损坏'}]))))
 const w=mount(MaterialUpload,{props:{projectId:'p1'},global:{plugins:[ElementPlus]}});await flushPromises()
 expect(w.text()).toContain('25 MiB');expect(w.text()).toContain('课件.docx');expect(w.text()).toContain('文档损坏');expect(w.text()).toContain('重试');w.unmount()
})

test('new video keeps selected files pending without uploading before generation', async () => {
 vi.stubGlobal('fetch', vi.fn(async()=>new Response(JSON.stringify([]))))
 const w=mount(MaterialUpload,{props:{pendingFiles:[]},global:{plugins:[ElementPlus]}})
 await flushPromises()
 const file=new File(['lesson'], 'lesson.txt', {type:'text/plain'})
 const input=w.get('input[type="file"]')
 Object.defineProperty(input.element,'files',{value:[file],configurable:true})
 await input.trigger('change')
 await flushPromises()
 expect(w.text()).toContain('lesson.txt')
 expect(vi.mocked(fetch)).not.toHaveBeenCalledWith('/api/projects',expect.anything())
 expect(vi.mocked(fetch).mock.calls.some(([url,init])=>String(url).includes('/materials')&&init?.method==='POST')).toBe(false)
 w.unmount()
})

test('existing draft keeps selected files pending until the draft is saved', async () => {
 const calls: {url:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,init});return new Response(JSON.stringify(url.includes('/materials')&&(init?.method==='POST'||init?.method==='GET')?[{id:'m1',filename:'lesson.pdf',size:4,status:'stored',error_message:null}]:[]))}))
 const w=mount(MaterialUpload,{props:{projectId:'p1'},global:{plugins:[ElementPlus]}});await flushPromises()
 const input=w.get('input[type="file"]');const file=new File(['pdf'],'lesson.pdf',{type:'application/pdf'})
 Object.defineProperty(input.element,'files',{value:[file],configurable:true});await input.trigger('change');await flushPromises()
 expect(calls.some(call=>call.url.includes('/materials')&&call.init?.method==='POST')).toBe(false)
 expect(w.text()).toContain('点击保存草稿时上传')
 w.unmount()
})
