import {mount,flushPromises,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import ElementPlus from 'element-plus'
import PptTextEditor from '../src/components/workbench/PptTextEditor.vue'
enableAutoUnmount(afterEach)
async function pointer(node:{element:Element},type:string,init:Record<string,number>){const event=new MouseEvent(type,{bubbles:true,cancelable:true,...init});Object.defineProperty(event,'pointerId',{value:init.pointerId});node.element.dispatchEvent(event);await flushPromises()}
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks()})
const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><text x="64" y="100" font-size="48" fill="#173359">光合作用</text><path d="M0 0L10 10" stroke="#2465D9"/></svg>'
const descriptor={revision:3,svg,objects:[{key:'object-1',path:[0],kind:'text',label:'光合作用',text_key:'text-0',bounds:[64,52,240,70]},{key:'object-2',path:[1],kind:'shape',label:'图形',bounds:[0,0,10,10]}],blocks:[{key:'text-0',text:'光合作用',x:64,y:100,font_size:48,color:'#173359',bold:false,editable:true}]}
async function setup(fail=false){
 const requests:{url:string;init?:RequestInit}[]=[]
 vi.stubGlobal('fetch',async(url:string,init?:RequestInit)=>{requests.push({url,init});return init?.method==='PATCH'?new Response(JSON.stringify(fail?{detail:{code:'ppt_text_invalid',message:'文字放不下，请缩小字号'}}:{id:'p1',revision:4}),{status:fail?422:200}):new Response(JSON.stringify(descriptor))})
 const w=mount(PptTextEditor,{props:{projectId:'p1',slideId:'s1',revision:3},global:{plugins:[ElementPlus]}});await flushPromises();return {w,requests}
}
test('selecting SVG text edits live and undo restores text without a model request',async()=>{
 const {w,requests}=await setup()
 await w.get('[data-text-key="text-0"]').trigger('dblclick')
 await w.get('[aria-label="画面原位文字输入"]').setValue('植物的能量')
 expect(w.get('svg text').text()).toBe('植物的能量')
 await w.get('[aria-label="文字颜色"]').setValue('#224466')
 expect(w.get('svg text').attributes('fill')).toBe('#224466')
 await w.get('[data-testid="undo-text-edit"]').trigger('click')
 expect(w.get('svg text').attributes('fill')).toBe('#173359')
 await w.get('[data-testid="undo-text-edit"]').trigger('click')
 expect(w.get('svg text').text()).toBe('光合作用')
 expect(requests.filter(r=>r.init?.method==='PATCH')).toHaveLength(0)
})
test('save submits patches and emits a new version',async()=>{
 const {w,requests}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick')
 await w.get('[aria-label="画面原位文字输入"]').setValue('植物的能量')
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const sent=requests.find(r=>r.init?.method==='PATCH')!
 expect(sent.url).toBe('/api/presentations/p1/slides/s1/text')
 expect(JSON.parse(String(sent.init?.body))).toMatchObject({revision:3,edits:[{key:'text-0',text:'植物的能量'}]})
 expect(String(sent.init?.body)).not.toContain('<svg')
 expect(w.emitted('saved')?.[0]?.[0]).toMatchObject({revision:4})
})
test('save failure preserves input and cancel does not mutate the project',async()=>{
 const {w}=await setup(true);await w.get('[data-text-key="text-0"]').trigger('dblclick')
 await w.get('[aria-label="画面原位文字输入"]').setValue('保留我的输入')
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 expect(w.text()).toContain('文字放不下')
 expect((w.get('[aria-label="画面原位文字输入"]').element as HTMLTextAreaElement).value).toBe('保留我的输入')
 expect(w.emitted('saved')).toBeUndefined()
 await w.get('[data-testid="cancel-text-edit"]').trigger('click')
 expect(w.emitted('cancel')).toHaveLength(1)
})

test('inline input keeps native spaces, newlines and IME keys',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 const overlay=w.get('[aria-label="画面原位文字输入"]')
 for(const key of [' ','Enter']){
  const event=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true})
  overlay.element.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(false)
 }
 await overlay.setValue('学习目标 1\n学习目标 2')
 expect(w.get('svg text').text()).toContain('学习目标 2')
})

