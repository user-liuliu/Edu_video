import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import {afterEach,beforeEach,expect,test,vi} from 'vitest'
import {createRouter,createMemoryHistory} from 'vue-router'
import VideoPreviewView from '../src/views/workbench/VideoPreviewView.vue'

let wrapper:VueWrapper|undefined
beforeEach(()=>{vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{})})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.unstubAllGlobals();vi.restoreAllMocks();vi.useRealTimers();sessionStorage.clear()})
function version(id='v1',status='succeeded',number=1){return {id,project_id:'p1',number,outline_revision:2,source_version_id:null,status,duration:8,created_at:'2026-10-18',style:{value:'science_animation'},job:{id:'j'+id,kind:'video',status:status==='queued'?'pending':status,stage:'正在制作动画（1/2）',progress:40,error_message:status==='failed'?'渲染失败，请重试':null},media_url:status==='succeeded'?'/api/projects/p1/videos/'+id+'/media/final':null,segments:[{id:'s'+id+'a',outline_segment_id:'o1',position:0,title:'观察图像',narration:'观察直线',start:0,end:4},{id:'s'+id+'b',outline_segment_id:'o1',position:1,title:'比较变化',narration:'比较斜率',start:4,end:8}]}}
async function setup(initial:any[]=[],outlineStatus='outline_confirmed',available=100){
 vi.useFakeTimers();let versions=initial
 const calls:{url:string;method:string;body:any}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
  if(url==='/api/account/credits')return new Response(JSON.stringify({balance:available,reserved:0,available,video_cost:10,total_credited:100,total_spent:0}))
  if(url.endsWith('/outline'))return new Response(JSON.stringify({project_id:'p1',title:'一次函数',revision:2,status:outlineStatus,needs_save:false,needs_regeneration:false,segments:[]}))
  if(method==='POST'&&url.endsWith('/export'))return new Response(JSON.stringify({id:'export1',kind:'video_export',status:'pending',stage:'准备导出',progress:0}),{status:202})
  if(method==='POST'){const next=version('v2','queued',2);versions=[next,...versions];return new Response(JSON.stringify(next),{status:202})}
  return new Response(JSON.stringify(versions))
 }))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/projects/:id/video',name:'project-video',component:VideoPreviewView},{path:'/projects/:id/outline',name:'project-outline',component:{template:'<div>大纲</div>'}}]})
 await router.push('/projects/p1/video');wrapper=mount(VideoPreviewView,{global:{plugins:[router,ElementPlus]}});await flushPromises()
 return {w:wrapper,calls,setVersions:(v:any[])=>versions=v}
}
async function click(text:string){const b=wrapper!.findAll('button').find(b=>b.text()===text);expect(b).toBeDefined();await b!.trigger('click');await flushPromises()}

test('confirmed outline can start video and register a completion reminder',async()=>{
 const {w,calls}=await setup();await click('生成视频')
 const call=calls.find(c=>c.method==='POST')!
 expect(call.url).toBe('/api/projects/p1/videos');expect(call.body.revision).toBe(2)
 expect(w.text()).toContain('正在制作动画')
 expect(sessionStorage.getItem('edu-video:outline-job-notification')).toContain('jv2')
 expect(calls.some(c=>c.url.endsWith('/confirm'))).toBe(false)
})

test('unconfirmed outline returns teacher to outline without starting a task',async()=>{
 const {w,calls}=await setup([],'outline_ready')
 expect(w.text()).toContain('请先保存并确认大纲');expect(w.findAll('button').find(b=>b.text()==='生成视频')).toBeUndefined()
 expect(calls.some(c=>c.method==='POST')).toBe(false)
})

