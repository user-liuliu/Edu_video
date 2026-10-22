import {flushPromises,mount,type VueWrapper} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import {createPinia,setActivePinia} from 'pinia'
import {createMemoryHistory,createRouter} from 'vue-router'
import {beforeEach,afterEach,expect,test,vi} from 'vitest'

let wrappers:VueWrapper[]=[]
let balance={balance:120,reserved:10,available:110,video_cost:10,total_credited:130,total_spent:10}
let failBalance=false,failRedeem=false,failRecords=false
let requests:{url:string;method:string;body:any}[]=[]
let entries:any[]=[]
let codes:any[]=[]
const issued={id:'c1',user_id:'u1',amount:200,suffix:'ABCD',status:'available',created_at:'2026-10-22T08:00:00Z',expires_at:'2026-11-21T08:00:00Z',redeemed_at:null,code:'EDU-ABCDEF-GHJKLM-NPQRST-UVWXYZ'}
beforeEach(()=>{
 setActivePinia(createPinia());requests=[];entries=[];codes=[];failBalance=false;failRedeem=false;failRecords=false
 balance={balance:120,reserved:10,available:110,video_cost:10,total_credited:130,total_spent:10}
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;requests.push({url,method,body})
  if(url==='/api/account/credits/redeem'){
   if(failRedeem)return new Response(JSON.stringify({detail:{code:'invalid_credit_code',message:'兑换码无效或已过期'}}),{status:400})
   balance={...balance,balance:320,available:310,total_credited:330};entries=[{id:'t1',kind:'redemption',description:'兑换码充值 · 尾号 ABCD',amount:200,balance_after:320,created_at:'2026-10-22T08:00:00Z'}];return new Response(JSON.stringify(balance))
  }
  if(url==='/api/account/credits')return failBalance?new Response(null,{status:503}):new Response(JSON.stringify(balance))
  if(url.startsWith('/api/account/credits/transactions'))return failRecords?new Response(null,{status:503}):new Response(JSON.stringify({items:entries,total:entries.length}))
  if(url==='/api/admin/users/u1/credit-codes'&&method==='POST'){codes=[issued];return new Response(JSON.stringify(issued),{status:201})}
  if(url.startsWith('/api/admin/users/u1/credit-codes'))return new Response(JSON.stringify({items:codes,total:codes.length}))
  if(url==='/api/admin/credit-codes/c1/revoke'){codes=[{...issued,status:'revoked'}];return new Response(JSON.stringify(codes[0]))}
  throw new Error('Unexpected URL '+url)
 }))
})
afterEach(()=>{wrappers.forEach(w=>w.unmount());wrappers=[];vi.unstubAllGlobals();document.body.innerHTML=''})
async function balancePage(){
 const View=(await import('../src/views/workbench/BalanceView.vue')).default
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/account/balance',component:View}]});await router.push('/account/balance')
 const w=mount(View,{global:{plugins:[ElementPlus,router]},attachTo:document.body});wrappers.push(w);await flushPromises();return w
}
async function click(w:VueWrapper,text:string){const b=w.findAll('button').find(x=>x.text()===text);expect(b).toBeDefined();await b!.trigger('click');await flushPromises()}
test('balance shows available and reserved points then redemption refreshes balance and real ledger',async()=>{
 const w=await balancePage();expect(w.get('[data-testid=available-balance]').text()).toContain('110');expect(w.text()).toContain('生成中预留');expect(w.text()).toContain('10 积分')
 await w.get('#credit-code').setValue(issued.code);await w.get('form').trigger('submit');await flushPromises()
 expect(requests.find(r=>r.method==='POST')?.body).toEqual({code:issued.code})
 expect(w.get('[data-testid=available-balance]').text()).toContain('310');expect(w.text()).toContain('+200');expect(w.text()).toContain('ABCD');expect(w.text()).toContain('兑换成功')
})
test('invalid code stays editable and does not claim success or change displayed balance',async()=>{
 failRedeem=true;const w=await balancePage();await w.get('#credit-code').setValue('INVALID');await w.get('form').trigger('submit');await flushPromises()
 expect(w.text()).toContain('兑换码无效');expect(w.get('[data-testid=available-balance]').text()).toContain('110');expect(w.text()).not.toContain('兑换成功');expect((w.get('#credit-code').element as HTMLInputElement).value).toBe('INVALID')
})
test('balance failure shows explicit retry instead of false zero',async()=>{
 failBalance=true;const w=await balancePage();expect(w.find('[data-testid=available-balance]').exists()).toBe(false);expect(w.text()).toContain('余额加载失败')
 failBalance=false;await click(w,'重新加载');expect(w.get('[data-testid=available-balance]').text()).toContain('110')
})
test('history filters request expenses and failed history has its own retry',async()=>{
 const w=await balancePage();await click(w,'支出');expect(requests.some(r=>r.url.includes('type=expense'))).toBe(true)
 failRecords=true;await click(w,'收入');expect(w.text()).toContain('记录加载失败');failRecords=false;await click(w,'重试记录');expect(w.text()).toContain('暂无积分记录')
})
test('admin generates code for selected user with chosen amount and can revoke it',async()=>{
 const View=(await import('../src/views/admin/UserCreditCodes.vue')).default
 const w=mount(View,{props:{user:{id:'u1',username:'teacher1'}},global:{plugins:[ElementPlus]},attachTo:document.body});wrappers.push(w);await flushPromises()
 await w.get('#code-amount').setValue('200');await w.get('form').trigger('submit');await flushPromises()
 expect(requests.find(r=>r.method==='POST')?.url).toBe('/api/admin/users/u1/credit-codes');expect(requests.find(r=>r.method==='POST')?.body.amount).toBe(200)
 expect(w.text()).toContain(issued.code);expect(w.text()).toContain('teacher1');await click(w,'停用');expect(w.text()).toContain('已停用')
})


test('sidebar balance refreshes after redemption and remains the selected entry',async()=>{
 const {useAuthStore}=await import('../src/stores/auth')
 const {notifyCreditsChanged}=await import('../src/api/credits')
 const View=(await import('../src/components/CreditBalanceLink.vue')).default
 const pinia=createPinia();setActivePinia(pinia)
 useAuthStore().user={id:'u1',username:'teacher1',role:'teacher',status:'active'}
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/account/balance',component:{template:'<div />'}}]})
 await router.push('/account/balance')
 const w=mount(View,{global:{plugins:[pinia,router]}});wrappers.push(w);await flushPromises()
 expect(w.attributes('aria-label')).toContain('110')
 expect(w.attributes('aria-current')).toBe('page')
 balance={...balance,available:210,balance:220}
 notifyCreditsChanged();await flushPromises()
 expect(w.attributes('aria-label')).toContain('210')
 failBalance=true;notifyCreditsChanged();await flushPromises()
 expect(w.text()).toContain('点击查看余额');expect(w.find('.wallet-points').exists()).toBe(false)
})