test('single click selects frame and double click edits on the original canvas',async()=>{
 const {w}=await setup()
 await w.get('[data-text-key="text-0"]').trigger('click');await flushPromises()
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(false)
 expect(w.findAll('[data-resize-handle]')).toHaveLength(8)
 await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(true)
 expect(w.find('[aria-label="文字内容"]').exists()).toBe(false)
 expect(w.get('.ppt-editor-toolbar').element.compareDocumentPosition(w.get('.ppt-editor-canvas').element)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
test('add text box places editable text on the canvas and saves only structured additions',async()=>{
 const {w,requests}=await setup()
 await w.get('[data-testid="add-text-box"]').trigger('click')
 await w.get('.ppt-editor-canvas').trigger('click',{clientX:200,clientY:250});await flushPromises()
 await w.get('[aria-label="画面原位文字输入"]').setValue('新增课堂提问')
 expect(w.get('svg').text()).toContain('新增课堂提问')
 expect(w.get('[aria-label="画面原位文字输入"]').attributes('style')).toContain('width: 31.25%')
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const body=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body))
 expect(body.additions).toHaveLength(1)
 expect(body.additions[0]).toMatchObject({text:'新增课堂提问',font_size:28,color:'#173359'})
 expect(body.edits).toEqual([])
 expect(String(body)).not.toContain('<svg')
})


test('dragging text maps scaled pointer motion to slide coordinates and saves movement once',async()=>{
 const {w,requests}=await setup()
 const canvas=w.get('.ppt-editor-canvas')
 vi.spyOn(canvas.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:640,height:360,right:640,bottom:360,x:0,y:0,toJSON:()=>({})})
 await pointer(w.get('[data-text-key="text-0"]'),'pointerdown',{clientX:50,clientY:50,pointerId:1,button:0})
 await pointer(canvas,'pointermove',{clientX:90,clientY:65,pointerId:1})
 await pointer(canvas,'pointerup',{clientX:90,clientY:65,pointerId:1})
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(false)
 expect(w.get('[data-text-key="text-0"]').attributes('transform')).toContain('80 30')
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const body=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body))
 expect(body.moves).toEqual([{key:'object-1',dx:80,dy:30}])
 expect(body.edits).toEqual([])
})

test('drag cancel and undo restore objects without discarding text changes',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick')
 await w.get('[aria-label="画面原位文字输入"]').setValue('新文字')
 await w.get('[data-testid="move-mode"]').trigger('click')
 const node=w.get('[data-object-key="object-2"]'),canvas=w.get('.ppt-editor-canvas')
 await pointer(node,'pointerdown',{clientX:10,clientY:10,pointerId:1,button:0})
 await pointer(canvas,'pointermove',{clientX:40,clientY:30,pointerId:1})
 await pointer(canvas,'pointercancel',{pointerId:1})
 expect(w.get('[data-object-key="object-2"]').attributes('transform')??'').not.toContain('translate')
 await pointer(w.get('[data-object-key="object-2"]'),'pointerdown',{clientX:10,clientY:10,pointerId:2,button:0})
 await pointer(canvas,'pointermove',{clientX:40,clientY:30,pointerId:2})
 await pointer(canvas,'pointerup',{clientX:40,clientY:30,pointerId:2})
 await w.get('[data-testid="undo-text-edit"]').trigger('click')
 expect(w.get('svg text').text()).toBe('新文字')
 expect(w.get('[data-object-key="object-2"]').attributes('transform')??'').not.toContain('translate')
})

test('move mode supports keyboard nudging and text click still opens inline editing',async()=>{
 const {w}=await setup()
 await w.get('[data-testid="move-mode"]').trigger('click')
 await w.get('[data-object-key="object-1"]').trigger('click')
 await w.get('[data-object-key="object-1"]').trigger('keydown',{key:'ArrowRight',shiftKey:true})
 expect(w.get('[data-object-key="object-1"]').attributes('transform')).toContain('10 0')
 await w.get('[data-testid="move-mode"]').trigger('click')
 await w.get('[data-text-key="text-0"]').trigger('dblclick')
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(true)
})


