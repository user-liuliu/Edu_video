from uuid import uuid4
from langgraph.checkpoint.memory import InMemorySaver
from app.outline.graph import build_outline_graph
from app.outline.schemas import OutlineData

async def test_generate_review_and_interrupt_without_secret_checkpoint():
    calls=[]
    async def generate(state):
        calls.append('generate')
        return {'segments':[{'id':str(uuid4()),'title':'开场','objective':'理解概念','narration':'同学们好','visuals':[{'kind':'文字卡','description':'标题'}],'evidence_ids':[],'content_kind':'knowledge'}]}
    async def review(state):
        calls.append('review')
        return {state['outline']['segments'][0]['id']:{'passed':True,'issues':[],'notes':['请核对教材']}}
    saver=InMemorySaver()
    graph=build_outline_graph(saver,generate,review)
    config={'configurable':{'thread_id':'owner:project:job'}}
    result=await graph.ainvoke({'prompt':'数学','evidence':[],'form_values':{},'operation':'generate'},config)
    assert calls==['generate','review']
    assert result['__interrupt__']
    assert OutlineData.model_validate(result['outline']).segments[0].reviewed_revision==1
    assert 'api_key' not in str(saver.storage)
    # A newly built graph can resume the persisted confirmation point.
    from langgraph.types import Command
    resumed=await build_outline_graph(saver,generate,review).ainvoke(Command(resume=True),config)
    assert resumed['confirmed'] is True
