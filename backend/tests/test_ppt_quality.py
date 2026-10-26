import pytest
from app.presentations.quality import parse_review, audit_pages, QualityError


def test_parse_review_accepts_only_explicit_pass_or_bounded_issues():
    assert parse_review({'status':'passed','issues':[]}) == []
    issues=parse_review({'status':'needs_attention','issues':[{'category':'readability','message':'文字遮挡','repair':'移开标签'}]})
    assert issues[0]['message']=='文字遮挡'
    with pytest.raises(QualityError): parse_review({'status':'passed','issues':[{'category':'teaching','message':'错','repair':'改'}]})
    with pytest.raises(QualityError): parse_review({'status':'passed','issues':[],'score':100})


@pytest.mark.asyncio
async def test_audit_repairs_each_selected_page_at_most_twice_and_keeps_unselected():
    pages=[{'id':'a','svg':'a'},{'id':'b','svg':'b'}]
    renders=[];reviews=[]
    async def render(candidate):
        renders.append([p['svg'] for p in candidate]); return [b'a',b'b']
    async def review(page,image):
        reviews.append(page['id'])
        if page['id']=='a' and page['svg']!='fixed': return [{'category':'readability','message':'拥挤','repair':'留白'}]
        return []
    async def repair(page,issues): return {**page,'svg':'fixed'}
    audited,warnings=await audit_pages(pages,selected_ids={'a'},render=render,review=review,repair=repair)
    assert audited[0]['svg']=='fixed' and audited[0]['review']['status']=='passed'
    assert audited[1] is pages[1]
    assert len(renders)==2 and reviews==['a','a'] and warnings==[]


@pytest.mark.asyncio
async def test_audit_blocks_publication_after_two_unsuccessful_repairs():
    pages=[{'id':'a','svg':'a'}];repairs=[]
    async def render(candidate): return [b'image']
    async def review(page,image): return [{'category':'readability','message':'元素重叠','repair':'分开'}]
    async def repair(page,issues): repairs.append(page['svg']); return {**page,'svg':page['svg']+'x'}
    snapshots=[]
    async def save(page):snapshots.append(page)
    with pytest.raises(QualityError,match='未通过自动审核'):
        await audit_pages(pages,selected_ids={'a'},render=render,review=review,repair=repair,on_update=save)
    assert repairs==['a','ax']
    assert snapshots[-1]['review']['status']=='needs_attention'
    assert snapshots[-1]['review']['repairs']==2
    assert pages==[{'id':'a','svg':'a'}]


@pytest.mark.parametrize('result',[{}, {'status':True,'issues':[]}, {'status':'needs_attention','issues':[]}, {'status':'passed','issues':'none'}, {'status':'needs_attention','issues':[{'category':'unknown','message':'x','repair':'x'}]}])
def test_malformed_review_never_passes(result):
    with pytest.raises(QualityError): parse_review(result)


@pytest.mark.asyncio
async def test_review_error_does_not_mutate_published_pages():
    pages=[{'id':'a','svg':'original'}]
    async def render(candidate): return [b'image']
    async def review(page,image): raise QualityError('审核模型连接失败')
    async def repair(page,issues): raise AssertionError('not called')
    with pytest.raises(QualityError):
        await audit_pages(pages,selected_ids={'a'},render=render,review=review,repair=repair)
    assert pages==[{'id':'a','svg':'original'}]


@pytest.mark.asyncio
async def test_resume_budget_is_bounded_and_stale_pass_is_not_trusted():
    pages=[{'id':'a','svg':'replacement','review':{'status':'passed','repairs':2,'content_sha256':'stale','issues':[]}}]
    async def render(candidate): return [b'new-image']
    async def review(page,image): return [{'category':'teaching','message':'遮光区不应变蓝','repair':'修正颜色'}]
    async def repair(page,issues): raise AssertionError('budget already exhausted')
    with pytest.raises(QualityError,match='未通过自动审核'):
        await audit_pages(pages,selected_ids={'a'},render=render,review=review,repair=repair)


def test_native_pptx_is_rendered_to_readable_page_images():
    from app.presentations.quality import render_review_images
    from app.presentations.master_runtime import compile_deck, VERSION
    from tests.test_ppt_master_runtime import sample_svg
    from PIL import Image
    from io import BytesIO
    deck=compile_deck([{'id':'one','title':'审核测试','content':'测试植物叶片','renderer':VERSION,'design':{'visual_brief':'叶片与光线','composition':'图文并排'},'svg':sample_svg()}],'审核测试',{})
    images=render_review_images(deck,1)
    assert len(images)==1
    with Image.open(BytesIO(images[0])) as image:
        assert image.size==(1280,720)
        assert image.convert('RGB').getextrema()!=((255,255),(255,255),(255,255))



@pytest.mark.parametrize('review',[None,{'status':'pending','issues':[]},{'status':'needs_attention','issues':[]},{'status':'passed','issues':[{'message':'仍有问题'}]}])
def test_publication_rejects_missing_incomplete_or_contradictory_review(review):
    from app.presentations.quality import require_approved_pages
    page={'id':'a','svg':'content'}
    if review is not None:page['review']=review
    with pytest.raises(QualityError):require_approved_pages([page])


def test_publication_requires_review_for_exact_page_content():
    from app.presentations.quality import require_approved_pages,content_digest,VERSION
    page={'id':'a','svg':'reviewed'}
    page['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':content_digest(page),'image_sha256':'f'*64}
    require_approved_pages([page])
    page['svg']='changed after review'
    with pytest.raises(QualityError):require_approved_pages([page])


