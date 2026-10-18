import hashlib
import json
from .tavily import search

async def search_cached(query, config, client, redis, *, allow_web_search):
    if not allow_web_search: return []
    digest=hashlib.sha256((config.base_url+'\0'+config.api_key+'\0'+query).encode()).hexdigest()
    key='search:cache:'+digest
    cached=await redis.get(key)
    if cached: return json.loads(cached)
    token=hashlib.sha256(__import__('os').urandom(32)).hexdigest()
    slot=None
    for n in range(3):
        candidate=f'search:slot:{n}'
        if await redis.set(candidate,token,nx=True,ex=40): slot=candidate; break
    if slot is None: raise ValueError('搜索服务繁忙，请稍后重试')
    try:
        result=await search(query,config,client)
        await redis.set(key,json.dumps(result,ensure_ascii=False),ex=300)
        return result
    finally:
        await redis.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,slot,token)
