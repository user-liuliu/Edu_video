"""Technical file delivery is independent from the honest internal quality verdict."""
from copy import deepcopy
from hashlib import sha256
from .quality import QualityError,content_digest,require_approved_pages

VERSION='ppt-delivery-1'

def certify_pages(pages,images):
    if not pages or len(pages)!=len(images) or any(not image for image in images):
        raise QualityError('整份课件文件验证未完成，原课件已保留')
    result=deepcopy(pages)
    for page,image in zip(result,images):
        if teacher_confirmed(page):continue
        try:require_approved_pages([page]);continue
        except QualityError:mode='fallback'
        page['delivery']={'version':VERSION,'mode':mode,'content_sha256':content_digest(page),'image_sha256':sha256(image).hexdigest()}
    return result


def confirm_teacher_page(page,user_id):
    result=deepcopy(page)
    result.pop('review',None);result.pop('delivery',None)
    result['manual_edit']={'version':'ppt-text-edit-1','confirmed_by':str(user_id)}
    result['delivery']={'version':VERSION,'mode':'teacher_confirmed','content_sha256':content_digest(result)}
    return result

def teacher_confirmed(page):
    receipt=page.get('delivery') or {};manual=page.get('manual_edit') or {}
    return (receipt.get('version')==VERSION and receipt.get('mode')=='teacher_confirmed'
            and manual.get('version')=='ppt-text-edit-1' and bool(manual.get('confirmed_by'))
            and receipt.get('content_sha256')==content_digest(page))

def require_deliverable_pages(pages):
    if not pages:raise QualityError('课件尚未制作完成')
    for page in pages:
        if teacher_confirmed(page):continue
        try:require_approved_pages([page]);continue
        except QualityError:pass
        receipt=page.get('delivery') or {}
        if (receipt.get('version')!=VERSION or receipt.get('mode') not in ('reviewed','fallback')
            or receipt.get('content_sha256')!=content_digest(page) or not receipt.get('image_sha256')):
            raise QualityError('课件文件验证未完成或内容已变化，请重新生成；原课件已保留')
