import asyncio
import codecs
import json
import logging
import time
import httpx

MAX_TRANSIENT_RETRIES = 3


async def animation_response(http, url, headers, payload):
    from app.outline.model_client import ModelCallError, _http_failure, _retry_delay
    logger = logging.getLogger(__name__)
    # Retry transient transport/provider faults without changing the frozen prompt.
    # Permanent configuration errors must fail immediately; never log URLs,
    # exception messages, keys, prompts or provider response bodies.
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        response = None
        started = time.monotonic()
        exception_type = None
        try:
            response = await _animation_response_once(http, url, headers, payload)
            if response.is_success:
                return response
            failure = _http_failure(response)
        except ModelCallError as error:
            failure = error
        except httpx.TimeoutException as error:
            exception_type = type(error).__name__
            failure = ModelCallError('整片动画模型响应超时，请稍后重试', category='timeout')
        except httpx.HTTPError as error:
            exception_type = type(error).__name__
            failure = ModelCallError('整片动画模型连接中断，请稍后重试', category='connection')
        retry = attempt < MAX_TRANSIENT_RETRIES and failure.category in ('timeout', 'connection', 'rate_limit', 'unavailable')
        logger.warning('animation_request_failed category=%s status=%s exception_type=%s retry=%s retry_count=%s elapsed_seconds=%.1f',
                       failure.category, failure.status_code, exception_type, retry, attempt, time.monotonic() - started)
        if not retry:
            raise failure from None
        await asyncio.sleep(_retry_delay(response, attempt))


async def _animation_response_once(http, url, headers, payload, *, label='整片动画'):
    # Large animation JSON must not wait behind an upstream buffered response.
    # Discard partial streams, bound bytes and total time, then validate as usual.
    async def receive():
        async with http.stream('POST',url,headers=headers,json=payload,timeout=150) as response:
            if not response.is_success or 'text/event-stream' not in response.headers.get('content-type',''):
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>2*1024*1024: raise ValueError(f'{label}模型返回内容过大')
                # aiter_bytes has already decoded Content-Encoding. Do not ask
                # httpx to decompress this body a second time.
                decoded_headers={k:v for k,v in response.headers.items()
                                 if k.lower() not in ('content-encoding','content-length','transfer-encoding')}
                return httpx.Response(response.status_code,content=bytes(data),headers=decoded_headers)
            decoder=codecs.getincrementaldecoder('utf-8')()
            buffer='';content=[];size=0;content_size=0;oversized=False;finished=False;done=False;valid=True;finish_reason=None
            def consume(line):
                nonlocal content_size,oversized,finished,done,valid,finish_reason
                line=line.strip()
                # Compatible gateways sometimes terminate SSE heartbeats with
                # a plain JSON error, including a final line without newline.
                if line.startswith('data:'):value=line[5:].strip()
                elif line.startswith('{'):
                    try:event=json.loads(line)
                    except (ValueError,TypeError):return None
                    if isinstance(event,dict) and event.get('error'):
                        return _stream_error_response(event['error'],response.headers)
                    return None
                else:return None
                if value=='[DONE]':done=True;return None
                try:
                    event=json.loads(value)
                    if event.get('error'):
                        return _stream_error_response(event['error'],response.headers)
                    for choice in event.get('choices',[]):
                        if choice.get('index',0)!=0:continue
                        part=choice.get('delta',{}).get('content')
                        if part is not None:
                            if not isinstance(part,str) or finished:valid=False
                            else:
                                content_size+=len(part.encode('utf-8'))
                                if content_size>2*1024*1024:oversized=True;break
                                content.append(part)
                        reason=choice.get('finish_reason')
                        if reason is not None:
                            finish_reason=reason;finished=reason=='stop'
                            if not finished:valid=False
                except (ValueError,TypeError,AttributeError):valid=False
                return None
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>8*1024*1024: raise ValueError(f'{label}模型流式响应过大')
                buffer+=decoder.decode(chunk)
                while '\n' in buffer:
                    line,buffer=buffer.split('\n',1)
                    error=consume(line)
                    if error is not None:return error
                    if done:break
                if oversized:raise ValueError(f'{label}模型生成内容过大')
                if done:break
            buffer+=decoder.decode(b'',final=True)
            if not done and buffer.strip():
                error=consume(buffer)
                if error is not None:return error
            if oversized:raise ValueError(f'{label}模型生成内容过大')
            if finish_reason=='length':
                from app.outline.model_client import ModelCallError
                raise ModelCallError(f'{label}模型达到输出长度上限，未生成完整内容，请简化生成要求后重试',category='output_limit')
            if finish_reason=='content_filter':
                from app.outline.model_client import ModelCallError
                raise ModelCallError(f'{label}模型未通过服务方内容限制，请调整内容后重试',category='invalid_request')
            # An incomplete stream is a transport failure, not bad generated
            # HTML. Discard it and retry the original request within the budget.
            if not valid or not done or not finished:
                from app.outline.model_client import ModelCallError
                raise ModelCallError(f'{label}模型响应中断或未完整返回，请重试', category='connection')
            result=''.join(content)
            return httpx.Response(200,json={'choices':[{'message':{'content':result}}]})
    try:
        return await asyncio.wait_for(receive(),timeout=300)
    except asyncio.TimeoutError:
        raise httpx.ReadTimeout(f'{label}模型返回超时') from None


def _stream_error_response(error, headers):
    # Providers may send errors after HTTP 200. Route these through the same
    # bounded transport recovery and safe messages as non-streaming failures.
    error=error if isinstance(error,dict) else {}
    tags={str(error.get(key,'')).lower() for key in ('code','type')}
    status=next((int(error[key]) for key in ('status','status_code','code')
                 if str(error.get(key,'')).isdigit() and 400<=int(error[key])<=599),502)
    if tags & {'invalid_api_key','authentication_error','unauthorized'}:status=401
    elif tags & {'permission_error','permission_denied','forbidden'}:status=403
    elif tags & {'rate_limit_error','rate_limit_exceeded'}:status=429
    elif tags & {'invalid_request_error','context_length_exceeded','content_policy_violation','content_filter'}:status=400
    return httpx.Response(status,json={'error':error},
                          headers={'Retry-After':headers['Retry-After']} if 'Retry-After' in headers else {})


