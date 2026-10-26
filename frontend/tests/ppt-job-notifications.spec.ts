import {afterEach,expect,test,vi} from 'vitest'
import {startPptJob,type PptProject} from '../src/api/presentations'
import {addPendingOutlineNotification,removePendingOutlineNotification,clearPendingOutlineNotifications,readPendingOutlineNotifications} from '../src/utils/outline-job-notification'
afterEach(()=>{sessionStorage.clear();vi.unstubAllGlobals()})
test.each(['outline','render','revise'])('submitting PPT %s registers a global completion reminder',async(kind)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({id:'ppt-job',kind,status:'pending'}))))
 await startPptJob({id:'ppt-project',revision:1} as PptProject,kind)
 expect(readPendingOutlineNotifications()).toEqual([{jobId:'ppt-job',projectId:'ppt-project',target:'ppt'}])
})
test('failed submission does not register a completion reminder',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}',{status:503})))
 await expect(startPptJob({id:'ppt-project',revision:1} as PptProject,'render')).rejects.toThrow()
 expect(readPendingOutlineNotifications()).toEqual([])
})

test('a stale running response cannot register a completed PPT job again',()=>{
 const item={jobId:'already-completed',projectId:'ppt-project',target:'ppt' as const}
 addPendingOutlineNotification(item)
 removePendingOutlineNotification(item.jobId)
 addPendingOutlineNotification(item)
 expect(readPendingOutlineNotifications()).toEqual([])
 clearPendingOutlineNotifications()
 addPendingOutlineNotification(item)
 expect(readPendingOutlineNotifications()).toEqual([item])
})