test('selected group moves as one object instead of dragging its child',async()=>{
 const groupSvg=svg.replace('<text','<g id="illustration"><text').replace('</svg>','</g></svg>')
 const requests:RequestInit[]=[]
 vi.stubGlobal('fetch',async(_url:string,init?:RequestInit)=>{if(init)requests.push(init);return new Response(JSON.stringify(init?.method==='PATCH'?{revision:4}:{...descriptor,svg:groupSvg,objects:[{key:'object-1',path:[0],kind:'group',label:'组合',bounds:[0,0,400,300]},{key:'object-2',path:[0,0],kind:'text',label:'光合作用',text_key:'text-0',bounds:[64,52,240,70]}]}))})
 const w=mount(PptTextEditor,{props:{projectId:'p1',slideId:'s1',revision:3},global:{plugins:[ElementPlus]}});await flushPromises()
 await w.get('[aria-label="选择移动对象"]').setValue('object-1')
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-text-key="text-0"]'),'pointerdown',{clientX:50,clientY:50,pointerId:1,button:0})
 await pointer(canvas,'pointermove',{clientX:80,clientY:70,pointerId:1})
 await pointer(canvas,'pointerup',{pointerId:1})
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 expect(JSON.parse(String(requests.find(i=>i.method==='PATCH')?.body)).moves).toEqual([{key:'object-1',dx:30,dy:20}])
})


test('manual save shows saving without suggesting a quality check',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick')
 await w.get('[aria-label="画面原位文字输入"]').setValue('教师编辑')
 let finish:(response:Response)=>void=()=>{}
 vi.stubGlobal('fetch',()=>new Promise<Response>(resolve=>{finish=resolve}))
 await w.get('[data-testid="save-text-edit"]').trigger('click')
 expect(w.get('[data-testid="save-text-edit"]').text()).toBe('保存中')
 finish(new Response(JSON.stringify({id:'p1',revision:4})));await flushPromises()
})


test('selected text has move and resize handles even while inline input is open',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(true)
 expect(w.find('[data-testid="text-move-handle"]').exists()).toBe(true)
 expect(w.find('[data-testid="text-resize-corner"]').exists()).toBe(true)
 expect(w.find('[data-testid="text-resize-width"]').exists()).toBe(true)
})

test('dragging width handle reflows textbox and submits width with one undo step',async()=>{
 const {w,requests}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 const canvas=w.get('.ppt-editor-canvas')
 vi.spyOn(canvas.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:640,height:360,right:640,bottom:360,x:0,y:0,toJSON:()=>({})})
 await pointer(w.get('[data-testid="text-resize-width"]'),'pointerdown',{clientX:150,clientY:80,pointerId:3,button:0})
 await pointer(canvas,'pointermove',{clientX:200,clientY:80,pointerId:3})
 await pointer(canvas,'pointerup',{pointerId:3})
 expect(Number((w.get('[aria-label="文本框宽度"]').element as HTMLInputElement).value)).toBeGreaterThan(300)
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const body=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body))
 expect(body.edits[0].width).toBeGreaterThan(300)
 expect(body.moves).toEqual([])
})

test('corner resize changes frame width and height while preserving font size, cancel restores',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-testid="text-resize-corner"]'),'pointerdown',{clientX:200,clientY:80,pointerId:5,button:0})
 await pointer(canvas,'pointermove',{clientX:260,clientY:100,pointerId:5})
 expect((w.get('[aria-label="文字字号"]').element as HTMLInputElement).value).toBe('48')
 expect(Number((w.get('[aria-label="文本框高度"]').element as HTMLInputElement).value)).toBeGreaterThan(70)
 await pointer(canvas,'pointercancel',{pointerId:5})
 expect((w.get('[aria-label="文字字号"]').element as HTMLInputElement).value).toBe('48')
 expect(w.get('[data-testid="save-text-edit"]').attributes('disabled')).toBeDefined()
})

test('move handle drags existing text while overlay was open',async()=>{
 const {w,requests}=await setup();await w.get('[data-text-key="text-0"]').trigger('dblclick');await flushPromises()
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-testid="text-move-handle"]'),'pointerdown',{clientX:100,clientY:80,pointerId:6,button:0})
 await pointer(canvas,'pointermove',{clientX:125,clientY:95,pointerId:6})
 await pointer(canvas,'pointerup',{pointerId:6})
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const body=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body))
 expect(body.moves).toEqual([{key:'object-1',dx:25,dy:15}])
})

