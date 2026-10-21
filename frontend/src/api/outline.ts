import {request} from './http'
export type Visual={kind:'插图'|'数学图形'|'公式'|'学科示意图'|'文字卡';description:string}
export type Segment={id:string;position:number;title:string;objective:string;narration:string;visuals:Visual[];evidence_ids:string[];content_kind:'knowledge'|'fact'|'reenactment';review_notes:string[];review_passed?:boolean|null;review_issues?:string[];estimated_duration_seconds:number;content_revision:number;reviewed_revision:number}
export type Outline={project_id:string;title:string;revision:number;status:string;segments:Segment[];job_id:string|null;needs_regeneration:boolean;needs_save?:boolean;material_warnings?:{material_id:string;filename:string;location:string;message:string}[]}
export type Job={id:string;project_id:string;kind:string;workflow?:string|null;status:string;stage:string;progress:number;error_message:string|null;created_at?:string;updated_at?:string}
export type Evidence={id:string;claim:string;source_type:string;source_ref:string;location:string;excerpt:string;source_grade:string;verification_status:string}
const base=(id:string)=>'/api/projects/'+encodeURIComponent(id)+'/outline'
export const getOutline=(id:string)=>request<Outline>('GET',base(id))
export const saveOutline=(id:string,revision:number,segments:Segment[])=>request<Outline>('PUT',base(id),{revision,segments})
export const submitOutlineJob=(id:string,operation:'generate'|'rewrite'|'review',revision:number,extra:Record<string,unknown>={})=>request<Job>('POST',base(id)+'/'+operation,{revision,idempotency_key:crypto.randomUUID(),...extra})
export const getJob=(id:string)=>request<Job>('GET','/api/jobs/'+encodeURIComponent(id))
export const confirmOutline=(id:string,revision:number)=>request<Outline>('POST',base(id)+'/confirm',{revision})
export const getEvidence=(pid:string,id:string)=>request<Evidence>('GET','/api/projects/'+encodeURIComponent(pid)+'/evidence/'+encodeURIComponent(id))
