type Mode='video'|'ppt'
type Entry={path:string;data:Record<string,unknown>}
const entries=new Map<Mode,Entry>()
let epoch=0
export const creationEpoch=()=>epoch
export function rememberCreation(mode:Mode,path:string,data:Record<string,unknown>,ownerEpoch=epoch){if(ownerEpoch!==epoch)return;entries.set(mode,{path,data:copy(data)})}
function copy<T>(value:T):T{if(value instanceof File)return value;if(Array.isArray(value))return value.map(copy) as T;if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,copy(v)])) as T;return value}
export function restoreCreation(mode:Mode,path:string){const e=entries.get(mode);return e?.path===path?copy(e.data):undefined}
export function creationPath(mode:Mode){return entries.get(mode)?.path??(mode==='ppt'?'/presentations/new':'/projects/new')}
export function clearCreationMemory(){entries.clear();epoch++}
