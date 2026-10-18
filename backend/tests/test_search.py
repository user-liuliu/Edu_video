import json
import httpx
import pytest
from app.model_configs.schemas import ResolvedConfig
from app.purposes import Purpose
from app.search.tavily import search, SearchError

def cfg(): return ResolvedConfig(Purpose.web_search,'https://api.tavily.com','test-secret','',{})

async def test_tavily_protocol_and_no_invented_date(respx_mock):
    route=respx_mock.post('https://api.tavily.com/search').respond(200,json={'results':[{'title':'教材','url':'https://edu.gov.cn/a','content':'二次函数'}]})
    async with httpx.AsyncClient() as client:
        hits=await search('二次函数',cfg(),client)
    assert route.calls.last.request.headers['Authorization']=='Bearer test-secret'
    assert json.loads(route.calls.last.request.content)['query']=='二次函数'
    assert hits[0]['published_at'] is None
    assert hits[0]['url']=='https://edu.gov.cn/a'

@pytest.mark.parametrize('status',[401,403,429,432,500])
async def test_tavily_errors_safe_and_explicit(respx_mock,status):
    respx_mock.post('https://api.tavily.com/search').respond(status,text='bad test-secret')
    async with httpx.AsyncClient() as client:
        with pytest.raises(SearchError) as error: await search('历史',cfg(),client)
    assert 'test-secret' not in str(error.value)
    assert any('一'<=c<='鿿' for c in str(error.value))

async def test_empty_results_are_success(respx_mock):
    respx_mock.post('https://api.tavily.com/search').respond(200,json={'results':[]})
    async with httpx.AsyncClient() as client: assert await search('历史',cfg(),client)==[]
