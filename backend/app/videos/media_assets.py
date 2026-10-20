"""Bounded immutable resources shared by preparation and export."""
import asyncio
import hashlib
ASSET_LIMITS={'audio':20*1024*1024,'captions':256*1024,'html':4*1024*1024,'raw_html':1_500_000,'whole_audio':140*1024*1024}

def dimensions(snapshot):
    return {'16:9':(1280,720),'9:16':(720,1280),'1:1':(960,960)}.get(snapshot['form_values'].get('aspect_ratio'),(1280,720))


async def read_asset(storage,key,digest,name):
    from minio.error import S3Error
    from .media import stream_video_bytes
    try:
        size=await asyncio.to_thread(storage.stat,key)
        if not 0<size<=ASSET_LIMITS[name]:raise ValueError('预览资源大小无效，请重新生成预览')
        data=bytearray()
        async for block in stream_video_bytes(storage,key,0,size):data.extend(block)
    except (OSError,S3Error,KeyError):
        raise ValueError('预览资源不可用，请稍后重试或重新生成预览') from None
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('预览资源校验失败，请重新生成预览')
    return bytes(data)


def align_audio(data):
    """Pad at most one frame of silence before sealing the shared audio asset."""
    import io,math,wave
    with wave.open(io.BytesIO(data),'rb') as source:
        params=source.getparams();frames=source.getnframes();rate=source.getframerate()
        if rate%30 or source.getcomptype()!='NONE':raise ValueError('配音采样格式不支持精确音画对齐')
        aligned=math.ceil(frames/(rate//30))*(rate//30)
        if aligned==frames:return data
        pcm=source.readframes(frames)
    output=io.BytesIO()
    with wave.open(output,'wb') as target:
        target.setparams(params);target.writeframes(pcm+bytes((aligned-frames)*params.nchannels*params.sampwidth))
    return output.getvalue()


