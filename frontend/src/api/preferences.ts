import {request} from './http'
export type Preference={id:string;category:string;value:string;reason?:string}
export type Preferences={enabled:boolean;options:Record<string,string[]>;items:Preference[];suggestions:Preference[]}
export const getPreferences=()=>request<Preferences>('GET','/api/preferences')
export const addPreference=(category:string,value:string)=>request<Preference>('POST','/api/preferences',{category,value})
export const editPreference=(id:string,category:string,value:string)=>request<Preference>('PATCH','/api/preferences/'+id,{category,value})
export const deletePreference=(id:string)=>request<void>('DELETE','/api/preferences/'+id)
export const acceptPreference=(id:string)=>request<Preference>('POST','/api/preferences/suggestions/'+id+'/accept')
