import {request} from './http'
export type CreditBalance={balance:number;reserved:number;available:number;video_cost:number;ppt_cost:number;total_credited:number;total_spent:number}
export type CreditTransaction={id:string;kind:'redemption'|'video_generation'|'ppt_generation';description:string;amount:number;balance_after:number;created_at:string}
export type CreditCode={id:string;user_id:string;amount:number;suffix:string;status:'available'|'redeemed'|'revoked'|'expired';created_at:string;expires_at:string;redeemed_at:string|null}
export type IssuedCode=CreditCode&{code:string}
export const getCreditBalance=()=>request<CreditBalance>('GET','/api/account/credits')
export const redeemCreditCode=(code:string)=>request<CreditBalance>('POST','/api/account/credits/redeem',{code})
export function getCreditTransactions(page=1,type='all'){return request<{items:CreditTransaction[];total:number}>('GET',`/api/account/credits/transactions?page=${page}&type=${encodeURIComponent(type)}`)}
export const listCreditCodes=(userId:string,page=1)=>request<{items:CreditCode[];total:number}>('GET',`/api/admin/users/${encodeURIComponent(userId)}/credit-codes?page=${page}`)
export const issueCreditCode=(userId:string,amount:number,expiresInDays:number)=>request<IssuedCode>('POST',`/api/admin/users/${encodeURIComponent(userId)}/credit-codes`,{amount,expires_in_days:expiresInDays})
export const revokeCreditCode=(id:string)=>request<CreditCode>('POST',`/api/admin/credit-codes/${encodeURIComponent(id)}/revoke`)
export function notifyCreditsChanged(){window.dispatchEvent(new Event('edu-video:credits-changed'))}
export const formatPoints=(value:number)=>new Intl.NumberFormat('zh-CN').format(value)
export function formatCreditTime(iso:string){return new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(iso))}
