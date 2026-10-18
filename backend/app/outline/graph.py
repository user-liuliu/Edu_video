from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from .schemas import OutlineData
from .review import validate_verdict
from .evidence import enforce_evidence
from .policy import apply_duration_warning

class OutlineState(TypedDict,total=False):
    prompt: str
    form_values: dict
    generation_params: dict
    preferences: list
    evidence: list
    outline: dict
    operation: str
    segment_ids: list[str]
    instruction: str
    confirmed: bool

def build_outline_graph(checkpointer,generate,review,store=None):
    async def draft(state):
        if state.get('operation')=='review': return {}
        result=await generate(state)
        data=OutlineData.model_validate(result).model_dump(mode='json')
        old={s['id']:s for s in state.get('outline',{}).get('segments',[])}
        if state.get('operation')=='rewrite':
            ids=set(state['segment_ids']); generated={s['id']:s for s in data['segments']}
            if set(generated)!=ids: raise ValueError('改写结果的段落与所选段落不一致')
            data={'segments':[generated[s['id']] if s['id'] in ids else s for s in state['outline']['segments']]}
        for n,s in enumerate(data['segments']):
            s['position']=n
            if state.get('operation')=='rewrite' and s['id'] not in state['segment_ids']: continue
            s['content_revision']=old.get(s['id'],{}).get('content_revision',0)+1
            s['reviewed_revision']=0; s['review_notes']=[]; s['review_passed']=None; s['review_issues']=[]
            import re
            words=len(re.findall(r'[A-Za-z]+',s['narration'])); cjk=len(re.findall(r'[一-鿿]',s['narration']))
            s['estimated_duration_seconds']=max(1,round(cjk/3.5+words/2.2))
        return {'outline':enforce_evidence(data,state.get('evidence',[]))}

    async def audit(state):
        results=await review(state)
        data={**state['outline'], **OutlineData.model_validate(state['outline']).model_dump(mode='json')}
        selected=set(state.get('segment_ids',[]))
        for s in data['segments']:
            if selected and s['id'] not in selected: continue
            verdict=validate_verdict(results.get(s['id']))
            s['review_passed']=verdict['passed']
            s['review_issues']=verdict['issues']
            s['review_notes']=verdict['notes']
            s['reviewed_revision']=s['content_revision']
            enforce_evidence({'segments':[s]},state.get('evidence',[]))
        data=apply_duration_warning(data,state.get('form_values',{}),state.get('generation_params'))
        return {'outline':data}


    def wait_for_teacher(state):
        accepted=interrupt({'stage':'等待教师确认','message':'请检查并确认已保存的大纲'})
        return {'confirmed':bool(accepted)}

    graph=StateGraph(OutlineState)
    graph.add_node('draft',draft);graph.add_node('audit',audit);graph.add_node('teacher_confirmation',wait_for_teacher)
    graph.add_edge(START,'draft');graph.add_edge('draft','audit');graph.add_edge('audit','teacher_confirmation');graph.add_edge('teacher_confirmation',END)
    return graph.compile(checkpointer=checkpointer,store=store)
