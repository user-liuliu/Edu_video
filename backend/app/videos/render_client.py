import asyncio
import time
import base64
import math
import httpx
from .render_contract import MAX_OUTPUT_BYTES, decoded, DirectHtmlRuntimeError

QUEUE_TIMEOUT = 1800


class RendererClient:
    def __init__(self,settings,http):
        self.url=settings.renderer_url.rstrip('/')
        self.http=http

    async def _call(self,operation,payload,dimensions):
        if not self.url: raise ValueError('视频渲染服务尚未配置，请联系管理员')
        try:
            async with self.http.stream('POST',self.url+'/'+operation,json=payload,timeout=960,follow_redirects=False) as response:
                if response.status_code == 429:
                    return None
                if not response.is_success:
                    if response.status_code==409:
                        raise ValueError('动画运行版本不一致，请联系管理员完成更新后重试导出')
                    if response.status_code==422:
                        await response.aread()
                        try: detail=response.json().get('detail')
                        except ValueError: detail=None
                        if isinstance(detail,dict) and detail.get('code')=='direct_runtime':
                            raise DirectHtmlRuntimeError(str(detail.get('message','整片动画运行检查失败'))[:500])
                    raise ValueError('视频渲染检查失败，请重试或调整片段画面描述')
                body=bytearray()
                async for block in response.aiter_bytes():
                    body.extend(block)
                    if len(body)>MAX_OUTPUT_BYTES*1.4+4096: raise ValueError('渲染输出过大')
                import json
                result=json.loads(body)
                if operation=='validate-html':
                    if result!={'validated':True}:raise ValueError('动画运行检查未通过')
                    return result
                data=decoded(result['mp4_base64'],MAX_OUTPUT_BYTES)
                metadata=result['metadata']
                duration=metadata['duration']
                if not isinstance(duration,(int,float)) or not math.isfinite(duration) or not 0<duration<=7200 or (metadata['width'],metadata['height'])!=dimensions:
                    raise ValueError('渲染输出信息无效')
                return data,metadata
        except (httpx.HTTPError,KeyError,TypeError):
            raise ValueError('视频渲染服务连接失败，请稍后重试') from None

    async def call(self,operation,payload,dimensions):
        deadline = time.monotonic() + QUEUE_TIMEOUT
        while True:
            result = await self._call(operation,payload,dimensions)
            if result is not None:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('视频渲染等待超时，请稍后重试')
            await asyncio.sleep(min(2,remaining))

    async def direct(self,html,manifest,audio,dimensions,*,validate=False):
        from .direct_html import direct_digest
        payload={'compiler_digest':direct_digest(),'html':html,'manifest':manifest,'audio_base64':base64.b64encode(audio).decode(),'width':dimensions[0],'height':dimensions[1],'fps':30}
        return await self.call('validate-html' if validate else 'render-html',payload,dimensions)
