from uuid import UUID
import pytest
from test_videos import ready_project


def test_ranges_are_bounded_and_unsatisfiable_requests_fail():
    from app.videos.media import byte_range
    assert byte_range(None, 20) == (0,19,False)
    assert byte_range('bytes=2-5', 20) == (2,5,True)
    assert byte_range('bytes=18-', 20) == (18,19,True)
    assert byte_range('bytes=-4', 20) == (16,19,True)
    assert byte_range('bytes=0-999', 20) == (0,19,True)
    for value in ('bytes=20-', 'bytes=6-2', 'bytes=-0', 'bytes=0-1,3-4','items=0-1'):
        with pytest.raises(ValueError): byte_range(value,20)


async def test_private_video_media_ranges_and_response_cleanup(db,teacher_client,admin_client,box,monkeypatch):
    from app.models import VideoVersion, OutlineJob
    project,path=await ready_project(db,teacher_client,box)
    version=(await teacher_client.post(path,json={'revision':1,'idempotency_key':'media'})).json()
    row=await db.get(VideoVersion,UUID(version['id']))
    job=await db.get(OutlineJob,row.job_id)
    row.media_key='private/final.mp4';row.status=job.status='succeeded'
    await db.commit()
    closed=[];reads=[]
    class Response:
        def __init__(self,offset,length): self.data=b'0123456789'[offset:offset+length]
        def read(self,size): reads.append(size);data,self.data=self.data[:size],self.data[size:];return data
        def close(self): closed.append('closed')
        def release_conn(self): closed.append('released')
    class Storage:
        def __init__(self,settings): pass
        def stat(self,key): return 10
        def open(self,key,offset,length): return Response(offset,length)
    monkeypatch.setattr('app.videos.media.MaterialStorage',Storage)
    url=path+'/'+str(row.id)+'/media/final'
    assert (await admin_client.get(url)).status_code==404
    result=await teacher_client.get(url,headers={'Range':'bytes=2-5'})
    assert result.status_code==206 and result.content==b'2345'
    assert result.headers['content-range']=='bytes 2-5/10'
    assert result.headers['content-length']=='4'
    assert closed==['closed','released'] and max(reads)<=65536
    result=await teacher_client.get(url,headers={'Range':'bytes=99-'})
    assert result.status_code==416 and result.headers['content-range']=='bytes */10'
    result=await teacher_client.get(url+'?download=1')
    assert result.content==b'0123456789' and 'attachment' in result.headers['content-disposition']


async def test_disconnect_during_minio_open_eventually_releases_connection():
    import asyncio
    import threading
    from app.videos.media import stream_video_bytes
    started,release,closed=threading.Event(),threading.Event(),threading.Event()
    class Response:
        def close(self): pass
        def release_conn(self): closed.set()
        def read(self,size): return b'x'
    class Store:
        def open(self,*args): started.set();release.wait(5);return Response()
    stream=stream_video_bytes(Store(),'key',0,1)
    task=asyncio.create_task(anext(stream))
    await asyncio.to_thread(started.wait,2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    release.set()
    assert await asyncio.to_thread(closed.wait,2)


async def test_disconnect_during_minio_read_waits_before_releasing_connection():
    import asyncio
    import threading
    from app.videos.media import stream_video_bytes
    started,release,closed=threading.Event(),threading.Event(),threading.Event()
    class Response:
        def read(self,size): started.set();release.wait(5);return b'x'
        def close(self): assert release.is_set()
        def release_conn(self): closed.set()
    class Store:
        def open(self,*args): return Response()
    stream=stream_video_bytes(Store(),'key',0,1)
    task=asyncio.create_task(anext(stream))
    assert await asyncio.to_thread(started.wait,2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not closed.is_set()
    release.set()
    assert await asyncio.to_thread(closed.wait,2)
