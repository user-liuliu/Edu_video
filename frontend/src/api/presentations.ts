import {request} from './http'
import {addPendingOutlineNotification} from '../utils/outline-job-notification'
import type {Material} from './materials'
export type PptSlide={id:string;layout:string;title:string;content:string;slots:Record<string,string>}
export type PptReviewIssue={category:'teaching'|'readability'|'visual'|'file'|'generation'|'service';severity?:'blocking'|'suggestion';message:string;repair:string}
export type PptReview={status:'passed'|'needs_attention'|'pending';repairs:number;rebuilds?:number;issues:PptReviewIssue[];version?:string;content_sha256?:string;image_sha256?:string}
export type PptPage=PptSlide&{renderer?:string;review?:PptReview;delivery?:{version:string;mode:'reviewed'|'fallback'|'teacher_confirmed';content_sha256?:string;image_sha256?:string}}
export type PptWarning={message?:string;filename?:string;location?:string;slide_id?:string;page?:number}
export type PptJob={id:string;project_id:string;kind:string;status:string;stage:string;progress:number;error_message:string|null;created_at?:string;updated_at?:string}
export type PptKnowledgeReview={status:'passed'|'needs_attention';version:string;issues:{slide_id:string;message:string;repair:string}[];changes:{slide_id:string;message:string;before:string;after:string;title_before?:string;title_after?:string}[];repairs:number}
export const pptBlockingIssues=(issues:PptReviewIssue[])=>issues.filter(i=>i.category!=='visual'&&(['teaching','readability','file','generation','service'].includes(i.category)||i.severity!=='suggestion'))
export const pptPageApproved=(page:PptPage)=>page.review?.status==='passed'&&!pptBlockingIssues(page.review.issues).length
export const pptPageDelivered=(page:PptPage)=>page.delivery?.version==='ppt-delivery-1'&&['reviewed','fallback','teacher_confirmed'].includes(page.delivery.mode)
export type PptVersion={revision:number;title:string;page_count:number;created_at:string|null}
export type PptProject={id:string;title:string;prompt:string;style:string;template_id?:string;template_version?:string;template_name?:string;web_search:boolean;status:string;revision:number;confirmed_revision:number|null;rendered_revision:number|null;outline:{slides:PptSlide[];review?:PptKnowledgeReview}|null;pages:PptPage[];warnings:PptWarning[];job:PptJob|null;updated_at:string;versions?:PptVersion[]}
export type PptConfig={system_available:boolean;review_available?:boolean;search_available:boolean;search_visible:boolean;search_default:boolean;templates:{id:string;version:string;name:string}[];layouts:Record<string,string>}
const base=(id:string)=>'/api/presentations/'+encodeURIComponent(id)
export const getPptConfig=()=>request<PptConfig>('GET','/api/presentations/config')
export const getPpt=(id:string)=>request<PptProject>('GET',base(id))
export const getPptVersion=(id:string,version:number)=>request<PptProject>('GET',base(id)+'/versions/'+version)
export const listPpts=(scope='all',page=1)=>request<{items:PptProject[];total:number}>('GET',`/api/presentations?scope=${scope}&page=${page}`)
export const savePpt=(body:{title:string;prompt:string;style:string;web_search:boolean;revision?:number},id?:string)=>request<PptProject>(id?'PUT':'POST',id?base(id):'/api/presentations',body)
export const deletePpt=(p:PptProject)=>request<void>('DELETE',base(p.id)+'?revision='+p.revision)
export const savePptOutline=(p:PptProject,slides:PptSlide[])=>request<PptProject>('PUT',base(p.id)+'/outline',{revision:p.revision,slides})
export const confirmPptOutline=(p:PptProject)=>request<PptProject>('POST',base(p.id)+'/confirm',{revision:p.revision})
export async function startPptJob(p:PptProject,kind:string,extra:Record<string,unknown>={}){
 const job=await request<PptJob>('POST',base(p.id)+'/jobs/'+kind,{revision:p.revision,idempotency_key:crypto.randomUUID(),...extra})
 if(['outline','render','revise'].includes(kind))addPendingOutlineNotification({jobId:job.id,projectId:p.id,target:'ppt'})
 return job
}
export const getPptJob=(id:string)=>request<PptJob>('GET','/api/presentations/jobs/'+encodeURIComponent(id))
export const pptMaterialApi={
  list:(id:string)=>request<Material[]>('GET',base(id)+'/materials'),
  upload:(p:PptProject,file:File)=>{const form=new FormData();form.append('file',file);return request<Material>('POST',base(p.id)+'/materials?revision='+p.revision,form)},
  remove:(id:string,mid:string,revision:number)=>request<void>('DELETE',base(id)+'/materials/'+encodeURIComponent(mid)+'?revision='+revision),
  retry:(id:string,mid:string,revision:number)=>request<Material>('POST',base(id)+'/materials/'+encodeURIComponent(mid)+'/retry?revision='+revision),
}
export const pptExportUrl=(id:string,partial=false,version?:number)=>base(id)+'/export'+(version?'?version='+version+(partial?'&partial=true':''):partial?'?partial=true':'')
export const pptPreviewUrl=(p:PptProject,sid:string,version?:number)=>base(p.id)+'/slides/'+encodeURIComponent(sid)+'/preview?'+(version?'version='+version:'revision='+p.revision)

export type PptTextBlock={key:string;text:string;font_size:number;color:string;bold:boolean;x:number;y:number;anchor?:string;width?:number|null;height?:number|null;editable:boolean}
export type PptTextPatch={key:string;text?:string;font_size?:number;color?:string;bold?:boolean;x?:number;y?:number;width?:number;height?:number}
export type PptTextAddition={key:string;text:string;x:number;y:number;width:number;height?:number;font_size:number;color:string;bold:boolean}
export type PptCanvasObject={key:string;path:number[];kind:'text'|'image'|'group'|'shape';label:string;text_key?:string|null;bounds:[number,number,number,number]}
export type PptObjectMove={key:string;dx:number;dy:number}
export type PptEditorData={revision:number;svg:string;blocks:PptTextBlock[];objects?:PptCanvasObject[]}
export const getPptEditor=(id:string,sid:string,revision:number)=>request<PptEditorData>('GET',base(id)+'/slides/'+encodeURIComponent(sid)+'/editor?revision='+revision)
export const savePptText=(id:string,sid:string,revision:number,edits:PptTextPatch[],additions:PptTextAddition[]=[],moves:PptObjectMove[]=[])=>request<PptProject>('PATCH',base(id)+'/slides/'+encodeURIComponent(sid)+'/text',{revision,edits,additions,moves})
