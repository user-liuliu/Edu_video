import {expect,test} from 'vitest'
import {JSDOM} from 'jsdom'
import {preparePreviewHtml} from '../src/utils/preview-frame'

test('frozen runtime strings containing body tags remain valid when adding the frame bridge',()=>{
 const html=preparePreviewHtml("<!doctype html><html><body><script>window.original='</body>';window.seek=async()=>{};</script></body></html>")
 const dom=new JSDOM(html,{runScripts:'dangerously'})
 expect(dom.window.original).toBe('</body>')
 expect(typeof dom.window.seek).toBe('function')
 dom.window.close()
})

test('the real bridge waits for drawing before acknowledging a frame',async()=>{
 const dom=new JSDOM(preparePreviewHtml('<html><body><script>window.seek=()=>new Promise(resolve=>window.finishDrawing=resolve)</script></body></html>'),{runScripts:'dangerously',pretendToBeVisual:true})
 const events:any[]=[]
 dom.window.addEventListener('message',event=>events.push(event.data))
 dom.window.dispatchEvent(new dom.window.MessageEvent('message',{source:dom.window,data:{type:'edu-preview:render',channel:'test',request:7,time:12}}))
 expect(events.some(d=>d.type==='edu-preview:rendered')).toBe(false)
 dom.window.finishDrawing()
 await new Promise<void>(resolve=>{const poll=()=>{if(events.some(d=>d.type==='edu-preview:rendered'))resolve();else setTimeout(poll,5)};poll()})
 expect(events.find(d=>d.type==='edu-preview:rendered')).toEqual({type:'edu-preview:rendered',channel:'test',request:7,time:12})
 dom.window.close()
})
