from collections import Counter
from uuid import uuid5,NAMESPACE_URL
from sqlalchemy import select
from app.models import Preference,OutlineJob

OPTIONS={
    'teaching':['先举例再讲概念','先讲概念再练习','多用生活实例','增加互动提问','分步骤讲解'],
    'expression':['简洁清晰','生动有趣','严谨规范','循序渐进'],
    'visual':['简洁板书','学科示意图优先','插图辅助理解','文字卡总结'],
    'settings':['短时精讲','保留开场与小结','增加练习环节'],
}

async def suggestions(db,owner_id):
    instructions=(await db.scalars(select(OutlineJob.payload).where(OutlineJob.owner_id==owner_id,OutlineJob.kind=='rewrite',OutlineJob.status=='succeeded').order_by(OutlineJob.created_at.desc()).limit(100))).all()
    counts=Counter()
    for payload in instructions:
        instruction=payload.get('instruction','')
        for category,values in OPTIONS.items():
            for value in values:
                if value in instruction: counts[(category,value)]+=1
    accepted={(p.category,p.value) for p in (await db.scalars(select(Preference).where(Preference.owner_id==owner_id,Preference.accepted.is_(True)))).all()}
    return [{'id':str(uuid5(NAMESPACE_URL,f'{owner_id}:{category}:{value}')),'category':category,'value':value,'reason':f'最近有 {count} 次已完成改写明确要求“{value}”'}
            for (category,value),count in counts.items() if count>=2 and (category,value) not in accepted]

async def sync_store(db,store,owner_id):
    namespace=('users',str(owner_id),'preferences')
    rows=(await db.scalars(select(Preference).where(Preference.owner_id==owner_id,Preference.accepted.is_(True)))).all()
    wanted={str(p.id):{'category':p.category,'value':p.value} for p in rows}
    for item in await store.asearch(namespace,limit=100):
        if item.key not in wanted: await store.adelete(namespace,item.key)
    for key,value in wanted.items(): await store.aput(namespace,key,value)
    return list(wanted.values())