test('playback boundary selects complete segment of displayed version for visual revision',async()=>{
 const {w,calls}=await setup([version()]);const video=w.get('video')
 Object.defineProperty(video.element,'currentTime',{value:4,writable:true,configurable:true})
 await video.trigger('pause');await click('修改这一段')
 expect(w.get('[aria-label="修改片段 sv1b"]').element.checked).toBe(true)
 expect(w.get('[aria-label="修改片段 sv1a"]').element.checked).toBe(false)
 await w.get('[aria-label="画面修改要求"]').setValue('让斜率变化再平缓一点')
 await click('生成修改版')
 const call=calls.find(c=>c.method==='POST')!
 expect(call.url).toBe('/api/projects/p1/videos/v1/revisions')
 expect(call.body.segment_ids).toEqual(['sv1b']);expect(call.body.instruction).toBe('让斜率变化再平缓一点')
 expect(call.body).not.toHaveProperty('narration')
})

test('fractional media seek selects next segment despite floating point rounding',async()=>{
 const value=version()
 value.segments[0]!.end=35.300000000000004
 value.segments[1]!.start=35.300000000000004
 value.segments[1]!.end=48.8
 const {w}=await setup([value])
 Object.defineProperty(w.get('video').element,'currentTime',{value:35.3,writable:true,configurable:true})
 await click('修改这一段')
 expect(w.get('[aria-label="修改片段 sv1b"]').element.checked).toBe(true)
 expect(w.get('[aria-label="修改片段 sv1a"]').element.checked).toBe(false)
})

test('failed newer version retains old playable video and offers retry',async()=>{
 const {w,calls}=await setup([version('v2','failed',2),version()])
 expect(w.get('video').attributes('src')).toContain('/v1/media/final')
 expect(w.text()).toContain('渲染失败')
 await click('重试失败任务')
 expect(calls.find(c=>c.method==='POST')?.body.retry_version_id).toBe('v2')
})

test('failed task can regenerate fully after model configuration changes',async()=>{
 const {w,calls}=await setup([version('v2','failed',2),version()])
 await click('重新生成完整视频')
 const body=calls.find(c=>c.method==='POST')?.body
 expect(body.revision).toBe(2);expect(body).not.toHaveProperty('retry_version_id')
 expect(w.get('video').attributes('src')).toContain('/v1/media/final')
})

test('leaving and reopening reads persisted stage and does not submit another task',async()=>{
 const {w,calls}=await setup([version('v2','running',2)])
 expect(w.text()).toContain('正在制作动画（1/2）')
 await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(calls.filter(c=>c.method==='POST')).toHaveLength(0)
 expect(w.find('[data-testid="live-outline-progress"]').exists()).toBe(true)
})

test('completed video displays duration warning and remains playable',async()=>{
 const {w}=await setup([{...version(),target_duration:60,duration_notice:'实际时长8秒，目标60秒。请返回大纲调整。'}])
 expect(w.text()).toContain('实际时长8秒')
 expect(w.get('video').attributes('src')).toContain('/v1/media/final')
 await click('返回大纲');expect(w.text()).toContain('大纲')
})


function preview(){return {...version(),status:'preview_ready',workflow:'html-preview-1',playback_mode:'whole_html',html_url:'/film/html',audio_url:'/film/audio',media_url:null,export_status:null,export_job:null,segments:version().segments}}

test('completed version reopens the exported MP4 without reinitializing HTML preview',async()=>{
 const {w,calls}=await setup([{...preview(),status:'succeeded',media_url:'/api/projects/p1/videos/v1/media/final'}],'completed')
 expect(w.find('iframe').exists()).toBe(false)
 expect(w.get('video').attributes('src')).toBe('/api/projects/p1/videos/v1/media/final')
 expect(calls.some(c=>c.url.startsWith('/film/'))).toBe(false)
})

test('media failure is visible and completed video can be reloaded without regeneration',async()=>{
 const {w,calls}=await setup([version()],'completed')
 await w.get('video').trigger('error')
 expect(w.get('[role=alert]').text()).toContain('视频加载失败')
 vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{})
 await click('重新加载视频')
 expect(HTMLMediaElement.prototype.load).toHaveBeenCalled()
 expect(w.find('[role=alert]').exists()).toBe(false)
 expect(calls.some(c=>c.method==='POST')).toBe(false)
})

