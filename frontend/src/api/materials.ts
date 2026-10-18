import {request} from './http'
export type Material={id:string;filename:string;size:number;status:string;error_message:string|null;job_id?:string;parse_warnings?:{location:string;message:string}[]}
const base=(id:string)=>'/api/projects/'+encodeURIComponent(id)+'/materials'
export const listMaterials=(id:string)=>request<Material[]>('GET',base(id))
export function uploadMaterial(id:string,file:File,deferParse=false){const form=new FormData();form.append('file',file);return request<Material>('POST',base(id)+(deferParse?'?defer_parse=true':''),form)}
export const prepareMaterials=(id:string)=>request<{job_ids:string[]}>('POST',base(id)+'/prepare')
export const deleteMaterial=(id:string,mid:string)=>request<void>('DELETE',base(id)+'/'+encodeURIComponent(mid))
export const retryMaterial=(id:string,mid:string)=>request<{job_id:string}>('POST',base(id)+'/'+encodeURIComponent(mid)+'/retry')
