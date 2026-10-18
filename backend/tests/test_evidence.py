import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from app.outline.evidence import enforce_evidence,source_grade
from app.search.service import search_cached

async def test_disabled_search_never_reads_cache_or_calls_provider():
    redis=AsyncMock();http=AsyncMock()
    assert await search_cached('数学',None,http,redis,allow_web_search=False)==[]
    redis.get.assert_not_called();http.post.assert_not_called()

def test_invented_evidence_rejected_and_forum_is_not_proof():
    eid=str(uuid4())
    data={'segments':[{'evidence_ids':[eid],'content_kind':'fact','review_notes':[]}]}
    with pytest.raises(ValueError): enforce_evidence(data,[])
    result=enforce_evidence(data,[{'id':eid,'source_grade':'discussion'}])
    assert any('不能独立佐证' in n for n in result['segments'][0]['review_notes'])
    assert source_grade('https://fakewikipedia.org/a')=='general'
    assert source_grade('https://en.wikipedia.org/a')=='secondary'