test('finishing an export switches from animation to the persisted MP4',async()=>{
 const {w,setVersions}=await setup([{...preview(),export_status:'running',export_job:{id:'export1',status:'running',stage:'导出中'}}],'video_exporting')
 expect(w.find('iframe').exists()).toBe(true)
 setVersions([{...preview(),status:'succeeded',media_url:'/api/projects/p1/videos/v1/media/final',export_status:'succeeded',export_job:{id:'export1',status:'succeeded'}}])
 await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(w.find('iframe').exists()).toBe(false)
 expect(w.get('video').attributes('src')).toContain('/media/final')
})

test('narrated HTML preview requires explicit MP4 export and stays editable',async()=>{
 const {w,calls}=await setup([preview()],'preview_ready')
 expect(w.find('iframe[title="教学动画"]').exists()).toBe(true)
 expect(w.find('video').exists()).toBe(false)
 expect(calls.some(c=>c.method==='POST')).toBe(false)
 expect(w.findAll('button').find(b=>b.text()==='修改这一段')?.attributes('disabled')).toBeUndefined()
 await click('满意，导出MP4')
 expect(calls.filter(c=>c.method==='POST')).toHaveLength(1)
 expect(calls.find(c=>c.method==='POST')?.url).toBe('/api/projects/p1/videos/v1/export')
 expect(w.text()).toContain('准备导出')
 expect(sessionStorage.getItem('edu-video:outline-job-notification')).toContain('export1')
 expect(w.find('iframe').exists()).toBe(true)
})

test('failed export keeps HTML preview and retries without video generation',async()=>{
 const value={...preview(),export_status:'failed',export_job:{id:'export-old',kind:'video_export',status:'failed',error_message:'视频编码失败'}}
 const {w,calls}=await setup([value],'preview_ready')
 expect(w.text()).toContain('视频编码失败')
 expect(w.find('iframe').exists()).toBe(true)
 await click('重试导出MP4')
 expect(calls.find(c=>c.method==='POST')?.url).toContain('/v1/export')
})

test('new preview becomes selected after preparation and keeps history available',async()=>{
 const {w,setVersions}=await setup([version('v2','running',2),version()],'video_generating')
 expect(w.find('video').exists()).toBe(true)
 setVersions([{...preview(),id:'v2',number:2},version()])
 await vi.advanceTimersByTimeAsync(1100);await flushPromises()
 expect(w.find('iframe').exists()).toBe(true)
 expect(w.find('video').exists()).toBe(false)
})


test('voice-only revision sends selected scope and keeps the transcript immutable',async()=>{
 const {w,calls}=await setup([preview()],'preview_ready')
 await click('修改这一段')
 const mode=w.get('input[value=voice]');await mode.setValue(true)
 const textarea=w.get('textarea');await textarea.setValue('配音更自然清晰一些')
 await click('生成修改版')
 const call=calls.find(c=>c.method==='POST')!
 expect(call.url).toContain('/v1/revisions')
 expect(call.body.mode).toBe('voice')
 expect(call.body.segment_ids).toEqual(['sv1a'])
 expect(call.body.instruction).toBe('配音更自然清晰一些')
 expect(call.body).not.toHaveProperty('narration')
})


test('insufficient credits shows price and prevents generation request',async()=>{
 const {w,calls}=await setup([],'outline_confirmed',9)
 expect(w.text()).toContain('每次成功生成扣 10 积分')
 await click('生成视频')
 expect(w.text()).toContain('积分不足')
 expect(calls.some(call=>call.method==='POST')).toBe(false)
 expect(w.get('a[href="/account/balance"]').text()).toContain('兑换积分')
})

test('existing preview can export with zero credits',async()=>{
 const {calls}=await setup([preview()],'preview_ready',0)
 await click('满意，导出MP4')
 expect(calls.filter(call=>call.method==='POST').map(call=>call.url)).toEqual(['/api/projects/p1/videos/v1/export'])
})
