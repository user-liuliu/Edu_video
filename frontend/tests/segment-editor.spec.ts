import {mount} from '@vue/test-utils'
import ElementPlus from 'element-plus'
import {expect,test} from 'vitest'
import SegmentEditor from '../src/components/workbench/SegmentEditor.vue'
import type {Segment} from '../src/api/outline'

const segment:Segment={id:'s1',position:0,title:'电路',objective:'理解串联',narration:'同学们好',visuals:[{kind:'文字卡',description:'串联电路'}],evidence_ids:[],content_kind:'knowledge',review_notes:[],review_passed:true,review_issues:[],estimated_duration_seconds:3,content_revision:2,reviewed_revision:2}

test.each([
 {name:'reviewed with a factual concern',revision:2,notes:['电流关系表述错误，请核对'],label:'AI已审核',type:'success'},
 {name:'reviewed without an issue',revision:2,notes:[],label:'AI已审核',type:'success'},
 {name:'reviewed with whitespace only',revision:2,notes:['  ','\t'],label:'AI已审核',type:'success'},
 {name:'changed since review even with old notes',revision:1,notes:['旧稿的提示'],label:'待审核',type:'warning'},
 {name:'not yet reviewed',revision:0,notes:[],label:'待审核',type:'warning'},
])('$name has an accurate review label',({revision,notes,label,type})=>{
 const w=mount(SegmentEditor,{props:{segment:{...segment,reviewed_revision:revision,review_notes:notes},index:0,count:1,selected:false},global:{plugins:[ElementPlus]}})
 try{
  const tag=w.get('header .el-tag')
  expect(tag.text()).toBe(label)
  expect(tag.classes()).toContain(`el-tag--${type}`)
  if(notes.some(n=>n.trim()))expect(w.get('[aria-label="审核提示"]').text()).toContain(notes[0])
  expect(tag.attributes('title')).toContain('教师')
 }finally{w.unmount()}
})

test('review result updates after a new review and old concerns remain visible until then',async()=>{
 const w=mount(SegmentEditor,{props:{segment:{...segment,review_notes:['请核对公式']},index:0,count:1,selected:false},global:{plugins:[ElementPlus]}})
 try{
  expect(w.get('header .el-tag').text()).toBe('AI已审核')
  await w.setProps({segment:{...segment,content_revision:3,review_notes:['请核对公式']}})
  expect(w.get('header .el-tag').text()).toBe('待审核')
  expect(w.get('[aria-label="审核提示"]').text()).toContain('请核对公式')
  await w.setProps({segment:{...segment,content_revision:3,reviewed_revision:3,review_notes:[]}})
  expect(w.get('header .el-tag').text()).toBe('AI已审核')
  expect(w.find('[aria-label="审核提示"]').exists()).toBe(false)
 }finally{w.unmount()}
})


test('explicit rejection shows red reasons and an unsaved edit overrides it with pending',async()=>{
 const w=mount(SegmentEditor,{props:{segment:{...segment,review_passed:false,review_issues:['公式错误'],review_notes:['建议补例子']},index:0,count:1,selected:false},global:{plugins:[ElementPlus]}})
 try{
  expect(w.get('header .el-tag').text()).toBe('审核未通过')
  expect(w.get('header .el-tag').classes()).toContain('el-tag--danger')
  expect(w.get('[aria-label="未通过原因"]').text()).toContain('公式错误')
  expect(w.get('[aria-label="审核提示"]').text()).toContain('建议补例子')
  await w.setProps({contentChanged:true})
  expect(w.get('header .el-tag').text()).toBe('待审核')
  expect(w.get('header .el-tag').classes()).toContain('el-tag--warning')
  expect(w.find('[aria-label="未通过原因"]').exists()).toBe(false)
 }finally{w.unmount()}
})

test('legacy review revision without explicit verdict stays pending',()=>{
 const w=mount(SegmentEditor,{props:{segment:{...segment,review_passed:undefined},index:0,count:1,selected:false},global:{plugins:[ElementPlus]}})
 try{expect(w.get('header .el-tag').text()).toBe('待审核')}finally{w.unmount()}
})
