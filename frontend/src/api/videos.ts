import {request} from './http'
import type {Job} from './outline'
import {addPendingOutlineNotification} from '../utils/outline-job-notification'
export type VideoSegment={id:string;outline_segment_id:string;position:number;title:string;narration:string;start:number|null;end:number|null;media_url?:string|null;html_url?:string|null;audio_url?:string|null}
export type VideoVersion={playback_mode?:string;html_url?:string|null;audio_url?:string|null;id:string;project_id:string;number:number;outline_revision:number;source_version_id:string|null;status:'queued'|'running'|'preview_ready'|'succeeded'|'failed';workflow?:string;aspect_ratio?:string;export_status?:string|null;export_job?:Job|null;duration:number|null;target_duration?:number|null;duration_notice?:string|null;created_at:string;style:Record<string,unknown>;job:Job;segments:VideoSegment[];media_url:string|null}
const base=(id:string)=>'/api/projects/'+encodeURIComponent(id)+'/videos'
export const listVideos=(id:string)=>request<VideoVersion[]>('GET',base(id))
export async function submitVideo(id:string,revision:number,retryVersionId?:string){
 const video=await request<VideoVersion>('POST',base(id),{revision,idempotency_key:crypto.randomUUID(),...(retryVersionId?{retry_version_id:retryVersionId}:{})})
 addPendingOutlineNotification({jobId:video.job.id,projectId:id});return video
}
export async function reviseVideo(id:string,versionId:string,revision:number,segmentIds:string[],instruction:string,mode:'visual'|'voice'='visual'){
 const video=await request<VideoVersion>('POST',base(id)+'/'+encodeURIComponent(versionId)+'/revisions',{revision,idempotency_key:crypto.randomUUID(),segment_ids:segmentIds,instruction,mode})
 addPendingOutlineNotification({jobId:video.job.id,projectId:id});return video
}

export async function exportVideo(id:string,versionId:string){
 const job=await request<Job>('POST',base(id)+'/'+encodeURIComponent(versionId)+'/export',{idempotency_key:crypto.randomUUID()})
 addPendingOutlineNotification({jobId:job.id,projectId:id});return job
}
