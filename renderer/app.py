"""Offline isolated renderer for whole-film HTML, without provider secrets."""
import asyncio
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError
from app.videos.render_contract import DirectRenderRequest, MAX_OUTPUT_BYTES

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
busy=False
MAX_REQUEST=225*1024*1024
RENDER_TIMEOUT=900


async def terminate_process(process):
    if os.name=='nt':
        if process.returncode is None:
            child=await asyncio.create_subprocess_exec('taskkill','/PID',str(process.pid),'/T','/F',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            await child.wait()
    else:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    await process.wait()


@app.get('/health')
async def health(): return {'status':'ok'}


async def execute(request,operation):
    global busy
    if busy: raise HTTPException(429,'渲染服务忙，请稍后重试',headers={'Retry-After':'2'})
    busy=True
    process=None
    try:
        length=request.headers.get('content-length')
        if length and (not length.isdigit() or int(length)>MAX_REQUEST): raise HTTPException(413,'请求过大')
        data=bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data)>MAX_REQUEST: raise HTTPException(413,'请求过大')
        try:
            body=DirectRenderRequest.model_validate_json(data)
        except (ValidationError,ValueError): raise HTTPException(422,'渲染参数无效') from None
        if operation in ('validate-html','render-html'):
            from app.videos.direct_html import direct_digest
            if body.compiler_digest!=direct_digest():raise HTTPException(409,'整片动画运行版本不一致')
        with tempfile.TemporaryDirectory(prefix='edu-render-') as folder:
            folder=Path(folder)
            (folder/'request.json').write_text(body.model_dump_json(),encoding='utf-8')
            kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
            process=await asyncio.create_subprocess_exec(sys.executable,'-m','renderer.worker',operation,str(folder),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,**kwargs)
            try:
                await asyncio.wait_for(process.wait(),timeout=RENDER_TIMEOUT)
            except asyncio.TimeoutError:
                raise HTTPException(504,'渲染超时，请缩短片段或简化画面') from None
            finally:
                # Reap before TemporaryDirectory removes browser and encoder files.
                await terminate_process(process)
            if process.returncode:
                error_file=folder/'error.json'
                if error_file.exists():
                    error=json.loads(error_file.read_text(encoding='utf-8'))
                    if error.get('code')=='direct_runtime':
                        raise HTTPException(422,{'code':'direct_runtime','message':str(error.get('message',''))[:500]})
                raise HTTPException(422,'画面检查或视频导出失败，请调整片段画面要求')
            if operation=='validate-html':return json.loads((folder/'metadata.json').read_text())
            output=folder/'output.mp4'
            if not output.exists() or output.stat().st_size>MAX_OUTPUT_BYTES: raise HTTPException(413,'视频输出过大')
            return {'mp4_base64':base64.b64encode(output.read_bytes()).decode(),'metadata':json.loads((folder/'metadata.json').read_text())}
    finally:
        busy=False


@app.post('/validate-html')
async def validate_html(request:Request):return await execute(request,'validate-html')


@app.post('/render-html')
async def render_html(request:Request):return await execute(request,'render-html')

@app.post('/ppt-graphic')
async def ppt_graphic(request:Request):
    from app.presentations.graphic_contract import GraphicSpec, VERSION, LEGACY_VERSION, MAX_PNG
    global busy
    if busy:raise HTTPException(429,'渲染服务忙',headers={'Retry-After':'2'})
    busy=True;process=None
    try:
        data=bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data)>12000:raise HTTPException(413,'信息图请求过大')
        try:
            value=json.loads(data)
            if not isinstance(value,dict) or set(value)!= {'version','source'}:raise ValueError()
            if value['version'] not in (VERSION,LEGACY_VERSION):raise HTTPException(409,'信息图运行版本不一致')
            source=GraphicSpec.model_validate(value['source'])
        except (ValueError,TypeError,KeyError):raise HTTPException(422,'信息图参数无效') from None
        with tempfile.TemporaryDirectory(prefix='edu-graphic-') as folder:
            root=Path(folder);(root/'request.json').write_text(json.dumps({'version':value['version'],'source':source.model_dump()}),encoding='utf-8')
            kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
            process=await asyncio.create_subprocess_exec(sys.executable,'-m','renderer.ppt_worker',folder,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,**kwargs)
            try:await asyncio.wait_for(process.wait(),timeout=35)
            except asyncio.TimeoutError:raise HTTPException(504,'信息图渲染超时') from None
            finally:await terminate_process(process)
            output=root/'output.json'
            if process.returncode or not output.is_file():raise HTTPException(422,'信息图渲染失败')
            if output.stat().st_size>MAX_PNG*1.4+30000:raise HTTPException(413,'信息图输出过大')
            return json.loads(output.read_text())
    finally:busy=False