test('new box stays selectable in move mode and its frame can drag after typing',async()=>{
 const {w}=await setup();await w.get('[data-testid="add-text-box"]').trigger('click')
 await w.get('.ppt-editor-canvas').trigger('click',{clientX:200,clientY:250});await flushPromises()
 await w.get('[aria-label="画面原位文字输入"]').setValue('新增文本框')
 await w.get('[data-testid="move-mode"]').trigger('click')
 await w.get('[data-text-key="new-1"]').trigger('click');await flushPromises()
 expect(w.find('[data-testid="text-move-handle"]').exists()).toBe(true)
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-testid="text-move-handle"]'),'pointerdown',{clientX:50,clientY:50,pointerId:7,button:0})
 await pointer(canvas,'pointermove',{clientX:100,clientY:70,pointerId:7})
 await pointer(canvas,'pointerup',{pointerId:7})
 expect((w.get('[aria-label="文本框横坐标"]').element as HTMLInputElement).value).toBe('114')
})


test('top left resize moves frame origin and shrinks size with undo restoring geometry',async()=>{
 const {w,requests}=await setup();await w.get('[data-text-key="text-0"]').trigger('click');await flushPromises()
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-resize-handle="nw"]'),'pointerdown',{clientX:64,clientY:52,pointerId:8,button:0})
 await pointer(canvas,'pointermove',{clientX:84,clientY:62,pointerId:8})
 await pointer(canvas,'pointerup',{pointerId:8})
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const patch=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body)).edits[0]
 expect(patch.x).toBe(84);expect(patch.y).toBe(110)
 expect(patch.width).toBe(220);expect(patch.height).toBeCloseTo(60)
})


test('moving then expanding frame left submits final positive slide position',async()=>{
 const {w,requests}=await setup();await w.get('[data-text-key="text-0"]').trigger('click');await flushPromises()
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-testid="text-move-handle"]'),'pointerdown',{clientX:50,clientY:50,pointerId:9,button:0})
 await pointer(canvas,'pointermove',{clientX:250,clientY:50,pointerId:9})
 await pointer(canvas,'pointerup',{pointerId:9})
 await pointer(w.get('[data-resize-handle="w"]'),'pointerdown',{clientX:264,clientY:50,pointerId:10,button:0})
 await pointer(canvas,'pointermove',{clientX:32,clientY:50,pointerId:10})
 await pointer(canvas,'pointerup',{pointerId:10})
 await w.get('[data-testid="save-text-edit"]').trigger('click');await flushPromises()
 const body=JSON.parse(String(requests.find(r=>r.init?.method==='PATCH')?.init?.body))
 expect(body.edits[0].x).toBe(32)
 expect(body.edits[0].width).toBe(472)
})


test('west resize never exceeds supported maximum textbox width',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('click');await flushPromises()
 await w.get('[aria-label="文本框宽度"]').setValue('1200')
 const canvas=w.get('.ppt-editor-canvas')
 await pointer(w.get('[data-resize-handle="w"]'),'pointerdown',{clientX:64,clientY:50,pointerId:11,button:0})
 await pointer(canvas,'pointermove',{clientX:0,clientY:50,pointerId:11})
 await pointer(canvas,'pointerup',{pointerId:11})
 expect((w.get('[aria-label="文本框宽度"]').element as HTMLInputElement).value).toBe('1200')
})


test('selection preserves SVG text node so native double click can enter editing',async()=>{
 const {w}=await setup();const node=w.get('[data-text-key="text-0"]')
 await node.trigger('click');await flushPromises()
 expect(w.get('[data-text-key="text-0"]').element).toBe(node.element)
 await node.trigger('click');await node.trigger('dblclick');await flushPromises()
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(true)
})


test('double click on the selection frame also edits the selected text',async()=>{
 const {w}=await setup();await w.get('[data-text-key="text-0"]').trigger('click');await flushPromises()
 await w.get('[data-resize-handle="s"]').trigger('dblclick');await flushPromises()
 expect(w.find('[aria-label="画面原位文字输入"]').exists()).toBe(true)
})
