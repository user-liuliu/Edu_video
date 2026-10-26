import { request } from './http'
import type { FieldKey, FieldOption } from './admin'
export type PublicField = { key: FieldKey; label: string; default: string | boolean | null; options: FieldOption[]; default_by_subject: Record<string,string> }
export type FormConfig = { system_available: boolean; form_version: string; fields: PublicField[] }
export type Project = { id:string; title:string; prompt:string; form_values:Record<string,unknown>; status:string; revision:number; needs_regeneration:boolean; download_url?:string|null; created_at:string; updated_at:string }
export type ProjectInput = { prompt:string; title?:string; form_values:Record<string,unknown>; form_version?:string; revision?:number }
export const getFormConfig = () => request<FormConfig>('GET','/api/config/form')
export const getProject = (id:string) => request<Project>('GET','/api/projects/'+encodeURIComponent(id))
export const listProjects = (scope='completed',page=1) => request<{items:Project[];total:number}>('GET','/api/projects?scope='+scope+'&page='+page)
export const saveProject = (body:ProjectInput,id?:string) => request<Project>(id?'PATCH':'POST','/api/projects'+(id?'/'+encodeURIComponent(id):''),body)
export const deleteProject = (p:Project) => request<void>('DELETE','/api/projects/'+p.id+'?revision='+p.revision)
