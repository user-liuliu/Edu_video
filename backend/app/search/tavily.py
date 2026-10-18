"""Tavily Search API. Never return provider error bodies or credentials."""
from urllib.parse import urlsplit
import httpx

class SearchError(ValueError):
    pass

def search_url(base_url):
    base = base_url.rstrip('/')
    return base if urlsplit(base).path.rstrip('/').endswith('/search') else base+'/search'

async def search(query, config, client):
    try:
        response = await client.post(search_url(config.base_url),
            headers={'Authorization':'Bearer '+config.api_key},
            json={'query':query[:500],'search_depth':'basic','max_results':5,'include_answer':False,'include_raw_content':False},timeout=30)
        if response.status_code in (401,403): raise SearchError('搜索鉴权失败，请管理员检查 Tavily Key 和权限')
        if response.status_code in (402,432,433): raise SearchError('Tavily 搜索额度不足，请管理员检查账户')
        if response.status_code == 429: raise SearchError('搜索请求过于频繁，请稍后重试')
        if not response.is_success: raise SearchError('搜索服务暂不可用，请稍后重试')
        body = response.json()
        if not isinstance(body,dict) or not isinstance(body.get('results'),list): raise SearchError('搜索服务返回了无效结果')
        hits=[]
        for item in body['results'][:5]:
            if not isinstance(item,dict): raise SearchError('搜索服务返回了无效结果')
            url=item.get('url',''); parsed=urlsplit(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username: continue
            if not isinstance(item.get('title'),str) or not isinstance(item.get('content'),str): continue
            hits.append({'title':item['title'][:300],'url':url[:2000],'excerpt':item['content'][:4000],
                         'published_at':item.get('published_date') if isinstance(item.get('published_date'),str) else None})
        return hits
    except SearchError: raise
    except httpx.TimeoutException: raise SearchError('搜索请求超时，请重试') from None
    except (httpx.HTTPError,ValueError,TypeError): raise SearchError('搜索连接失败或响应格式无效，请重试') from None
