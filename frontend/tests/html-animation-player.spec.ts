import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {beforeEach,afterEach,expect,test,vi} from 'vitest'
import HtmlAnimationPlayer from '../src/components/workbench/HtmlAnimationPlayer.vue'
let wrapper:VueWrapper|undefined
const segments=[{id:'a',outline_segment_id:'o',position:0,title:'观察',narration:'观察',start:0,end:1,html_url:'/a/html',audio_url:'/a/audio'},{id:'b',outline_segment_id:'o',position:1,title:'比较',narration:'比较',start:1,end:2,html_url:'/b/html',audio_url:'/b/audio'}]
beforeEach(()=>{
 vi.useFakeTimers();vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{});vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue(undefined)
 vi.stubGlobal('requestAnimationFrame',vi.fn(()=>1));vi.stubGlobal('cancelAnimationFrame',vi.fn())
 Object.defineProperty(URL,'createObjectURL',{value:vi.fn(()=> 'blob:audio'),configurable:true});Object.defineProperty(URL,'revokeObjectURL',{value:vi.fn(),configurable:true})
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(url.endsWith('html')?'<html>animation</html>':'audio')))
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks();vi.unstubAllGlobals();vi.useRealTimers()})
async function setup(){wrapper=mount(HtmlAnimationPlayer,{props:{segments,duration:2,htmlUrl:'/film/html',audioUrl:'/film/audio'},attachTo:document.body});await flushPromises();return wrapper}
async function connect(painted=true){
 const iframe=wrapper!.get('iframe');const post=vi.spyOn(iframe.element.contentWindow!,'postMessage')
 await iframe.trigger('load');const data=post.mock.calls.find(c=>(c[0] as any)?.type==='edu-preview:init')![0] as any
 window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{type:'edu-preview:ready',channel:data.channel}}));await flushPromises()
 const render=post.mock.calls.find(c=>(c[0] as any)?.type==='edu-preview:render')?.[0] as any
 if(painted&&render){window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{...render,type:'edu-preview:rendered'}}));await flushPromises()}
 return post
}

test('a ready script without a rendered frame never enables playback',async()=>{
 const w=await setup();await connect(false)
 expect(w.get('button.play-toggle').attributes('disabled')).toBeDefined()
 expect(w.find('[role=status]').exists()).toBe(true)
 await vi.advanceTimersByTimeAsync(13000)
 expect(w.get('button.play-toggle').attributes('disabled')).toBeDefined()
 expect(w.get('[role=alert]').text()).toContain('动画')
})

test('a foreign or stale render acknowledgement cannot enable playback',async()=>{
 const w=await setup(),post=await connect(false),iframe=w.get('iframe')
 const render=post.mock.calls.find(c=>(c[0] as any)?.type==='edu-preview:render')![0] as any
 for(const [source,data] of [[window,{...render,type:'edu-preview:rendered'}],[iframe.element.contentWindow,{...render,request:render.request+1,type:'edu-preview:rendered'}]]){
  window.dispatchEvent(new MessageEvent('message',{source:source as Window,data}));await flushPromises()
  expect(w.get('button.play-toggle').attributes('disabled')).toBeDefined()
 }
})

test('seeks made during drawing end at the newest requested position',async()=>{
 const w=await setup(),post=await connect(),iframe=w.get('iframe')
 await w.get('input').setValue(.4);await w.get('input').setValue(1.7)
 const first=post.mock.calls.filter(c=>(c[0] as any)?.type==='edu-preview:render').at(-1)![0] as any
 window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{...first,type:'edu-preview:rendered'}}));await flushPromises()
 const last=post.mock.calls.filter(c=>(c[0] as any)?.type==='edu-preview:render').at(-1)![0] as any
 expect(last.time).toBe(1.7)
 window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{...last,type:'edu-preview:rendered'}}));await flushPromises()
 expect(w.emitted('time')?.at(-1)).toEqual([1.7]);expect(w.find('[role=alert]').exists()).toBe(false)
})

