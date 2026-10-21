<script setup lang="ts">
import {computed} from 'vue'
import {segmentReviewState} from '../../utils/outline-review'
import type {Segment,Visual} from '../../api/outline'

const props=defineProps<{segment:Segment;index:number;count:number;disabled?:boolean;selected:boolean;contentChanged?:boolean}>()
const emit=defineEmits<{change:[segment:Segment];move:[direction:number];remove:[];select:[value:boolean];evidence:[id:string]}>()
const kinds:Visual['kind'][]=['插图','数学图形','公式','学科示意图','文字卡']
const reviewNotes=computed(()=>props.segment.review_notes.filter(note=>note.trim()))
const reviewState=computed(()=>segmentReviewState(props.segment,props.contentChanged))
const reviewStatus=computed(()=>{
  if(reviewState.value==='pending')return {label:'待审核',type:'warning' as const,description:'当前内容尚未通过AI审核，请保存后重新审核，再由教师确认。'}
  if(reviewState.value==='failed')return {label:'审核未通过',type:'danger' as const,description:'AI发现当前版本存在必须修改的问题，请教师根据原因修改并重新审核。'}
  return {label:'AI已审核',type:'success' as const,description:'AI已审核当前版本，未发现必须修改的问题；普通建议仍需教师核对；此状态仅针对大纲内容，生成后仍需预览核对画面与配音。'}
})
function update(key:keyof Segment,value:unknown){emit('change',{...props.segment,[key]:value})}
function visual(index:number,key:keyof Visual,value:unknown){update('visuals',props.segment.visuals.map((v,i)=>i===index?{...v,[key]:value}:v))}
</script>

<template>
  <article class="segment">
    <header>
      <el-checkbox :model-value="selected" :disabled="disabled" :aria-label="'选择段落 '+(index+1)" @update:model-value="(v:unknown)=>emit('select',Boolean(v))"/>
      <span class="position">{{String(index+1).padStart(2,'0')}}</span>
      <strong>{{segment.title||'未命名段落'}}</strong>
      <el-tag size="small" disable-transitions :type="reviewStatus.type" :title="reviewStatus.description">{{reviewStatus.label}}</el-tag>
      <span class="duration">预计时长 {{segment.estimated_duration_seconds}} 秒</span>
    </header>
    <el-form label-position="top" :disabled="disabled">
      <div class="pair">
        <el-form-item label="段落标题"><el-input :model-value="segment.title" :aria-label="'段落标题 '+(index+1)" @update:model-value="(v:unknown)=>update('title',v)"/></el-form-item>
        <el-form-item label="内容性质"><el-select :model-value="segment.content_kind" :aria-label="'内容性质 '+(index+1)" @update:model-value="(v:unknown)=>update('content_kind',v)"><el-option label="知识讲解" value="knowledge"/><el-option label="事实陈述" value="fact"/><el-option label="情景演绎" value="reenactment"/></el-select></el-form-item>
      </div>
      <el-form-item label="教学目标"><el-input :model-value="segment.objective" :aria-label="'教学目标 '+(index+1)" @update:model-value="(v:unknown)=>update('objective',v)"/></el-form-item>
      <el-form-item label="完整逐字稿"><el-input type="textarea" :rows="5" :model-value="segment.narration" :aria-label="'逐字稿 '+(index+1)" @update:model-value="(v:unknown)=>update('narration',v)"/></el-form-item>
      <p class="field-label">画面说明</p>
      <p :id="`visual-help-${segment.id}`" class="visual-help">写清展示什么、发生什么变化、希望学生理解什么即可，无需编写分镜或具体秒数。</p>
      <div v-for="(v,i) in segment.visuals" :key="i" class="visual-row">
        <el-select :model-value="v.kind" :aria-label="'画面类型 '+(index+1)+'-'+(i+1)" @update:model-value="(value:unknown)=>visual(i,'kind',value)"><el-option v-for="kind in kinds" :key="kind" :label="kind" :value="kind"/></el-select>
        <el-input :model-value="v.description" type="textarea" :rows="2" :aria-label="'画面描述 '+(index+1)+'-'+(i+1)" :aria-describedby="`visual-help-${segment.id}`" @update:model-value="(value:unknown)=>visual(i,'description',value)"/>
        <el-button text type="danger" :disabled="disabled||segment.visuals.length<=1" @click="update('visuals',segment.visuals.filter((_,n)=>n!==i))">移除</el-button>
      </div>
      <el-button text :disabled="disabled||segment.visuals.length>=12" @click="update('visuals',[...segment.visuals,{kind:'文字卡',description:''}])">添加画面</el-button>
    </el-form>
    <div class="evidence">
      <span>内容依据</span>
      <el-button v-for="(id,i) in segment.evidence_ids" :key="id" text @click="emit('evidence',id)">查看依据 {{i+1}}</el-button>
      <span v-if="!segment.evidence_ids.length" class="ev-muted">未核实出处</span>
    </div>
    <div v-if="reviewState==='failed'" class="review-issues" aria-label="未通过原因"><strong>审核未通过原因</strong><ul><li v-for="(issue,i) in segment.review_issues" :key="i">{{issue}}</li></ul></div>
    <ul v-if="reviewNotes.length" class="review-notes" aria-label="审核提示"><li v-for="(note,i) in reviewNotes" :key="i">{{note}}</li></ul>
    <footer>
      <el-button :disabled="disabled||index===0" @click="emit('move',-1)">上移</el-button>
      <el-button :disabled="disabled||index===count-1" @click="emit('move',1)">下移</el-button>
      <el-button text type="danger" :disabled="disabled||count<=1" @click="emit('remove')">删除段落</el-button>
    </footer>
  </article>
</template>

<style scoped>
.segment{background:var(--ev-color-surface);border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);padding:24px;margin-bottom:20px}
header{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--ev-color-border)}
header strong{font-size:16px;font-weight:600}
.position{display:grid;place-items:center;width:28px;height:28px;border-radius:7px;background:var(--el-color-primary-light-9);color:var(--ev-color-primary);font-variant-numeric:tabular-nums;font-size:12px}
.duration{margin-left:auto;color:var(--ev-color-muted);font-size:12px}
.pair{display:grid;grid-template-columns:2fr 1fr;gap:20px}
.field-label{font-size:14px;margin:0 0 8px}
.visual-help{font-size:13px;line-height:1.7;color:var(--ev-color-muted);margin:0 0 12px}
.visual-row{display:grid;grid-template-columns:130px minmax(0,1fr) auto;gap:10px;margin-bottom:12px}
.evidence{display:flex;align-items:center;flex-wrap:wrap;gap:10px;font-size:13px}
.review-notes{border-left:3px solid var(--ev-color-border);padding:10px 16px 10px 28px;color:var(--ev-color-muted);font-size:13px;line-height:1.8}
.review-issues{border-left:3px solid var(--ev-color-danger);padding:12px 16px;color:var(--ev-color-danger);font-size:13px;line-height:1.8}.review-issues ul{margin:6px 0 0;padding-left:20px}
footer{display:flex;justify-content:flex-end;gap:8px;border-top:1px solid var(--ev-color-border);padding-top:14px;margin-top:18px}
footer .el-button{margin:0}
@media(max-width:600px){.segment{padding:16px}.pair{grid-template-columns:1fr;gap:0}.visual-row{grid-template-columns:1fr}.duration{margin-left:0;width:100%}}
</style>