async def test_audit_simplified_rebuild_is_reviewed_after_two_failed_repairs():
    snapshots=[];seen=[]
    async def render(pages):return [p['svg'].encode() for p in pages]
    async def review(page,image):
        seen.append(image)
        return [] if image==b'simple' else [{'category':'readability','message':'重叠','repair':'改成简洁布局'}]
    async def repair(page,issues):return {**page,'svg':'still-bad'}
    async def rebuild(page,issues):return {**page,'svg':'simple'}
    async def save(page):snapshots.append(page)
    pages,warnings=await audit_pages([{'id':'a','svg':'bad'}],selected_ids={'a'},render=render,review=review,repair=repair,rebuild=rebuild,on_update=save,allow_partial=True)
    assert pages[0]['svg']=='simple' and pages[0]['review']['status']=='passed' and not warnings
    assert pages[0]['review']['repairs']==2 and pages[0]['review']['rebuilds']==1
    assert seen==[b'bad',b'still-bad',b'still-bad',b'simple']
    assert any(p['review'].get('rebuilds')==1 and p['svg']!='simple' for p in snapshots)


async def test_audit_repair_exception_falls_back_and_does_not_approve_without_review():
    async def render(pages):return [p['svg'].encode() for p in pages]
    async def review(page,image):return [{'category':'teaching','message':'概念有误','repair':'纠正后复查'}]
    async def repair(page,issues):raise ValueError('不支持的属性')
    async def rebuild(page,issues):return {**page,'svg':'rebuilt'}
    pages,warnings=await audit_pages([{'id':'a','svg':'bad'}],selected_ids={'a'},render=render,review=review,repair=repair,rebuild=rebuild,allow_partial=True)
    assert pages[0]['review']['status']=='needs_attention' and warnings
    assert pages[0]['review']['rebuilds']==1


async def test_resumed_rebuild_budget_cannot_be_reset():
    async def render(pages):return [b'bad']
    async def review(page,image):return [{'category':'readability','message':'重叠','repair':'布局'}]
    async def forbidden(*args):raise AssertionError('exhausted budget must not call model')
    page={'id':'a','svg':'bad','review':{'status':'pending','repairs':2,'rebuilds':1}}
    result,_=await audit_pages([page],selected_ids={'a'},render=render,review=review,repair=forbidden,rebuild=forbidden,allow_partial=True)
    assert result[0]['review']['status']=='needs_attention'


async def test_exporter_failure_is_feedback_for_model_repair_then_review():
    class ExportError(ValueError):pass
    feedback=[];reviewed=[]
    async def render(pages):
        if pages[0]['svg']=='unsupported':raise ExportError('不支持的曲线属性')
        return [b'actual-pptx']
    async def review(page,image):reviewed.append(image);return []
    async def repair(page,issues):feedback.extend(issues);return {**page,'svg':'fixed'}
    result,_=await audit_pages([{'id':'a','svg':'unsupported'}],selected_ids={'a'},render=render,review=review,repair=repair,render_errors=(ExportError,))
    assert '不支持的曲线属性' in feedback[0]['message']
    assert result[0]['review']['status']=='passed' and reviewed==[b'actual-pptx']


async def test_visual_suggestions_allow_delivery_without_automatic_repairs():
    from app.presentations.quality import require_approved_pages
    async def render(pages):return [b'actual-native-page']
    async def review(page,image):return [{'category':'visual','severity':'suggestion','message':'建议增加留白','repair':'增加段间距'}]
    async def forbidden(*args):raise AssertionError('suggestions must not trigger repair')
    pages,_=await audit_pages([{'id':'a','svg':'readable'}],selected_ids={'a'},render=render,review=review,repair=forbidden)
    require_approved_pages(pages)
    assert pages[0]['review']['status']=='passed' and pages[0]['review']['issues'][0]['message']=='建议增加留白'

async def test_visual_category_cannot_be_promoted_to_a_delivery_blocker():
    async def render(pages):return [b'actual-page']
    async def review(page,image):return [{'category':'visual','severity':'blocking','message':'颜色不够美观','repair':'换色'}]
    async def forbidden(*args):raise AssertionError('aesthetic issue must not block')
    pages,_=await audit_pages([{'id':'a','svg':'ok'}],selected_ids={'a'},render=render,review=review,repair=forbidden)
    assert pages[0]['review']['status']=='passed'

async def test_only_substantive_issues_are_sent_to_automatic_repair():
    feedback=[]
    async def render(pages):return [p['svg'].encode() for p in pages]
    async def review(page,image):
        if image==b'fixed':return []
        return [{'category':'teaching','severity':'blocking','message':'对称轴符号错误','repair':'改为负号'},{'category':'visual','severity':'suggestion','message':'配色建议','repair':'换色'}]
    async def repair(page,issues):feedback.extend(issues);return {**page,'svg':'fixed'}
    pages,_=await audit_pages([{'id':'a','svg':'bad'}],selected_ids={'a'},render=render,review=review,repair=repair)
    assert len(feedback)==1 and feedback[0]['category']=='teaching' and pages[0]['review']['status']=='passed'


def test_teaching_errors_cannot_be_downgraded_to_suggestions():
    from app.presentations.quality import parse_review
    parsed=parse_review({'status':'needs_attention','issues':[{'category':'teaching','severity':'suggestion','message':'公式符号错误','repair':'改为负号'}]})
    assert parsed[0]['severity']=='blocking'
