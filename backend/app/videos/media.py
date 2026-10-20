import asyncio
import re
from uuid import UUID
from fastapi import Depends, Request, Response
from fastapi.responses import StreamingResponse
from app.auth import require_active_user
from app.db import get_session
from app.materials.storage import MaterialStorage
from app.errors import api_error
from .service import owned_version


def close_stream(stream):
    try: stream.close()
    finally: stream.release_conn()


async def stream_video_bytes(storage,key,start,length):
    opening=asyncio.create_task(asyncio.to_thread(storage.open,key,start,length))
    try:
        stream=await asyncio.shield(opening)
    except asyncio.CancelledError:
        # A thread cannot be cancelled: dispose its result when it eventually opens.
        def dispose(task):
            if not task.cancelled() and task.exception() is None:
                close_stream(task.result())
        opening.add_done_callback(dispose)
        raise
    try:
        remaining=length
        while remaining:
            reading=asyncio.create_task(asyncio.to_thread(stream.read,min(65536,remaining)))
            try:
                data=await asyncio.shield(reading)
            except asyncio.CancelledError:
                # Finish the read before returning the pooled connection.
                current_stream=stream
                def finish_read(task):
                    if not task.cancelled(): task.exception()
                    close_stream(current_stream)
                reading.add_done_callback(finish_read)
                stream=None
                raise
            if not data: break
            remaining-=len(data)
            yield data
    finally:
        if stream is not None: close_stream(stream)


def byte_range(header, size):
    if size <= 0: raise ValueError('empty')
    if header is None: return 0,size-1,False
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if not match or not any(match.groups()): raise ValueError('invalid')
    left,right=match.groups()
    if left:
        start=int(left);end=min(int(right),size-1) if right else size-1
    else:
        length=int(right)
        if length<=0: raise ValueError('invalid')
        start=max(0,size-length);end=size-1
    if start>=size or end<start: raise ValueError('unsatisfiable')
    return start,end,True


async def video_media(project_id:UUID,version_id:UUID,asset:str,request:Request,download:bool=False,db=Depends(get_session),user=Depends(require_active_user)):
    version=await owned_version(db,user.id,project_id,version_id)
    key=version.media_key if asset=='final' else None
    if not key: raise api_error(404,'video_asset_not_found','视频文件尚未生成')
    storage=MaterialStorage(request.app.state.settings)
    try: size=await asyncio.to_thread(storage.stat,key)
    except Exception: raise api_error(503,'video_storage_unavailable','视频存储暂不可用，请稍后重试') from None
    try: start,end,partial=byte_range(request.headers.get('range'),size)
    except ValueError: return Response(status_code=416,headers={'Content-Range':f'bytes */{size}','Accept-Ranges':'bytes'})
    headers={'Accept-Ranges':'bytes','Content-Length':str(end-start+1),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    if partial: headers['Content-Range']=f'bytes {start}-{end}/{size}'
    if download: headers['Content-Disposition']=f'attachment; filename="video-v{version.number}.mp4"'
    if request.method=='HEAD': return Response(status_code=206 if partial else 200,headers=headers,media_type='video/mp4')
    return StreamingResponse(stream_video_bytes(storage,key,start,end-start+1),status_code=206 if partial else 200,headers=headers,media_type='video/mp4')


async def film_asset(project_id:UUID,version_id:UUID,asset:str,request:Request,db=Depends(get_session),user=Depends(require_active_user)):
    from .media_assets import read_asset
    version=await owned_version(db,user.id,project_id,version_id)
    entry=version.snapshot.get('direct_manifest')
    if version.status not in ('preview_ready','succeeded') or not entry or asset not in ('html','audio'):
        raise api_error(404,'preview_asset_not_found','预览资源不存在')
    storage=MaterialStorage(request.app.state.settings)
    try:data=await read_asset(storage,entry['keys'][asset],entry['hashes'][asset],'whole_audio' if asset=='audio' else 'html')
    except (KeyError,ValueError,OSError):raise api_error(409,'preview_integrity_error','预览资源校验失败，请重新生成预览') from None
    size=len(data)
    try:start,end,partial=byte_range(request.headers.get('range') if asset=='audio' else None,size)
    except ValueError:return Response(status_code=416,headers={'Content-Range':f'bytes */{size}'})
    headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Length':str(end-start+1)}
    if asset=='audio':headers['Accept-Ranges']='bytes'
    else:headers['Content-Security-Policy']="sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-src about:; img-src data:; connect-src 'none'"
    if partial:headers['Content-Range']=f'bytes {start}-{end}/{size}'
    return Response(content=b'' if request.method=='HEAD' else data[start:end+1],status_code=206 if partial else 200,headers=headers,media_type='text/html; charset=utf-8' if asset=='html' else 'audio/wav')