test('reopening shows a visible frame even when the iframe load fires before its bridge is ready',async()=>{
 const w=await setup(),iframe=w.get('iframe'),post=vi.spyOn(iframe.element.contentWindow!,'postMessage')
 await iframe.trigger('load')
 post.mockClear()
 await vi.advanceTimersByTimeAsync(600)
 const init=post.mock.calls.find(c=>(c[0] as any)?.type==='edu-preview:init')?.[0] as any
 expect(init).toBeDefined()
 window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{type:'edu-preview:ready',channel:init.channel}}))
 await flushPromises()
 const render=post.mock.calls.find(c=>(c[0] as any)?.type==='edu-preview:render')?.[0] as any
 window.dispatchEvent(new MessageEvent('message',{source:iframe.element.contentWindow,data:{...render,type:'edu-preview:rendered'}}))
 await flushPromises()
 expect(w.get('button.play-toggle').attributes('disabled')).toBeUndefined()
 expect(post.mock.calls.some(c=>(c[0] as any)?.type==='edu-preview:render'&&(c[0] as any).time===0)).toBe(true)
})
test('whole HTML seeks across teaching sections without reloading document or audio',async()=>{
 wrapper=mount(HtmlAnimationPlayer,{props:{segments,duration:2,htmlUrl:'/film/html',audioUrl:'/film/audio'},attachTo:document.body})
 await flushPromises();const post=await connect();const iframe=wrapper.get('iframe').element,audio=wrapper.get('audio').element
 expect(fetch).toHaveBeenCalledWith('/film/html',expect.anything())
 await wrapper.get('input').setValue(1.4);await flushPromises()
 expect(wrapper.get('iframe').element).toBe(iframe);expect(wrapper.get('audio').element).toBe(audio)
 expect(fetch).toHaveBeenCalledTimes(2)
 expect(post.mock.calls.some(c=>(c[0] as any).type==='edu-preview:render'&&(c[0] as any).time===1.4)).toBe(true)
 Object.defineProperty(audio,'currentTime',{value:1.6,writable:true,configurable:true});await wrapper.get('audio').trigger('timeupdate')
 expect(wrapper.emitted('time')?.at(-1)).toEqual([1.6])
 await wrapper.get('audio').trigger('ended');await flushPromises()
 expect(fetch).toHaveBeenCalledTimes(2);expect(wrapper.emitted('time')?.at(-1)).toEqual([2])
})
test('sandbox connects only its own frame and seeks with audio clock',async()=>{
 const w=await setup();expect(w.get('iframe').attributes('sandbox')).toBe('allow-scripts')
 expect(w.get('button.play-toggle').attributes('disabled')).toBeDefined()
 const post=await connect();expect(w.get('button.play-toggle').attributes('disabled')).toBeUndefined()
 await w.get('button.play-toggle').trigger('click');await flushPromises()
 const first=post.mock.calls.filter(c=>(c[0] as any)?.type==='edu-preview:render').at(-1)![0] as any
 window.dispatchEvent(new MessageEvent('message',{source:w.get('iframe').element.contentWindow,data:{...first,type:'edu-preview:rendered'}}));await flushPromises()
 const audio=w.get('audio');Object.defineProperty(audio.element,'currentTime',{value:.6,writable:true,configurable:true});await audio.trigger('timeupdate')
 expect(w.emitted('time')?.at(-1)).toEqual([.6]);expect(post.mock.calls.some(c=>(c[0] as any).type==='edu-preview:render'&&(c[0] as any).time===.6)).toBe(true)
 await w.get('input').setValue(1);await flushPromises();await connect()
 expect(w.emitted('time')?.at(-1)).toEqual([1]);expect(fetch).toHaveBeenCalledTimes(2)
 expect(w.get('button.play-toggle').text()).toBe('播放')
})
test('foreign readiness messages cannot start the player',async()=>{
 const w=await setup();window.dispatchEvent(new MessageEvent('message',{source:window,data:{type:'edu-preview:ready',channel:'forged'}}));await flushPromises()
 expect(w.get('button.play-toggle').attributes('disabled')).toBeDefined();expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled()
})
test('ended stops the whole film and leaving revokes audio',async()=>{
 const w=await setup();await connect();await w.get('button.play-toggle').trigger('click');await flushPromises()
 await w.get('audio').trigger('ended');await flushPromises();await connect()
 expect(w.get('button.play-toggle').text()).toBe('播放');expect(fetch).toHaveBeenCalledTimes(2)
 w.unmount();wrapper=undefined;expect(URL.revokeObjectURL).toHaveBeenCalled();expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled()
})
test('late play resolution after seek never pauses newer segment audio',async()=>{
 const w=await setup();await connect();let resolve!:()=>void
 vi.mocked(HTMLMediaElement.prototype.play).mockImplementationOnce(()=>new Promise<void>(r=>resolve=r))
 await w.get('button.play-toggle').trigger('click')
 const oldAudio=w.get('audio').element
 await w.get('input').setValue(1);await flushPromises();await connect()
 await w.get('button.play-toggle').trigger('click');await flushPromises();const currentAudio=w.get('audio').element
 const pause=vi.mocked(HTMLMediaElement.prototype.pause);pause.mockClear();resolve();await flushPromises()
 expect(oldAudio).toBe(currentAudio)
 expect(pause.mock.instances).not.toContain(currentAudio)
})

test.each(['resolve','reject'])('old same-segment play %s cannot interrupt a newer play',async(outcome)=>{
 const w=await setup();await connect();let resolve!:()=>void,reject!:(e:Error)=>void
 vi.mocked(HTMLMediaElement.prototype.play).mockImplementationOnce(()=>new Promise<void>((a,b)=>{resolve=a;reject=b}))
 await w.get('button.play-toggle').trigger('click')
 await w.get('input').setValue(.4);await flushPromises()
 await w.get('button.play-toggle').trigger('click');await flushPromises()
 expect(w.get('button.play-toggle').text()).toBe('暂停')
 const pause=vi.mocked(HTMLMediaElement.prototype.pause);pause.mockClear()
 if(outcome==='resolve')resolve();else reject(new Error('old interruption'))
 await flushPromises()
 expect(w.get('button.play-toggle').text()).toBe('暂停')
 expect(w.find('[role=alert]').exists()).toBe(false)
 expect(pause).not.toHaveBeenCalled()
})
