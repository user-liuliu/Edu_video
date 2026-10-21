import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {afterEach,expect,test,vi} from 'vitest'
import ProjectCover from '../src/components/workbench/ProjectCover.vue'

let wrapper:VueWrapper|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals();vi.restoreAllMocks()})
const versions=[{id:'v3',status:'failed',media_url:null},{id:'v2',status:'succeeded',media_url:'/video/final.mp4'},{id:'v1',status:'succeeded',media_url:'/video/old.mp4'}]

test('cover shows the latest playable video first frame and never starts playback',async()=>{
 const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return new Response(JSON.stringify(versions))}))
 wrapper=mount(ProjectCover,{props:{projectId:'p1',title:'函数'}});await flushPromises()
 expect(calls).toEqual(['/api/projects/p1/videos'])
 const video=wrapper.get('video')
 expect(video.attributes('src')).toBe('/video/final.mp4')
 expect(video.attributes()).not.toHaveProperty('autoplay')
 expect(video.attributes()).not.toHaveProperty('controls')
 await video.trigger('loadeddata')
 expect(wrapper.find('.cover-placeholder').exists()).toBe(false)
})

test('HTML only projects show a sandboxed frozen animation without fetching narration audio',async()=>{
 const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push(url);return url.endsWith('/videos')?new Response(JSON.stringify([{id:'v1',status:'preview_ready',html_url:'/film/html',audio_url:'/film/audio',media_url:null}])):new Response('<html><body>教学画面</body></html>')}))
 wrapper=mount(ProjectCover,{props:{projectId:'p2',title:'大禹治水'}});await flushPromises()
 expect(calls).toEqual(['/api/projects/p2/videos','/film/html'])
 const frame=wrapper.get('iframe')
 expect(frame.attributes('sandbox')).toBe('allow-scripts')
 expect(frame.attributes('srcdoc')).toContain('教学画面')
 expect(wrapper.find('audio').exists()).toBe(false)
})

test('cover failures preserve a neutral placeholder without blocking project actions',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({detail:{message:'失败'}}),{status:503})))
 wrapper=mount(ProjectCover,{props:{projectId:'p3',title:'草稿'}});await flushPromises()
 expect(wrapper.find('.cover-placeholder').exists()).toBe(true)
 expect(wrapper.find('iframe').exists()).toBe(false)
 expect(wrapper.find('video').exists()).toBe(false)
 expect(wrapper.attributes('aria-busy')).toBe('false')
})

test('offscreen cover does not fetch video resources until it becomes visible',async()=>{
 let intersect:IntersectionObserverCallback=()=>{}
 const disconnect=vi.fn()
 vi.stubGlobal('IntersectionObserver',class{constructor(cb:IntersectionObserverCallback){intersect=cb}observe(){}disconnect=disconnect})
 const fetcher=vi.fn(async()=>new Response(JSON.stringify(versions)));vi.stubGlobal('fetch',fetcher)
 wrapper=mount(ProjectCover,{props:{projectId:'p4',title:'函数'}});await flushPromises()
 expect(fetcher).not.toHaveBeenCalled()
 intersect([{isIntersecting:true}] as IntersectionObserverEntry[],{} as IntersectionObserver);await flushPromises()
 expect(wrapper.get('video').attributes('src')).toBe('/video/final.mp4')
 wrapper.unmount();wrapper=undefined
 expect(disconnect).toHaveBeenCalled()
})
