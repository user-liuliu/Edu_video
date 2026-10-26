import {onBeforeUnmount,ref} from 'vue'
import {notifyCreditsChanged} from '../api/credits'
import {getPpt,type PptProject} from '../api/presentations'
import {errorText} from '../api/http'
import {addPendingOutlineNotification} from '../utils/outline-job-notification'
export function usePptProject(){
  const project=ref<PptProject>(),error=ref(''),loading=ref(true),connectionError=ref(false)
  let timer:ReturnType<typeof setTimeout>|undefined,disposed=false,inflight=false
  async function load(id:string){if(disposed||inflight)return;inflight=true;clearTimeout(timer);try{const previous=project.value?.job;project.value=await getPpt(id);const job=project.value.job;if(previous&&['render','revise'].includes(previous.kind)&&['pending','running'].includes(previous.status)&&job&&!['pending','running'].includes(job.status))notifyCreditsChanged();if(job&&['pending','running'].includes(job.status)&&['outline','render','revise'].includes(job.kind))addPendingOutlineNotification({jobId:job.id,projectId:id,target:'ppt'});error.value='';connectionError.value=false}catch(e){error.value=errorText(e);connectionError.value=true}finally{inflight=false;loading.value=false;if(!disposed&&project.value?.job&&['pending','running'].includes(project.value.job.status))timer=setTimeout(()=>load(id),2000)}}
  onBeforeUnmount(()=>{disposed=true;clearTimeout(timer)})
  return {project,error,loading,connectionError,load}
}
